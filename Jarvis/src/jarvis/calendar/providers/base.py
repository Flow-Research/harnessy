from datetime import datetime
from typing import Protocol

from jarvis.models import CalendarBusySlot


class CalendarProvider(Protocol):
    def get_busy_slots(
        self,
        start: datetime,
        end: datetime,
        calendar_id: str = "primary",
    ) -> list[CalendarBusySlot]: ...

    def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        description: str | None = None,
        calendar_id: str = "primary",
    ) -> str: ...

    def delete_event(self, event_id: str, calendar_id: str = "primary") -> None: ...
