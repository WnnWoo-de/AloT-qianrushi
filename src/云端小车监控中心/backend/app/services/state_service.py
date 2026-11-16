from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from app.cache.runtime_cache import RuntimeCache
from app.core.audit import record
from app.core.clock import now_iso
from app.core.settings import CACHE_DSN, ENVIRONMENT, NODE_ID


def empty_state() -> dict[str, Any]:
    return {
        "meta": {"schema_version": 1, "node_id": NODE_ID},
        "system": {},
        "robots": [],
        "tasks": [],
        "events": [],
        "map": {},
        "statistics": {},
    }


cache = RuntimeCache("robot_search", empty_state)


def initialize_runtime() -> dict[str, Any]:
    def update(state: dict[str, Any]):
        meta = state.setdefault("meta", {})
        meta["schema_version"] = 1
        meta["node_id"] = NODE_ID
        meta["environment"] = ENVIRONMENT
        meta["cache_backend"] = CACHE_DSN
        meta["last_boot_at"] = now_iso()
        meta["state"] = "warm"
        return deepcopy(meta)
    return cache.mutate(update)


def system_status() -> dict[str, Any]:
    state = cache.read()
    robots = state.get("robots", [])
    result = deepcopy(state.get("system", {}))
    result.setdefault("floor", 2)
    result.setdefault("status", "巡检链路正常 · 未发现异常")
    result["service"] = "online"
    result["robot_total"] = len(robots)
    result["robot_online"] = sum(1 for item in robots if item.get("online"))
    result["updated_at"] = now_iso()
    return result


def list_robots() -> list[dict[str, Any]]:
    return deepcopy(cache.read().get("robots", []))


def get_robot(robot_id: str) -> dict[str, Any] | None:
    return next((r for r in list_robots() if r.get("robot_id") == robot_id), None)


def update_robot(robot_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    def update(state: dict[str, Any]):
        for robot in state.setdefault("robots", []):
            if robot.get("robot_id") == robot_id:
                robot.update(payload)
                robot["last_update"] = now_iso()
                return deepcopy(robot)
        return None
    item = cache.mutate(update)
    if item:
        record("telemetry_update", "robot", robot_id, payload)
    return item


def list_tasks() -> list[dict[str, Any]]:
    return deepcopy(cache.read().get("tasks", []))


def current_task() -> dict[str, Any] | None:
    tasks = list_tasks()
    return tasks[0] if tasks else None


def list_events() -> list[dict[str, Any]]:
    return deepcopy(cache.read().get("events", []))


def current_event() -> dict[str, Any] | None:
    events = list_events()
    return events[0] if events else None


def create_event(payload: dict[str, Any]) -> dict[str, Any]:
    now = now_iso()
    event_id = payload.get("event_id") or f"evt-{datetime.now().strftime('%Y%m%d%H%M%S%f')[:18]}"
    item = {
        "event_id": str(event_id), "type": str(payload.get("type") or "异常事件"),
        "level": str(payload.get("level") or "待复核"), "position": str(payload.get("position") or "未标注区域"),
        "status": str(payload.get("status") or "已上报"), "created_at": now, "updated_at": now,
    }
    def update(state: dict[str, Any]):
        state.setdefault("events", []).insert(0, item)
        state["events"] = state["events"][:100]
        return deepcopy(item)
    result = cache.mutate(update)
    record("event_create", "event", item["event_id"], item)
    return result


def update_event(event_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    def update(state: dict[str, Any]):
        for item in state.setdefault("events", []):
            if item.get("event_id") == event_id:
                if payload.get("status") is not None:
                    item["status"] = payload["status"]
                if payload.get("level") is not None:
                    item["level"] = payload["level"]
                item["updated_at"] = now_iso()
                return deepcopy(item)
        return None
    result = cache.mutate(update)
    if result:
        record("event_update", "event", event_id, payload)
    return result


def map_state() -> dict[str, Any]:
    return deepcopy(cache.read().get("map", {}))


def statistics() -> dict[str, Any]:
    result = deepcopy(cache.read().get("statistics", {}))
    robots = list_robots()
    result["online_robots"] = sum(1 for robot in robots if robot.get("online"))
    result["robot_total"] = len(robots)
    result["updated_at"] = now_iso()
    return result
