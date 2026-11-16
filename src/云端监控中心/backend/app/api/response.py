from typing import Any
from app.core.clock import now_iso


def ok(data: Any, message: str = "ok") -> dict[str, Any]:
    return {"code": 0, "message": message, "data": data, "request_time": now_iso()}
