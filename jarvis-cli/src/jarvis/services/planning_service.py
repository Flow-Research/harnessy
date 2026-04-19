from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
import re
from uuid import uuid4

from jarvis.models import (
    CalendarBusySlot,
    Priority,
    PlannedBlock,
    SchedulePlan,
    Suggestion,
    Task,
    UnplacedTask,
    UserContext,
)


def estimate_minutes(task: Task) -> int:
    text = f"{task.title} {(task.description or '')}".lower()
    if any(k in text for k in ("research", "design", "implement", "build", "architecture")):
        return 120
    if any(k in text for k in ("review", "meeting", "sync", "refactor", "write")):
        return 90
    if any(k in text for k in ("reply", "email", "follow up", "check", "update")):
        return 30
    if len(text) > 180:
        return 90
    return 60


def deep_work_score(task: Task) -> float:
    text = f"{task.title} {(task.description or '')}".lower()
    score = 0.2
    if any(k in text for k in ("design", "implement", "build", "architecture", "prototype")):
        score += 0.5
    if any(k in text for k in ("research", "analysis", "plan")):
        score += 0.2
    if "meeting" in text or "sync" in text:
        score -= 0.2
    return max(0.0, min(1.0, score))


def urgency_score(task: Task, today: date) -> float:
    if not task.due_date:
        return 0.3
    delta = (task.due_date - today).days
    if delta < 0:
        return 1.0
    if delta == 0:
        return 0.95
    if delta <= 2:
        return 0.85
    if delta <= 7:
        return 0.65
    return 0.4


def priority_score(task: Task) -> float:
    if task.priority == Priority.HIGH:
        return 1.0
    if task.priority == Priority.MEDIUM:
        return 0.65
    if task.priority == Priority.LOW:
        return 0.35
    return 0.5


def build_reorganize_suggestions(
    tasks: list[Task],
    start_date: date,
    end_date: date,
) -> list[Suggestion]:
    active = [
        t
        for t in tasks
        if t.due_date and start_date <= t.due_date <= end_date and t.is_moveable and not t.is_done
    ]
    if not active:
        return []

    by_day: dict[date, list[Task]] = defaultdict(list)
    for task in active:
        due = task.due_date
        if due is None:
            continue
        by_day[due].append(task)

    target_per_day = 4
    all_days: list[date] = []
    cur = start_date
    while cur <= end_date:
        if cur.weekday() < 5:
            all_days.append(cur)
        cur += timedelta(days=1)

    suggestions: list[Suggestion] = []
    for current_day in sorted(by_day.keys()):
        tasks_today = by_day[current_day]
        if len(tasks_today) <= target_per_day:
            continue

        ranked = sorted(
            tasks_today,
            key=lambda t: (
                priority_score(t),
                deep_work_score(t),
                urgency_score(t, start_date),
            ),
        )
        overflow = len(tasks_today) - target_per_day
        for task in ranked[:overflow]:
            new_day = _find_better_day(task, current_day, all_days, by_day, target_per_day)
            if not new_day or new_day == current_day:
                continue
            by_day[current_day] = [x for x in by_day[current_day] if x.id != task.id]
            by_day[new_day].append(task)
            suggestions.append(
                Suggestion(
                    id=f"sug_{uuid4().hex[:8]}",
                    task_id=task.id,
                    task_name=task.title,
                    current_date=current_day,
                    proposed_date=new_day,
                    reasoning="Protect deep-work capacity while preserving deadline safety and balancing daily load.",
                    confidence=0.72,
                    created_at=datetime.now(),
                )
            )

    return suggestions


def build_calendar_plan(
    tasks: list[Task],
    busy_slots: list[CalendarBusySlot],
    start_date: date,
    end_date: date,
    backend: str,
    space_id: str,
    min_block_minutes: int = 30,
    context: UserContext | None = None,
    now_dt: datetime | None = None,
    workday_start_hour: int | None = None,
    workday_end_hour: int | None = None,
    enforce_due_dates: bool = True,
    due_date_grace_days: int = 0,
    include_weekends: bool = True,
) -> SchedulePlan:
    now_local = now_dt or datetime.now().astimezone()
    tzinfo = now_local.tzinfo
    if tzinfo is None:
        raise RuntimeError("Could not determine local timezone")

    context_start, context_end = parse_work_hours_from_context(context)
    start_hour = workday_start_hour if workday_start_hour is not None else context_start
    end_hour = workday_end_hour if workday_end_hour is not None else context_end

    moveable = [t for t in tasks if not t.is_done and t.is_moveable]
    ranked = sorted(
        moveable,
        key=lambda t: (
            priority_score(t),
            deep_work_score(t),
            urgency_score(t, date.today()),
        ),
        reverse=True,
    )

    free_slots = _build_free_slots(
        start_date,
        end_date,
        busy_slots,
        min_block_minutes,
        now_local,
        tzinfo,
        start_hour,
        end_hour,
        include_weekends,
    )
    blocks: list[PlannedBlock] = []
    unplaced: list[UnplacedTask] = []

    for task in ranked:
        minutes = estimate_minutes(task)
        latest_date = None
        if enforce_due_dates and task.due_date:
            latest_date = task.due_date + timedelta(days=max(0, due_date_grace_days))
        slot_index = _find_slot(
            free_slots,
            minutes,
            latest_date=latest_date,
            earliest_start=now_local,
        )
        if slot_index is None:
            reason = "No free slot large enough in planning horizon"
            if latest_date:
                reason = f"No slot found before due date {latest_date.isoformat()}"
            unplaced.append(
                UnplacedTask(
                    task_id=task.id,
                    task_title=task.title,
                    reason=reason,
                )
            )
            continue
        slot_start, slot_end = free_slots.pop(slot_index)
        block_end = slot_start + timedelta(minutes=minutes)
        if block_end < slot_end:
            free_slots.append((block_end, slot_end))
        blocks.append(
            PlannedBlock(
                block_id=f"blk_{uuid4().hex[:10]}",
                task_id=task.id,
                task_title=task.title,
                start=slot_start,
                end=block_end,
                estimated_minutes=minutes,
                reason="Content-aware estimate with deep-work-first slotting.",
            )
        )

    return SchedulePlan(
        plan_id=f"plan_{uuid4().hex[:10]}",
        created_at=now_local,
        horizon_start=start_date,
        horizon_end=end_date,
        backend=backend,
        space_id=space_id,
        blocks=sorted(blocks, key=lambda b: b.start),
        unplaced=unplaced,
        warnings=[] if blocks else ["No schedulable blocks created in this horizon."],
    )


