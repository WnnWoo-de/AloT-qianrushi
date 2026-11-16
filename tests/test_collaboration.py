from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from silverguard.api import finalize, install
from silverguard.store import Conflict, Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "state.sqlite3")


def event(key="evt-1"):
    return {"event_id": key, "run_id": "run-lab", "type": "受控演练", "position": "模拟走廊"}


def online(store, key="A"):
    return store.telemetry(key, {"online": True, "battery": 90})


def test_duplicate_concurrent_and_restart(store):
    online(store)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: Store(store.path).create_event(event()), range(16)))
    assert len({r["task_id"] for r in results}) == 1
    restored = Store(store.path)
    assert len(restored.list("events")) == len(restored.list("tasks")) == 1
    assert len(restored.changes()) == 3  # 心跳、事件、任务；重复不新增派单审计
    with pytest.raises(Conflict):
        store.create_event({**event(), "position": "另一区域"})


def test_full_trace_and_closed_restart(store):
    online(store)
    e = store.create_event(event())
    tid = e["task_id"]
    with pytest.raises(Conflict):
        store.confirm(e["event_id"], "护工-测试")
    with pytest.raises(Conflict):
        store.transition(tid, "已接单", "B")
    with pytest.raises(Conflict):
        store.transition(tid, "已到场", "A")
    for state in ("已接单", "已到场"):
        store.transition(tid, state, "A")
        before = len(store.changes())
        store.transition(tid, state, "A")
        assert len(store.changes()) == before
    final = store.confirm(e["event_id"], "护工-测试")
    assert final["status"] == "已处理"
    restored = Store(store.path)
    assert restored.confirm(e["event_id"], "护工-测试") == final
    task = restored.get("tasks", tid)
    assert all(k in task for k in ("dispatched_at", "accepted_at", "arrived_at", "confirmed_at"))
    assert restored.create_event(event())["task_id"] == tid
    with pytest.raises(Conflict):
        store.transition(tid, "已接单", "A")


def test_waiting_offline_battery_reservation_and_failure(store):
    store.telemetry("LOW", {"online": True, "battery": 5})
    store.telemetry("OFF", {"online": False, "battery": 90})
    e = store.create_event(event())
    assert store.get("tasks", e["task_id"])["status"] == "待派单"
    online(store)
    assert store.dispatch(e["task_id"])["robot_id"] == "A"
    other = store.create_event(event("evt-2"))
    assert store.get("tasks", other["task_id"])["status"] == "待派单"
    with pytest.raises(Conflict):
        store.transition(e["task_id"], "失败", "A")
    store.transition(e["task_id"], "失败", "A", "授权断网注入")
    assert store.dispatch(other["task_id"])["robot_id"] == "A"


def test_stale_heartbeat(store):
    online(store)
    with store.connection(True) as db:
        robot = store._get(db, "robots", "A")
        robot["last_update"] = "2000-01-01T00:00:00+00:00"
        store._save(db, "robots", "A", robot)
    e = store.create_event(event())
    assert store.get("tasks", e["task_id"])["status"] == "待派单"


class Hub:
    async def broadcast(self, message):
        pass


def test_three_api_instances_share_state(monkeypatch, tmp_path):
    monkeypatch.setenv("SILVERGUARD_DB", str(tmp_path / "api.sqlite3"))
    apps = [FastAPI() for _ in range(3)]
    for app in apps:
        install(app, Hub())
        app.add_api_route("/api/v1/events", lambda: {"legacy": True}, methods=["POST"])
        finalize(app)
        assert sum(route.path == "/api/v1/events" and "POST" in (getattr(route, "methods", None) or []) for route in app.routes) == 1
    with TestClient(apps[0]) as robot, TestClient(apps[1]) as cloud, TestClient(apps[2]) as mobile:
        assert robot.post("/api/v1/events", json={}).status_code == 422
        assert robot.post("/api/v1/robots/A/telemetry", json={"battery": 90}).status_code == 200
        e = robot.post("/api/v1/events", json=event()).json()["data"]
        assert cloud.get("/api/v1/events/evt-1").json()["data"] == e
        assert mobile.get("/api/v1/tasks").json()["data"][0]["task_id"] == e["task_id"]
        assert mobile.post("/api/v1/events/evt-1/confirm", json={"handled_by": " "}).status_code == 422
        assert mobile.post("/api/v1/events/evt-1/confirm", json={"handled_by": "护工"}).status_code == 409
        for state in ("已接单", "已到场"):
            assert robot.patch("/api/v1/tasks/" + e["task_id"], json={"robot_id": "A", "status": state}).status_code == 200
        assert mobile.patch("/api/v1/events/evt-1", json={"status": "已处理", "handled_by": "护工"}).status_code == 200
        assert cloud.get("/api/v1/events/current").json()["data"]["status"] == "已处理"
        assert len(cloud.get("/api/v1/events/evt-1/trace").json()["data"]) == 8
        assert cloud.get("/api/v1/events/missing/trace").status_code == 404
        assert mobile.delete("/api/v1/tasks/" + e["task_id"]).status_code == 409
