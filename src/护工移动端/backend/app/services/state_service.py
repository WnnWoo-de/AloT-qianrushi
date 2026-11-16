from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from app.cache.runtime_cache import RuntimeCache
from app.core.audit import record
from app.core.clock import now_iso


def empty_state() -> dict[str, Any]:
    return {"elders": [], "profile": {}, "logs": [], "tasks": [], "events": [], "robots": [], "map": {}, "updated_at": now_iso()}


cache = RuntimeCache("care_mobile", empty_state)


def state(): return cache.read()

def system_status():
    return {"status":"online","care_station":"connected","cache":"ready","updated_at":now_iso()}

def elders(): return deepcopy(state().get("elders",[]))

def elder(elder_id): return next((x for x in elders() if x.get("id")==elder_id),None)

def profile(): return deepcopy(state().get("profile",{}))

def logs(elder_id=None):
    items=deepcopy(state().get("logs",[]))
    return [x for x in items if x.get("elderId")==elder_id] if elder_id else items

def create_log(payload):
    item=dict(payload); item.setdefault("id",f"log-{datetime.now().strftime('%Y%m%d%H%M%S%f')[:18]}"); item["createdAt"]=item.get("createdAt") or now_iso().replace("T"," ")[:16]
    def update(s): s.setdefault("logs",[]).insert(0,item); s["logs"]=s["logs"][:500]; s["updated_at"]=now_iso(); return deepcopy(item)
    value=cache.mutate(update); record("care_log_create","care_log",item["id"],item); return value

def tasks(): return deepcopy(state().get("tasks",[]))

def create_task(payload):
    item=dict(payload); item["task_id"]=item.get("task_id") or f"task-{datetime.now().strftime('%Y%m%d%H%M%S%f')[:18]}"; item["id"]=item["task_id"]
    item["title"]=item.get("title") or item.get("content") or "护理任务"; item["content"]=item.get("content") or item["title"]; item["created_at"]=now_iso(); item["createdAt"]=item["created_at"].replace("T"," ")[:16]
    def update(s): s.setdefault("tasks",[]).insert(0,item); s["updated_at"]=now_iso(); return deepcopy(item)
    value=cache.mutate(update); record("task_create","task",item["task_id"],item); return value

def update_task(task_id,payload):
    def update(s):
        for item in s.setdefault("tasks",[]):
            if item.get("task_id")==task_id or item.get("id")==task_id:
                item.update({k:v for k,v in payload.items() if v is not None}); item["updated_at"]=now_iso(); s["updated_at"]=now_iso(); return deepcopy(item)
        return None
    value=cache.mutate(update)
    if value: record("task_update","task",task_id,payload)
    return value

def delete_task(task_id):
    def update(s):
        items=s.setdefault("tasks",[]); before=len(items); s["tasks"]=[x for x in items if x.get("task_id")!=task_id and x.get("id")!=task_id]
        deleted=before!=len(s["tasks"])
        if deleted: s["updated_at"]=now_iso()
        return deleted
    deleted=cache.mutate(update)
    if deleted: record("task_delete","task",task_id,{})
    return deleted

def events(source=None):
    items=deepcopy(state().get("events",[]))
    return [x for x in items if x.get("source")==source or x.get("channel")==source] if source else items

def event(event_id): return next((x for x in events() if x.get("event_id")==event_id or x.get("id")==event_id),None)

def create_event(payload):
    item=dict(payload); item["event_id"]=item.get("event_id") or f"evt-{datetime.now().strftime('%Y%m%d%H%M%S%f')[:18]}"; item["id"]=item["event_id"]
    item["created_at"]=item.get("timestamp") or now_iso(); item["createdAt"]=item.get("createdAt") or item["created_at"].replace("T"," ")[:16]; item.setdefault("popup_shown",False); item.setdefault("popupShown",False); item.setdefault("channel",item.get("source"))
    def update(s): s.setdefault("events",[]).insert(0,item); s["events"]=s["events"][:300]; s["updated_at"]=now_iso(); return deepcopy(item)
    value=cache.mutate(update); record("event_create","event",item["event_id"],item); return value

def update_event(event_id,payload):
    def update(s):
        for item in s.setdefault("events",[]):
            if item.get("event_id")==event_id or item.get("id")==event_id:
                item.update({k:v for k,v in payload.items() if v is not None})
                if "popup_shown" in payload: item["popupShown"]=payload["popup_shown"]
                item["updated_at"]=now_iso(); s["updated_at"]=now_iso(); return deepcopy(item)
        return None
    value=cache.mutate(update)
    if value: record("event_update","event",event_id,payload)
    return value

def _is_today(value):
    return bool(value) and str(value)[:10] == now_iso()[:10]

def statistics():
    s=state(); logs_=s.get("logs",[]); tasks_=s.get("tasks",[]); events_=s.get("events",[])
    caregiver={
        "elderCount":len(s.get("elders",[])),
        "todayLogCount":sum(1 for x in logs_ if _is_today(x.get("createdAt") or x.get("created_at"))),
        "needFollowUpCount":sum(1 for x in logs_ if x.get("followUp")),
        "todayAlertCount":sum(1 for x in events_ if (x.get("channel")=="caregiver" or x.get("source")=="caregiver") and _is_today(x.get("createdAt") or x.get("created_at"))),
        "pendingCenterAlertCount":sum(1 for x in events_ if (x.get("channel")=="center" or x.get("source")=="center") and x.get("status")!="已完成"),
        "todoPendingCount":sum(1 for x in tasks_ if not x.get("done")),
        "todoDoneCount":sum(1 for x in tasks_ if x.get("done")),
    }
    return {"caregiver":caregiver,"updated_at":now_iso()}

def robots(): return deepcopy(state().get("robots", []))

def map_state():
    value = deepcopy(state().get("map", {}))
    value["updated_at"] = now_iso()
    return value
