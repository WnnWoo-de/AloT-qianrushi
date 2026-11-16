from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.response import ok
from app.core.audit import record_access, record_service
from app.core.settings import ENVIRONMENT, NODE_ID, SERVICE_NAME
from app.realtime.hub import hub
from app.schemas import EventCreate, EventUpdate, RobotTelemetry
from app.services import state_service as service

PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_PREFIX = "/api/v1"

@asynccontextmanager
async def lifespan(_: FastAPI):
    meta = service.initialize_runtime()
    record_service("service_start", {"environment": ENVIRONMENT, "node_id": NODE_ID, "cache": meta})
    try:
        yield
    finally:
        record_service("service_stop", {"environment": ENVIRONMENT, "node_id": NODE_ID})


app = FastAPI(
    title="银龄卫士多机器人协同服务",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)

@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
    record_access(request.method, request.url.path, response.status_code, duration_ms, request_id)
    return response

@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"code": exc.status_code, "message": str(exc.detail), "data": None})

@app.get(f"{API_PREFIX}/health")
def health(): return ok({"status": "healthy", "service": SERVICE_NAME, "environment": ENVIRONMENT, "node_id": NODE_ID})

@app.get(f"{API_PREFIX}/system/status")
def system_status(): return ok(service.system_status())

@app.get(f"{API_PREFIX}/robots")
def robots(): return ok(service.list_robots())

@app.get(f"{API_PREFIX}/robots/{{robot_id}}")
def robot_detail(robot_id: str):
    item = service.get_robot(robot_id)
    if not item: raise HTTPException(404, "机器人不存在")
    return ok(item)

@app.post(f"{API_PREFIX}/robots/{{robot_id}}/telemetry")
async def robot_telemetry(robot_id: str, payload: RobotTelemetry):
    item = service.update_robot(robot_id, payload.model_dump())
    if not item: raise HTTPException(404, "机器人不存在")
    await hub.broadcast({"type": "robot_update", "data": item})
    return ok(item, "telemetry accepted")

@app.get(f"{API_PREFIX}/tasks")
def tasks(): return ok(service.list_tasks())

@app.get(f"{API_PREFIX}/tasks/current")
def current_task(): return ok(service.current_task())

@app.get(f"{API_PREFIX}/events")
def events(): return ok(service.list_events())

@app.get(f"{API_PREFIX}/events/current")
def current_event(): return ok(service.current_event())

@app.post(f"{API_PREFIX}/events")
async def create_event(payload: EventCreate):
    item = service.create_event(payload.model_dump())
    await hub.broadcast({"type": "event_update", "data": item})
    return ok(item, "event created")

@app.patch(f"{API_PREFIX}/events/{{event_id}}")
async def update_event(event_id: str, payload: EventUpdate):
    item = service.update_event(event_id, payload.model_dump(exclude_none=True))
    if not item: raise HTTPException(404, "事件不存在")
    await hub.broadcast({"type": "event_update", "data": item})
    return ok(item, "event updated")

@app.get(f"{API_PREFIX}/map")
def map_state(): return ok(service.map_state())

@app.get(f"{API_PREFIX}/statistics")
def statistics(): return ok(service.statistics())

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

app.mount("/assets", StaticFiles(directory=PROJECT_ROOT / "assets"), name="assets")
app.mount("/js", StaticFiles(directory=PROJECT_ROOT / "js"), name="js")

@app.get("/app.js", include_in_schema=False)
def frontend_app(): return FileResponse(PROJECT_ROOT / "app.js", media_type="application/javascript")

@app.get("/style.css", include_in_schema=False)
def frontend_style(): return FileResponse(PROJECT_ROOT / "style.css", media_type="text/css")

@app.get("/", include_in_schema=False)
def frontend_index(): return FileResponse(PROJECT_ROOT / "index.html")
