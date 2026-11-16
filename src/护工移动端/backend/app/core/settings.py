from __future__ import annotations

import json
import os
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = BACKEND_ROOT / "config" / "deployment.json"
RUNTIME_ROOT = BACKEND_ROOT / "runtime"
CACHE_ROOT = RUNTIME_ROOT / "cache"
LOG_ROOT = RUNTIME_ROOT / "logs"
RUN_ROOT = RUNTIME_ROOT / "run"


def _deployment() -> dict[str, str]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        value = json.load(f)
    return value if isinstance(value, dict) else {}


_DEPLOYMENT = _deployment()


def setting(name: str, default: str = "") -> str:
    return os.getenv(name, str(_DEPLOYMENT.get(name.lower(), default) or default))


PUBLIC_API_BASE_URL = setting("PUBLIC_API_BASE_URL")
PUBLIC_WS_BASE_URL = setting("PUBLIC_WS_BASE_URL")
CACHE_DSN = setting("CACHE_DSN", "file://runtime/cache")
TRUSTED_PROXY = setting("TRUSTED_PROXY")
