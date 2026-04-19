from datetime import date, datetime, time, timedelta, timezone

from jarvis.models import CalendarBusySlot, Priority, Task, UserContext
from jarvis.services.planning_service import (
    build_calendar_plan,
    build_reorganize_suggestions,
    estimate_minutes,
    parse_work_hours_from_context,
)


def make_task(
    title: str,
    due_date: date | None = None,
    tags: list[str] | None = None,
    priority: Priority | None = None,
) -> Task:
    now = datetime.now(timezone.utc)
    return Task(
        id=f"task_{title.replace(' ', '_')}",
        space_id="space_1",
        title=title,
        description="",
        due_date=due_date,
        priority=priority,
        tags=tags or [],
        is_done=False,
        created_at=now,
        updated_at=now,
    )


def test_estimate_minutes_keyword_bands() -> None:
    assert estimate_minutes(make_task("Implement service layer")) == 120
    assert estimate_minutes(make_task("Review release notes")) == 90
    assert estimate_minutes(make_task("Reply to email")) == 30


def test_reorganize_suggests_moves_before_deadline() -> None:
    start = date(2026, 3, 2)
    end = start + timedelta(days=5)
    deadline_day = date(2026, 3, 6)
    tasks = [make_task(f"Deep task {i}", due_date=deadline_day) for i in range(7)]

    suggestions = build_reorganize_suggestions(tasks, start, end)

    assert len(suggestions) >= 1
    assert all(s.proposed_date <= deadline_day for s in suggestions)
    assert all(s.current_date == deadline_day for s in suggestions)


def test_reorganize_respects_immovable_tags() -> None:
    start = date(2026, 3, 2)
    end = start + timedelta(days=5)
    deadline_day = date(2026, 3, 6)
    moveable = [make_task(f"Task {i}", due_date=deadline_day) for i in range(6)]
    immovable = make_task("Fixed task", due_date=deadline_day, tags=["bar_movement"])

    suggestions = build_reorganize_suggestions(moveable + [immovable], start, end)

    assert all(s.task_id != immovable.id for s in suggestions)


def test_build_calendar_plan_places_blocks() -> None:
    start = date(2026, 3, 2)
    end = start + timedelta(days=1)
    tasks = [
        make_task("Implement parser"),
        make_task("Review docs"),
    ]
    busy = [
        CalendarBusySlot(
            start=datetime.combine(start, time(9, 0), tzinfo=timezone.utc),
            end=datetime.combine(start, time(10, 0), tzinfo=timezone.utc),
            source="test",
        )
    ]

    plan = build_calendar_plan(
        tasks=tasks,
        busy_slots=busy,
        start_date=start,
        end_date=end,
        backend="anytype",
        space_id="space_1",
        min_block_minutes=30,
        now_dt=datetime.combine(start, time(8, 0), tzinfo=timezone.utc),
    )

    assert plan.plan_id.startswith("plan_")
    assert len(plan.blocks) >= 1
    assert all(block.start < block.end for block in plan.blocks)


def test_build_calendar_plan_marks_unplaced_when_fully_busy() -> None:
    start = date(2026, 3, 2)
    end = start
    tasks = [make_task("Implement architecture")]
    busy = [
        CalendarBusySlot(
            start=datetime.combine(start, time(9, 0), tzinfo=timezone.utc),
            end=datetime.combine(start, time(17, 0), tzinfo=timezone.utc),
            source="test",
        )
    ]

    plan = build_calendar_plan(
        tasks=tasks,
        busy_slots=busy,
        start_date=start,
        end_date=end,
        backend="anytype",
        space_id="space_1",
        min_block_minutes=30,
    )

    assert len(plan.blocks) == 0
    assert len(plan.unplaced) == 1


def test_build_calendar_plan_never_schedules_in_past_today() -> None:
    today = date(2026, 3, 2)
    now_local = datetime(2026, 3, 2, 15, 30, tzinfo=timezone.utc)
    tasks = [make_task("Review docs")]

    plan = build_calendar_plan(
        tasks=tasks,
        busy_slots=[],
        start_date=today,
        end_date=today,
        backend="anytype",
        space_id="space_1",
        min_block_minutes=30,
        now_dt=now_local,
        workday_start_hour=9,
        workday_end_hour=17,
    )

    assert len(plan.blocks) == 1
    assert plan.blocks[0].start >= now_local


def test_build_calendar_plan_prioritizes_high_priority_task() -> None:
    start = date(2026, 3, 2)
    now_local = datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc)
    tasks = [
        make_task("Low priority admin", priority=Priority.LOW),
        make_task("High priority architecture", priority=Priority.HIGH),
    ]

    plan = build_calendar_plan(
        tasks=tasks,
        busy_slots=[],
        start_date=start,
        end_date=start,
        backend="anytype",
        space_id="space_1",
        min_block_minutes=30,
        now_dt=now_local,
    )

    assert len(plan.blocks) >= 2
    assert plan.blocks[0].task_title == "High priority architecture"


def test_parse_work_hours_from_context() -> None:
    context = UserContext(
        preferences_raw="Working hours: 10:00-18:00",
    )

    start_hour, end_hour = parse_work_hours_from_context(context)

    assert (start_hour, end_hour) == (10, 18)
