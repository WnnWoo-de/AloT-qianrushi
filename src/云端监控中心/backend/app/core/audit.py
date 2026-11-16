from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Any

from app.core.clock import now_iso
from app.core.settings import DATA_ROOT

_LOCK = RLock()


def record(action: str, entity: str, entity_id: str, payload: dict[str, Any] | None = None) -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    path = DATA_ROOT / "operation.jsonl"
    item = {
        "time": now_iso(),
        "action": action,
        "entity": entity,
        "entity_id": entity_id,
        "payload": payload or {},
    }
    with _LOCK, path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
