from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock
from typing import Any, Callable

from app.core.settings import CACHE_ROOT


class RuntimeCache:
    def __init__(self, namespace: str, initial_factory: Callable[[], dict[str, Any]]) -> None:
        self._path = CACHE_ROOT / f"{namespace}.json"
        self._snapshot_path = CACHE_ROOT / f"{namespace}.snapshot.js"
        self._initial_factory = initial_factory
        self._lock = RLock()

    def _write_snapshot_unlocked(self, state: dict[str, Any]) -> None:
        self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
        tmp = self._snapshot_path.with_suffix(self._snapshot_path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            f.write("window.__CLOUD_MONITOR_CACHE__=" + payload + ";")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self._snapshot_path)

    def _read_unlocked(self) -> dict[str, Any]:
        if not self._path.exists():
            return self._initial_factory()
        try:
            with self._path.open("r", encoding="utf-8") as f:
                value = json.load(f)
            return value if isinstance(value, dict) else self._initial_factory()
        except (OSError, json.JSONDecodeError):
            return self._initial_factory()

    def ensure(self) -> dict[str, Any]:
        with self._lock:
            if self._path.exists():
                state = self._read_unlocked()
                self._write_snapshot_unlocked(state)
                return state
            return self.write(self._initial_factory())

    def read(self) -> dict[str, Any]:
        with self._lock:
            return self._read_unlocked()

    def write(self, state: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(self._path.suffix + ".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, separators=(",", ":"))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._path)
            self._write_snapshot_unlocked(state)
            return state

    def mutate(self, updater: Callable[[dict[str, Any]], Any]) -> Any:
        with self._lock:
            state = self._read_unlocked()
            result = updater(state)
            self.write(state)
            return result
