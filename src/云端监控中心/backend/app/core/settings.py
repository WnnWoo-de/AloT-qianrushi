from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = BACKEND_ROOT / "config" / "deployment.json"
RUNTIME_ROOT = BACKEND_ROOT / "runtime"
CACHE_ROOT = RUNTIME_ROOT / "cache"
DATA_ROOT = RUNTIME_ROOT / "data"


def _deployment() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        value = json.load(f)
    return value if isinstance(value, dict) else {}


_DEPLOYMENT = _deployment()


def setting(name: str, default: Any = "") -> Any:
    env_value = os.getenv(name)
    if env_value is not None:
        return env_value
    return _DEPLOYMENT.get(name.lower(), default)


BIND_HOST = str(setting("BIND_HOST", "0.0.0.0") or "0.0.0.0")
BIND_PORT = int(setting("BIND_PORT", 8000) or 8000)
PUBLIC_API_BASE_URL = str(setting("PUBLIC_API_BASE_URL", "") or "")
PUBLIC_WS_BASE_URL = str(setting("PUBLIC_WS_BASE_URL", "") or "")
DATABASE_DSN = str(setting("DATABASE_DSN", "") or "")
CACHE_DSN = str(setting("CACHE_DSN", "") or "")
TRUSTED_PROXY = str(setting("TRUSTED_PROXY", "") or "")
