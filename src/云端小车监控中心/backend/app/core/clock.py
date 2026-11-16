from datetime import datetime
from zoneinfo import ZoneInfo


def now_iso() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
