"""Bulkhead concurrency limits per resource pool."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Dict

from core.errors import ExecutionError


class Bulkhead:
    def __init__(self, name: str, max_concurrent: int = 10):
        self.name = name
        self.max = max_concurrent
        self._sem = threading.Semaphore(max_concurrent)
        self._active = 0
        self._lock = threading.Lock()

    @contextmanager
    def acquire(self, timeout: float = 5.0):
        ok = self._sem.acquire(timeout=timeout)
        if not ok:
            raise ExecutionError(f"Bulkhead full: {self.name}")
        with self._lock:
            self._active += 1
        try:
            yield
        finally:
            with self._lock:
                self._active -= 1
            self._sem.release()

    @property
    def active(self) -> int:
        with self._lock:
            return self._active


class BulkheadRegistry:
    def __init__(self):
        self._pools: Dict[str, Bulkhead] = {}

    def get(self, name: str, max_concurrent: int = 10) -> Bulkhead:
        if name not in self._pools:
            self._pools[name] = Bulkhead(name, max_concurrent)
        return self._pools[name]


bulkheads = BulkheadRegistry()
