from pydantic import BaseModel, Field


class RobotTelemetry(BaseModel):
    status: str | None = None
    battery: float | None = Field(default=None, ge=0, le=100)
    online: bool | None = None
    position: str | None = None


class TaskUpdate(BaseModel):
    status: str | None = None


class EventUpdate(BaseModel):
    status: str | None = None
    level: str | None = None
