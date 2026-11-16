from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.cache.runtime_cache import RuntimeCache
from app.core.audit import record
from app.core.clock import now_iso


def initial_state() -> dict[str, Any]:
    return {
        "system": {},
        "robots": [],
        "tasks": [],
        "events": [],
        "map": {},
        "statistics": {},
        "ui": {},
    }


cache = RuntimeCache("cloud_monitor", initial_state)


def initialize_runtime():
    cache.ensure()


def system_status():
    system = deepcopy(cache.read().get("system", {}))
    system["updated_at"] = now_iso()
    return system


def list_robots():
    return deepcopy(cache.read().get("robots", []))


def get_robot(robot_id):
    return next((r for r in list_robots() if r.get("robot_id") == robot_id), None)


def update_robot(robot_id, payload):
    def update(state):
        for item in state.setdefault("robots", []):
            if item.get("robot_id") == robot_id:
                item.update({k: v for k, v in payload.items() if v is not None})
                item["last_update"] = now_iso()
                return deepcopy(item)
        return None

    value = cache.mutate(update)
    if value:
        record("robot_update", "robot", robot_id, payload)
    return value


def list_tasks():
    return deepcopy(cache.read().get("tasks", []))


def current_task():
    tasks = list_tasks()
    return tasks[0] if tasks else None


def update_task(task_id, payload):
    def update(state):
        for item in state.setdefault("tasks", []):
            if item.get("task_id") == task_id:
                item.update({k: v for k, v in payload.items() if v is not None})
                item["updated_at"] = now_iso()
                return deepcopy(item)
        return None

    value = cache.mutate(update)
    if value:
        record("task_update", "task", task_id, payload)
    return value


def list_events():
    return deepcopy(cache.read().get("events", []))


def current_event():
    events = list_events()
    return events[0] if events else None


def update_event(event_id, payload):
    def update(state):
        for item in state.setdefault("events", []):
            if item.get("event_id") == event_id:
                item.update({k: v for k, v in payload.items() if v is not None})
                item["updated_at"] = now_iso()
                return deepcopy(item)
        return None

    value = cache.mutate(update)
    if value:
        record("event_update", "event", event_id, payload)
    return value


def map_state():
    value = deepcopy(cache.read().get("map", {}))
    value["updated_at"] = now_iso()
    return value


def statistics():
    return deepcopy(cache.read().get("statistics", {}))


def ui_state():
    return deepcopy(cache.read().get("ui", {}))
