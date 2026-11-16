from __future__ import annotations

import json
import os
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = BACKEND_ROOT / "config" / "deployment.json"
RUNTIME_ROOT = BACKEND_ROOT / "runtime"
CACHE_ROOT = RUNTIME_ROOT / "cache"
LOG_ROOT = RUNTIME_ROOT / "logs"
TMP_ROOT = RUNTIME_ROOT / "tmp"


def _deployment() -> dict[str, object]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        value = json.load(f)
    return value if isinstance(value, dict) else {}


_DEPLOYMENT = _deployment()


def setting(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is not None:
        return value
    return str(_DEPLOYMENT.get(name.lower(), default) or default)


def int_setting(name: str, default: int) -> int:
    value = setting(name, str(default))
    try:
        return int(value)
    except ValueError:
        return default


ENVIRONMENT = setting("ENVIRONMENT", "production")
SERVICE_NAME = setting("SERVICE_NAME", "silverguard-robot-search")
NODE_ID = setting("NODE_ID", "edge-gateway-2f")
BIND_HOST = setting("BIND_HOST", "0.0.0.0")
BIND_PORT = int_setting("BIND_PORT", 8000)
PUBLIC_SERVER_IP = setting("PUBLIC_SERVER_IP")
PUBLIC_API_BASE_URL = setting("PUBLIC_API_BASE_URL")
PUBLIC_WS_BASE_URL = setting("PUBLIC_WS_BASE_URL")
CACHE_DSN = setting("CACHE_DSN", "file://runtime/cache")
TRUSTED_PROXY = setting("TRUSTED_PROXY")
