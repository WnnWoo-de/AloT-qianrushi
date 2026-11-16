from typing import Any
from pydantic import BaseModel, ConfigDict


class PayloadModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class CareLogCreate(PayloadModel):
    elderId: str | None = None
    elderName: str | None = None
    roomNo: str | None = None
    type: str | None = None
    note: str | None = None
    mood: str | None = None
    followUp: bool = False


class TaskCreate(PayloadModel):
    task_id: str | None = None
    title: str | None = None
    content: str | None = None
    priority: str = "中"
    relatedElderName: str | None = None
    dueText: str | None = None
    status: str = "待处理"
    done: bool = False


class TaskUpdate(PayloadModel):
    title: str | None = None
    content: str | None = None
    priority: str | None = None
    status: str | None = None
    done: bool | None = None


class EventCreate(PayloadModel):
    event_id: str | None = None
    type: str | None = None
    source: str = "caregiver"
    channel: str | None = None
    timestamp: str | None = None
    status: str = "已上报"
    level: str | None = None
    location: str | None = None
    position: Any = None
    payload: dict[str, Any] | None = None


class EventUpdate(PayloadModel):
    status: str | None = None
    level: str | None = None
    popup_shown: bool | None = None
