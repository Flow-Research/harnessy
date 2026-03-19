from datetime import date, datetime

from pydantic import BaseModel, Field


class TaskPlanningInput(BaseModel):
    task_id: str
    title: str
    description: str | None = None
    due_date: date | None = None
    priority: str | None = None
    tags: list[str] = Field(default_factory=list)
    is_moveable: bool
    estimated_minutes: int = Field(ge=15, le=480)
    deep_work_score: float = Field(ge=0.0, le=1.0)
    urgency_score: float = Field(ge=0.0, le=1.0)


class CalendarBusySlot(BaseModel):
    start: datetime
    end: datetime
    source: str = "calendar"


class PlannedBlock(BaseModel):
    block_id: str
    task_id: str
    task_title: str
    start: datetime
    end: datetime
    estimated_minutes: int
    reason: str


class UnplacedTask(BaseModel):
    task_id: str
    task_title: str
    reason: str


class SchedulePlan(BaseModel):
    version: int = 1
    plan_id: str
    created_at: datetime
    horizon_start: date
    horizon_end: date
    backend: str
    space_id: str
    blocks: list[PlannedBlock] = Field(default_factory=list)
    unplaced: list[UnplacedTask] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AppliedBlockResult(BaseModel):
    block_id: str
    task_id: str
    status: str
    event_id: str | None = None
    error: str | None = None


class PlanApplyResult(BaseModel):
    version: int = 1
    plan_id: str
    applied_at: datetime
    results: list[AppliedBlockResult] = Field(default_factory=list)
