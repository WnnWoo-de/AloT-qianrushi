from __future__ import annotations

import json
from threading import RLock
from typing import Any

from app.core.clock import now_iso
from app.core.settings import LOG_ROOT

_LOCK = RLock()


def _append(name: str, item: dict[str, Any]) -> None:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    path = LOG_ROOT / name
    with _LOCK, path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")


def record(action: str, entity: str, entity_id: str, payload: dict[str, Any] | None = None) -> None:
    _append("operation.jsonl", {
        "time": now_iso(),
        "action": action,
        "entity": entity,
        "entity_id": entity_id,
        "payload": payload or {},
    })


def record_access(method: str, path: str, status_code: int, process_time_ms: float, request_id: str) -> None:
    _append("access.jsonl", {
        "time": now_iso(),
        "request_id": request_id,
        "method": method,
        "path": path,
        "status_code": status_code,
        "process_time_ms": round(process_time_ms, 2),
    })
