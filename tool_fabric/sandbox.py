"""Sandbox — workspace isolation, path checks, process limits."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from core.errors import AuthorizationError, ExecutionError, ValidationError


class Workspace:
    def __init__(self, root: Path, organisation_id: str, execution_id: str):
        self.root = root.resolve()
        self.organisation_id = organisation_id
        self.execution_id = execution_id
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, relative: str) -> Path:
        """Resolve path inside workspace; reject traversal and absolute escapes."""
        if not relative or relative.strip() == "":
            raise ValidationError("Path required")
        # reject null bytes
        if "\x00" in relative:
            raise AuthorizationError("Invalid path")
        candidate = (self.root / relative).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            raise AuthorizationError(f"Path escapes workspace: {relative}")
        return candidate

    def cleanup(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)


class Sandbox:
    def __init__(self, base_dir: Optional[str] = None):
        self.base = Path(base_dir or tempfile.gettempdir()) / "cintexa_tf_workspaces"
        self.base.mkdir(parents=True, exist_ok=True)

    def create_workspace(self, organisation_id: str, execution_id: str) -> Workspace:
        # isolate orgs under separate dirs
        safe_org = hashlib.sha256(organisation_id.encode()).hexdigest()[:16]
        root = self.base / safe_org / execution_id
        return Workspace(root, organisation_id, execution_id)

    def run_process(
        self,
        *,
        argv: Sequence[str],
        cwd: Path,
        timeout_sec: int = 15,
        max_output_bytes: int = 200_000,
        env: Optional[Dict[str, str]] = None,
        network_disabled: bool = True,
    ) -> Dict:
        if not argv:
            raise ValidationError("Empty command")
        # never use shell=True
        run_env = os.environ.copy()
        # strip secrets from child by default
        for k in list(run_env.keys()):
            if any(s in k.upper() for s in ("SECRET", "PASSWORD", "TOKEN", "API_KEY", "PRIVATE")):
                run_env.pop(k, None)
        if env:
            run_env.update(env)
        try:
            proc = subprocess.run(
                list(argv),
                cwd=str(cwd),
                capture_output=True,
                timeout=timeout_sec,
                env=run_env,
                shell=False,
            )
            stdout = proc.stdout[:max_output_bytes]
            stderr = proc.stderr[: max_output_bytes // 4]
            return {
                "exit_code": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "truncated": len(proc.stdout) > max_output_bytes,
            }
        except subprocess.TimeoutExpired as e:
            raise ExecutionError(f"Process timed out after {timeout_sec}s") from e
        except FileNotFoundError as e:
            raise ExecutionError(f"Executable not found: {argv[0]}") from e
