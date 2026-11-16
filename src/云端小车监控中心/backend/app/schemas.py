from pydantic import BaseModel, Field


class RobotTelemetry(BaseModel):
    status: str = "巡逻中"
    battery: float = Field(default=92.0, ge=0, le=100)
    online: bool = True
    position: dict[str, float] | None = None
    heading: float | None = None


class EventCreate(BaseModel):
    event_id: str | None = None
    type: str
    level: str = "待复核"
    position: str
    status: str = "已上报"


class EventUpdate(BaseModel):
    status: str | None = None
    level: str | None = None