def _find_better_day(
    task: Task,
    current_day: date,
    all_days: list[date],
    by_day: dict[date, list[Task]],
    target_per_day: int,
) -> date | None:
    latest = task.due_date or all_days[-1]
    earlier = [d for d in all_days if d < current_day and d <= latest]
    later = [d for d in all_days if current_day < d <= latest]
    for day in earlier + later:
        if len(by_day[day]) < target_per_day:
            return day
    return None


def _build_free_slots(
    start_date: date,
    end_date: date,
    busy_slots: list[CalendarBusySlot],
    min_block_minutes: int,
    now_local: datetime,
    tzinfo,
    start_hour: int,
    end_hour: int,
    include_weekends: bool,
) -> list[tuple[datetime, datetime]]:
    busy = sorted(
        (
            CalendarBusySlot(
                start=s.start.astimezone(tzinfo), end=s.end.astimezone(tzinfo), source=s.source
            )
            for s in busy_slots
        ),
        key=lambda s: s.start,
    )
    slots: list[tuple[datetime, datetime]] = []
    current = start_date
    while current <= end_date:
        if include_weekends or current.weekday() < 5:
            day_start = datetime.combine(current, time(hour=start_hour, minute=0, tzinfo=tzinfo))
            day_end = datetime.combine(current, time(hour=end_hour, minute=0, tzinfo=tzinfo))
            if current == now_local.date() and day_start < now_local:
                day_start = now_local
            if day_start >= day_end:
                current += timedelta(days=1)
                continue
            windows = [(day_start, day_end)]
            busy_today = [b for b in busy if b.start.date() == current]
            for b in busy_today:
                windows = _subtract_windows(windows, b.start, b.end)
            for w_start, w_end in windows:
                if int((w_end - w_start).total_seconds() / 60) >= min_block_minutes:
                    slots.append((w_start, w_end))
        current += timedelta(days=1)
    return sorted(slots, key=lambda s: s[0])


def _subtract_windows(
    windows: list[tuple[datetime, datetime]],
    busy_start: datetime,
    busy_end: datetime,
) -> list[tuple[datetime, datetime]]:
    updated: list[tuple[datetime, datetime]] = []
    for start, end in windows:
        if busy_end <= start or busy_start >= end:
            updated.append((start, end))
            continue
        if busy_start > start:
            updated.append((start, busy_start))
        if busy_end < end:
            updated.append((busy_end, end))
    return updated


def _find_slot(
    slots: list[tuple[datetime, datetime]],
    required_minutes: int,
    latest_date: date | None = None,
    earliest_start: datetime | None = None,
) -> int | None:
    for idx, (start, end) in enumerate(sorted(slots, key=lambda s: s[0])):
        if earliest_start and start < earliest_start:
            continue
        minutes = int((end - start).total_seconds() / 60)
        if minutes < required_minutes:
            continue
        candidate_end = start + timedelta(minutes=required_minutes)
        if latest_date and candidate_end.date() > latest_date:
            continue
        if candidate_end > end:
            continue
        if minutes >= required_minutes:
            return idx
    return None


def parse_work_hours_from_context(context: UserContext | None) -> tuple[int, int]:
    default = (9, 17)
    if context is None:
        return default
    text = "\n".join(
        [
            context.preferences_raw,
            context.constraints_raw,
            context.calendar_raw,
            context.focus_raw,
        ]
    )
    pattern = re.compile(
        r"(?i)(?:work(?:ing)?|focus)\s*hours?\s*[:=-]\s*(\d{1,2})(?::(\d{2}))?\s*(?:-|to|–)\s*(\d{1,2})(?::(\d{2}))?"
    )
    match = pattern.search(text)
    if not match:
        return default
    try:
        start_hour = int(match.group(1))
        end_hour = int(match.group(3))
    except (TypeError, ValueError):
        return default
    if not (0 <= start_hour <= 23 and 1 <= end_hour <= 24 and start_hour < end_hour):
        return default
    return start_hour, end_hour
