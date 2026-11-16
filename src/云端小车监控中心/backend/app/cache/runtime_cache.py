from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock
from typing import Any, Callable

from app.core.clock import now_iso
from app.core.settings import CACHE_ROOT


class RuntimeCache:
    def __init__(self, namespace: str, initial_factory: Callable[[], dict[str, Any]]) -> None:
        self._path = CACHE_ROOT / f"{namespace}.json"
        self._initial_factory = initial_factory
        self._lock = RLock()

    @property
    def path(self) -> Path:
        return self._path

    def _read_unlocked(self) -> dict[str, Any]:
        if not self._path.exists():
            return self._initial_factory()
        try:
            with self._path.open("r", encoding="utf-8") as f:
                value = json.load(f)
            return value if isinstance(value, dict) else self._initial_factory()
        except (OSError, json.JSONDecodeError):
            return self._initial_factory()

    def read(self) -> dict[str, Any]:
        with self._lock:
            return self._read_unlocked()

    def write(self, state: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            state.setdefault("meta", {})["last_persisted_at"] = now_iso()
            tmp = self._path.with_suffix(self._path.suffix + ".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._path)
            return state

    def ensure(self) -> dict[str, Any]:
        with self._lock:
            state = self._read_unlocked()
            return self.write(state)

    def mutate(self, updater: Callable[[dict[str, Any]], Any]) -> Any:
        with self._lock:
            state = self._read_unlocked()
            result = updater(state)
            self.write(state)
            return result
