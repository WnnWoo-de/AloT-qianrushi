from __future__ import annotations

import json
import os
import socket
from pathlib import Path

from app.core.clock import now_iso
from app.core.settings import RUN_ROOT

_STATE_PATH = RUN_ROOT / "service.json"


def _read() -> dict:
    try:
        with _STATE_PATH.open("r", encoding="utf-8") as f:
            value = json.load(f)
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write(value: dict) -> None:
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    tmp = _STATE_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, separators=(",", ":"))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, _STATE_PATH)


def mark_started() -> None:
    value = _read()
    value.update({
        "service": "care-mobile",
        "status": "running",
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "last_started_at": now_iso(),
    })
    value.pop("last_stopped_at", None)
    _write(value)


def mark_stopped() -> None:
    value = _read()
    value.update({"status": "stopped", "last_stopped_at": now_iso()})
    _write(value)
