from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.response import ok
from app.core.settings import CACHE_ROOT, DATA_ROOT
from app.realtime.hub import hub
from app.schemas import EventUpdate, RobotTelemetry, TaskUpdate
from app.services import state_service as service

PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_: FastAPI):
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    (DATA_ROOT / "video").mkdir(parents=True, exist_ok=True)
    service.initialize_runtime()
    yield


app = FastAPI(title="银龄卫士云端监控服务", version="1.1.0", lifespan=lifespan)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{(time.perf_counter() - started) * 1000:.2f}"
    return response


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": str(exc.detail), "data": None},
    )


@app.get(f"{API_PREFIX}/health")
def health():
    return ok({"status": "healthy", "service": "cloud-monitor"})


@app.get(f"{API_PREFIX}/system/status")
def system_status():
    return ok(service.system_status())


@app.get(f"{API_PREFIX}/robots")
def robots():
    return ok(service.list_robots())


@app.get(f"{API_PREFIX}/robots/{{robot_id}}")
def robot_detail(robot_id: str):
    item = service.get_robot(robot_id)
    if not item:
        raise HTTPException(404, "机器人不存在")
    return ok(item)


@app.post(f"{API_PREFIX}/robots/{{robot_id}}/telemetry")
async def robot_telemetry(robot_id: str, payload: RobotTelemetry):
    item = service.update_robot(robot_id, payload.model_dump(exclude_none=True))
    if not item:
        raise HTTPException(404, "机器人不存在")
    await hub.broadcast({"type": "robot_update", "data": item})
    return ok(item)


@app.get(f"{API_PREFIX}/tasks")
def tasks():
    return ok(service.list_tasks())


@app.get(f"{API_PREFIX}/tasks/current")
def current_task():
    return ok(service.current_task())


@app.patch(f"{API_PREFIX}/tasks/{{task_id}}")
async def update_task(task_id: str, payload: TaskUpdate):
    item = service.update_task(task_id, payload.model_dump(exclude_none=True))
    if not item:
        raise HTTPException(404, "任务不存在")
    await hub.broadcast({"type": "task_update", "data": item})
    return ok(item)


@app.get(f"{API_PREFIX}/events")
def events():
    return ok(service.list_events())


@app.get(f"{API_PREFIX}/events/current")
def current_event():
    return ok(service.current_event())


@app.patch(f"{API_PREFIX}/events/{{event_id}}")
async def update_event(event_id: str, payload: EventUpdate):
    item = service.update_event(event_id, payload.model_dump(exclude_none=True))
    if not item:
        raise HTTPException(404, "事件不存在")
    await hub.broadcast({"type": "event_update", "data": item})
    return ok(item)


@app.get(f"{API_PREFIX}/map")
def map_state():
    return ok(service.map_state())


@app.get(f"{API_PREFIX}/statistics")
def statistics():
    return ok(service.statistics())


@app.get(f"{API_PREFIX}/ui")
def ui_state():
    return ok(service.ui_state())


@app.websocket("/ws/monitor")
async def monitor(websocket: WebSocket):
    await hub.connect(websocket)
    try:
        await websocket.send_json({"type": "system_update", "data": service.system_status()})
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=20)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "system_update", "data": service.system_status()})
    except WebSocketDisconnect:
        hub.disconnect(websocket)
    except Exception:
        hub.disconnect(websocket)


app.mount("/css", StaticFiles(directory=PROJECT_ROOT / "css"), name="css")
app.mount("/js", StaticFiles(directory=PROJECT_ROOT / "js"), name="js")
app.mount("/images", StaticFiles(directory=PROJECT_ROOT / "images"), name="images")
app.mount(
    "/backend/runtime/data/video",
    StaticFiles(directory=PROJECT_ROOT / "backend" / "runtime" / "data" / "video"),
    name="runtime-video",
)
app.mount(
    "/backend/runtime/cache/assets",
    StaticFiles(directory=PROJECT_ROOT / "backend" / "runtime" / "cache" / "assets"),
    name="runtime-cache-assets",
)




@app.get("/backend/runtime/cache/cloud_monitor.snapshot.js", include_in_schema=False)
def frontend_cache_snapshot():
    return FileResponse(PROJECT_ROOT / "backend" / "runtime" / "cache" / "cloud_monitor.snapshot.js", media_type="application/javascript")

@app.get("/", include_in_schema=False)
def frontend_index():
    return FileResponse(PROJECT_ROOT / "index.html")
