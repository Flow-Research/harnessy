from __future__ import annotations

import json
import subprocess
from datetime import datetime

from jarvis.models import CalendarBusySlot


class GWSProvider:
    def get_busy_slots(
        self,
        start: datetime,
        end: datetime,
        calendar_id: str = "primary",
    ) -> list[CalendarBusySlot]:
        payload = {
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "items": [{"id": calendar_id}],
        }
        result = self._run(
            [
                "gws",
                "calendar",
                "freebusy",
                "query",
                "--json",
                json.dumps(payload),
                "--format",
                "json",
            ]
        )
        calendars = result.get("calendars", {})
        busy = calendars.get(calendar_id, {}).get("busy", [])
        slots: list[CalendarBusySlot] = []
        for item in busy:
            start_raw = item.get("start")
            end_raw = item.get("end")
            if not start_raw or not end_raw:
                continue
            slots.append(
                CalendarBusySlot(
                    start=datetime.fromisoformat(start_raw.replace("Z", "+00:00")),
                    end=datetime.fromisoformat(end_raw.replace("Z", "+00:00")),
                    source="gws",
                )
            )
        return slots

    def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        description: str | None = None,
        calendar_id: str = "primary",
    ) -> str:
        payload = {
            "summary": summary,
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
        }
        if description:
            payload["description"] = description

        result = self._run(
            [
                "gws",
                "calendar",
                "events",
                "insert",
                "--params",
                json.dumps({"calendarId": calendar_id}),
                "--json",
                json.dumps(payload),
                "--format",
                "json",
            ]
        )
        event_id = result.get("id")
        if not event_id:
            raise RuntimeError("gws did not return event id")
        return str(event_id)

    def delete_event(self, event_id: str, calendar_id: str = "primary") -> None:
        self._run(
            [
                "gws",
                "calendar",
                "events",
                "delete",
                "--params",
                json.dumps({"calendarId": calendar_id, "eventId": event_id}),
                "--format",
                "json",
            ]
        )

    def _run(self, args: list[str]) -> dict:
        proc = subprocess.run(args, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "gws command failed")
        output = proc.stdout.strip()
        if not output:
            return {}
        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            raise RuntimeError("gws output was not valid JSON") from exc
