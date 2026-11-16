from __future__ import annotations

import asyncio
import time
import uuid

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.response import ok
from app.realtime.hub import hub
from app.core.audit import record_access
from app.core.runtime_status import mark_started, mark_stopped
from app.schemas import CareLogCreate, EventCreate, EventUpdate, TaskCreate, TaskUpdate
from app.services import state_service as service

API_PREFIX="/api/v1"
app=FastAPI(title="银龄卫士护工移动端服务",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=False,allow_methods=["*"],allow_headers=["*"])

@app.middleware("http")
async def request_context(request:Request,call_next):
    request_id=request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]; started=time.perf_counter(); response=await call_next(request)
    elapsed=(time.perf_counter()-started)*1000
    response.headers["X-Request-ID"]=request_id; response.headers["X-Process-Time-Ms"]=f"{elapsed:.2f}"
    record_access(request.method,request.url.path,response.status_code,elapsed,request_id)
    return response

@app.exception_handler(HTTPException)
async def http_error(_:Request,exc:HTTPException): return JSONResponse(status_code=exc.status_code,content={"code":exc.status_code,"message":str(exc.detail),"data":None})

@app.on_event("startup")
def service_started(): mark_started()

@app.on_event("shutdown")
def service_stopped(): mark_stopped()

@app.get(f"{API_PREFIX}/health")
def health(): return ok({"status":"healthy","service":"care-mobile"})
@app.get(f"{API_PREFIX}/system/status")
def system_status(): return ok(service.system_status())
@app.get(f"{API_PREFIX}/elders")
def elders(): return ok(service.elders())
@app.get(f"{API_PREFIX}/elders/{{elder_id}}")
def elder(elder_id:str):
    item=service.elder(elder_id)
    if not item: raise HTTPException(404,"老人信息不存在")
    return ok(item)
@app.get(f"{API_PREFIX}/caregiver/profile")
def caregiver_profile(): return ok(service.profile())
@app.get(f"{API_PREFIX}/care-logs")
def care_logs(elder_id:str|None=Query(default=None,alias="elderId")): return ok(service.logs(elder_id))
@app.post(f"{API_PREFIX}/care-logs")
def create_care_log(payload:CareLogCreate): return ok(service.create_log(payload.model_dump(exclude_none=True)),"log created")
@app.get(f"{API_PREFIX}/tasks")
def tasks(client:str|None=None): return ok(service.tasks())
@app.get(f"{API_PREFIX}/tasks/current")
def current_task():
    items=service.tasks(); return ok(items[0] if items else None)
@app.post(f"{API_PREFIX}/tasks")
async def create_task(payload:TaskCreate):
    item=service.create_task(payload.model_dump(exclude_none=True)); await hub.broadcast({"type":"task_update","data":item}); return ok(item,"task created")
@app.patch(f"{API_PREFIX}/tasks/{{task_id}}")
async def update_task(task_id:str,payload:TaskUpdate):
    item=service.update_task(task_id,payload.model_dump(exclude_none=True))
    if not item: raise HTTPException(404,"任务不存在")
    await hub.broadcast({"type":"task_update","data":item}); return ok(item,"task updated")
@app.delete(f"{API_PREFIX}/tasks/{{task_id}}")
def delete_task(task_id:str):
    if not service.delete_task(task_id): raise HTTPException(404,"任务不存在")
    return ok({"task_id":task_id},"task deleted")
@app.get(f"{API_PREFIX}/events")
def events(source:str|None=None): return ok(service.events(source))
@app.get(f"{API_PREFIX}/events/current")
def current_event():
    items=service.events(); return ok(items[0] if items else None)
@app.get(f"{API_PREFIX}/events/{{event_id}}")
def event(event_id:str):
    item=service.event(event_id)
    if not item: raise HTTPException(404,"报警事件不存在")
    return ok(item)
@app.post(f"{API_PREFIX}/events")
async def create_event(payload:EventCreate):
    item=service.create_event(payload.model_dump(exclude_none=True)); await hub.broadcast({"type":"event_update","data":item}); return ok(item,"event created")
@app.patch(f"{API_PREFIX}/events/{{event_id}}")
async def update_event(event_id:str,payload:EventUpdate):
    item=service.update_event(event_id,payload.model_dump(exclude_none=True))
    if not item: raise HTTPException(404,"报警事件不存在")
    await hub.broadcast({"type":"event_update","data":item}); return ok(item,"event updated")
@app.get(f"{API_PREFIX}/statistics")
def statistics(): return ok(service.statistics())
@app.get(f"{API_PREFIX}/robots")
def robots(): return ok(service.robots())
@app.get(f"{API_PREFIX}/map")
def map_state(): return ok(service.map_state())
@app.websocket("/ws/monitor")
async def monitor(websocket:WebSocket):
    await hub.connect(websocket)
    try:
        await websocket.send_json({"type":"system_update","data":service.system_status()})
        while True:
            try: await asyncio.wait_for(websocket.receive_text(),timeout=20)
            except asyncio.TimeoutError: await websocket.send_json({"type":"system_update","data":service.system_status()})
    except WebSocketDisconnect: hub.disconnect(websocket)
    except Exception: hub.disconnect(websocket)
