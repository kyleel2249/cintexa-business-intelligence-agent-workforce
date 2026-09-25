"""DAG validation and scheduling helpers for mission tasks."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple

from schemas.missions import MissionTask, MissionTaskStatus


class DependencyGraph:
    def __init__(self, tasks: List[MissionTask]) -> None:
        self.tasks = {t.task_id: t for t in tasks}
        self.adj: Dict[str, List[str]] = defaultdict(list)  # parent -> children
        self.rev: Dict[str, List[str]] = defaultdict(list)  # child -> parents
        for t in tasks:
            for dep in t.dependencies:
                if dep in self.tasks:
                    self.adj[dep].append(t.task_id)
                    self.rev[t.task_id].append(dep)

    def validate(self) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        # missing deps
        for t in self.tasks.values():
            for d in t.dependencies:
                if d not in self.tasks:
                    errors.append(f"Task {t.task_id} depends on missing {d}")
        # cycles via Kahn
        indeg = {tid: len(self.rev[tid]) for tid in self.tasks}
        q = deque([tid for tid, d in indeg.items() if d == 0])
        seen = 0
        while q:
            n = q.popleft()
            seen += 1
            for c in self.adj[n]:
                indeg[c] -= 1
                if indeg[c] == 0:
                    q.append(c)
        if seen != len(self.tasks):
            errors.append("Dependency cycle detected")
        # orphaned / unreachable from roots is OK for parallel roots
        return (len(errors) == 0, errors)

    def ready_tasks(self) -> List[MissionTask]:
        ready = []
        for t in self.tasks.values():
            if t.status not in (MissionTaskStatus.PENDING, MissionTaskStatus.READY):
                continue
            parents = self.rev.get(t.task_id, [])
            if all(
                self.tasks[p].status == MissionTaskStatus.COMPLETED
                for p in parents
                if p in self.tasks
            ):
                ready.append(t)
        ready.sort(key=lambda x: (-x.priority, x.task_id))
        return ready

    def critical_path_length(self) -> int:
        """Approximate longest path in DAG (number of nodes)."""
        memo: Dict[str, int] = {}

        def dfs(tid: str) -> int:
            if tid in memo:
                return memo[tid]
            children = self.adj.get(tid, [])
            if not children:
                memo[tid] = 1
                return 1
            memo[tid] = 1 + max(dfs(c) for c in children)
            return memo[tid]

        if not self.tasks:
            return 0
        return max(dfs(tid) for tid in self.tasks)

    def blocking_score(self, task_id: str) -> int:
        """How many downstream tasks depend (transitively) on this task."""
        seen: Set[str] = set()
        stack = list(self.adj.get(task_id, []))
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            stack.extend(self.adj.get(n, []))
        return len(seen)

    def topological_layers(self) -> List[List[str]]:
        indeg = {tid: len(self.rev[tid]) for tid in self.tasks}
        layers: List[List[str]] = []
        remaining = set(self.tasks.keys())
        while remaining:
            layer = [tid for tid in remaining if indeg[tid] == 0]
            if not layer:
                # cycle remnant
                layers.append(sorted(remaining))
                break
            layers.append(sorted(layer))
            for tid in layer:
                remaining.remove(tid)
                for c in self.adj[tid]:
                    indeg[c] -= 1
        return layers
