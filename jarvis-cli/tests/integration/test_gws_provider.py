import json
import os
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from jarvis.calendar.providers.gws_provider import GWSProvider


def _gws_ready() -> bool:
    if os.environ.get("RUN_GWS_INTEGRATION_TESTS", "").lower() not in {"1", "true", "yes"}:
        return False
    proc = subprocess.run(["gws", "auth", "status"], capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        return False
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return False
    return bool(data.get("token_valid"))


def _gws_write_ready() -> bool:
    return os.environ.get("RUN_GWS_WRITE_INTEGRATION_TESTS", "").lower() in {
        "1",
        "true",
        "yes",
    }


@pytest.mark.integration
def test_gws_provider_freebusy_query() -> None:
    if not _gws_ready():
        pytest.skip("Set RUN_GWS_INTEGRATION_TESTS=1 with valid gws auth to run")

    provider = GWSProvider()
    start = datetime.now(timezone.utc)
    end = start + timedelta(days=1)

    slots = provider.get_busy_slots(start=start, end=end, calendar_id="primary")

    assert isinstance(slots, list)
    assert all(slot.start <= slot.end for slot in slots)


@pytest.mark.integration
def test_gws_provider_event_lifecycle_create_and_delete() -> None:
    if not _gws_ready():
        pytest.skip("Set RUN_GWS_INTEGRATION_TESTS=1 with valid gws auth to run")
    if not _gws_write_ready():
        pytest.skip("Set RUN_GWS_WRITE_INTEGRATION_TESTS=1 to run write lifecycle test")

    provider = GWSProvider()
    start = datetime.now(timezone.utc) + timedelta(minutes=10)
    end = start + timedelta(minutes=15)
    summary = f"Jarvis integration test {int(start.timestamp())}"

    event_id: str | None = None
    try:
        event_id = provider.create_event(
            summary=summary,
            start=start,
            end=end,
            description="Created by integration test; should be deleted automatically.",
            calendar_id="primary",
        )
        assert event_id
    finally:
        if event_id:
            provider.delete_event(event_id=event_id, calendar_id="primary")
