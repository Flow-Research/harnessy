"""Workload analysis models.

These models are used by the task scheduler's workload analyzer.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, computed_field


class DayWorkload(BaseModel):
    """Workload for a single day."""

    day_date: date = Field(description="The date")
    total_tasks: int = Field(description="Total number of tasks")
    moveable_tasks: int = Field(description="Tasks that can be rescheduled")
    immovable_tasks: int = Field(description="Tasks with bar_movement tag")
    task_ids: list[str] = Field(default_factory=list, description="IDs of tasks on this day")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> Literal["overloaded", "balanced", "light"]:
        """Determine day status based on task count."""
        if self.total_tasks > 6:
            return "overloaded"
        elif self.total_tasks < 3:
            return "light"
        return "balanced"


class WorkloadAnalysis(BaseModel):
    """Complete workload analysis for a date range."""

    start_date: date = Field(description="Start of analysis period")
    end_date: date = Field(description="End of analysis period")
    days: list[DayWorkload] = Field(default_factory=list, description="Daily workload data")
    total_moveable: int = Field(description="Total moveable tasks in range")
    total_immovable: int = Field(description="Total immovable tasks in range")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def variance(self) -> float:
        """Standard deviation of daily task counts (lower is better)."""
        if not self.days:
            return 0.0
        counts = [d.total_tasks for d in self.days]
        mean = sum(counts) / len(counts)
        variance = sum((x - mean) ** 2 for x in counts) / len(counts)
        return float(variance**0.5)
