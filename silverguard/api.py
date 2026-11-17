"""三端默认复用协同 API；SILVERGUARD_DB 可指定同机数据库路径。"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from silverguard.store import Conflict, Store, now


class EventCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    event_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    type: str = Field(min_length=1, max_length=100)
    position: str = Field(min_length=1, max_length=200)
    level: str = "待复核"
    source: str = "controlled-test"


class Telemetry(BaseModel):
    online: bool = True
    battery: float = Field(ge=0, le=100)
    position: dict[str, float] | None = None
    status: str = "巡逻中"


class Receipt(BaseModel):
    robot_id: str = Field(min_length=1)
    status: Literal["已接单", "已到场", "失败"]
    reason: str = ""


class Confirmation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    handled_by: str = Field(min_length=1, max_length=100)


class EventPatch(BaseModel):
    status: Literal["处理中", "已完成", "已处理"] | None = None
    handled_by: str | None = None
    popup_shown: bool | None = None


def finalize(app: FastAPI):
    """保留优先注册的共享路由，移除同路径旧实现，避免 OpenAPI 与实际行为相反。"""
    if not hasattr(app.state, "collaboration_store"):
        return
    seen = set()
    routes = []
    for route in app.router.routes:
        keys = {(route.path, method) for method in (getattr(route, "methods", None) or [])}
        if keys and keys <= seen:
            continue
        seen.update(keys)
        routes.append(route)
    app.router.routes[:] = routes
    app.openapi_schema = None


def install(app: FastAPI, hub):
    if os.environ.get("SILVERGUARD_LEGACY") == "1":
        return
    path = os.environ.get("SILVERGUARD_DB") or str(Path(__file__).resolve().parents[1] / "runtime/collaboration.sqlite3")
    store = Store(path)
    app.state.collaboration_store = store
    router = APIRouter(prefix="/api/v1", tags=["可追踪协同链路"])

    def ok(value):
        return {"code": 0, "message": "ok", "data": value}

    def event_view(row):
        return {**row, "id": row["event_id"], "location": row.get("location") or row["position"]}

    def task_view(row):
        return {**row, "id": row["task_id"], "robotId": row.get("robot_id")}

    def call(fn, *args):
        try:
            return ok(fn(*args))
        except KeyError:
            raise HTTPException(404, "事件、任务或机器人不存在")
        except Conflict as exc:
            raise HTTPException(409, str(exc))

    @router.get("/collaboration/status")
    def status():
        return ok({"enabled": True, "mode": "single-host-sqlite", "physical_robot_verified": False})

    @router.get("/system/status")
    def system_status():
        robots = store.list("robots")
        return ok({"service": "online", "status": "软件协同链路在线（未验证实车）", "robot_total": len(robots), "robot_online": sum(bool(r.get("online")) for r in robots), "updated_at": now(), "mode": "single-host-sqlite"})

    @router.get("/statistics")
    def statistics():
        robots = store.list("robots")
        tasks = store.list("tasks")
        return ok({"robot_total": len(robots), "online_robots": sum(bool(r.get("online")) for r in robots), "task_total": len(tasks), "task_completed": sum(t["done"] for t in tasks), "event_total": len(store.list("events")), "scope": "software-chain-not-field-availability"})

    @router.post("/events")
    def create_event(payload: EventCreate):
        return call(lambda value: event_view(store.create_event(value)), payload.model_dump())

    @router.get("/events")
    def events(source: str | None = None):
        rows = store.list("events")
        return ok([event_view(row) for row in rows if not source or row.get("source") == source])

    @router.get("/events/current")
    def current_event():
        rows = store.list("events")
        return ok(event_view(rows[0]) if rows else None)

    @router.get("/events/{event_id}")
    def event(event_id: str):
        return call(lambda key: event_view(store.get("events", key)), event_id)

    @router.get("/events/{event_id}/trace")
    def trace(event_id: str):
        call(store.get, "events", event_id)
        return ok([r for r in store.changes() if r["data"].get("event_id") == event_id])

    @router.post("/events/{event_id}/confirm")
    def confirm(event_id: str, payload: Confirmation):
        return call(lambda key, actor: event_view(store.confirm(key, actor)), event_id, payload.handled_by)

    @router.patch("/events/{event_id}")
    def patch_event(event_id: str, payload: EventPatch):
        if payload.status:
            actor = (payload.handled_by or "").strip()
            if not actor:
                raise HTTPException(422, "护工确认须提供 handled_by")
            if payload.status == "处理中":
                return call(lambda key, actor: event_view(store.start_care(key, actor)), event_id, actor)
            return call(lambda key, actor: event_view(store.confirm(key, actor)), event_id, actor)
        if payload.popup_shown is not None:
            return call(lambda key, shown: event_view(store.mark_popup(key, shown)), event_id, payload.popup_shown)
        raise HTTPException(422, "未提供可更新字段")

    @router.get("/tasks")
    def tasks():
        return ok([task_view(row) for row in store.list("tasks")])

    @router.get("/tasks/current")
    def current_task():
        rows = store.list("tasks")
        return ok(task_view(rows[0]) if rows else None)

    @router.get("/tasks/{task_id}")
    def task(task_id: str):
        return call(lambda key: task_view(store.get("tasks", key)), task_id)

    @router.post("/tasks/{task_id}/dispatch")
    def dispatch(task_id: str):
        return call(lambda key: task_view(store.dispatch(key)), task_id)

    @router.patch("/tasks/{task_id}")
    def receipt(task_id: str, payload: Receipt):
        return call(lambda key, state, robot, reason: task_view(store.transition(key, state, robot, reason)), task_id, payload.status, payload.robot_id, payload.reason)

    @router.post("/tasks")
    @router.delete("/tasks/{task_id}")
    def reject_manual_task(task_id: str = ""):
        raise HTTPException(409, "协同模式的任务仅由事件创建，不允许手工新增或删除证据链")

    @router.get("/robots")
    def robots():
        return ok(store.list("robots"))

    @router.get("/robots/{robot_id}")
    def robot(robot_id: str):
        return call(store.get, "robots", robot_id)

    @router.post("/robots/{robot_id}/telemetry")
    def telemetry(robot_id: str, payload: Telemetry):
        return call(store.telemetry, robot_id, payload.model_dump())

    # 必须在原业务路由之前调用 install，保证同一路径只由共享链路处理。
    app.include_router(router)
    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with original(application):
            # 历史状态由 HTTP 快照恢复；WS 仅转发启动后的增量。
            changes = await asyncio.to_thread(store.changes)
            cursor = changes[-1]["seq"] if changes else 0

            async def relay():
                nonlocal cursor
                while True:
                    for change in await asyncio.to_thread(store.changes, cursor):
                        await hub.broadcast({"type": change["kind"], "data": change["data"]})
                        cursor = change["seq"]
                    await asyncio.sleep(0.5)

            relay_task = asyncio.create_task(relay())
            try:
                yield
            finally:
                relay_task.cancel()
                with suppress(asyncio.CancelledError):
                    await relay_task

    app.router.lifespan_context = lifespan
