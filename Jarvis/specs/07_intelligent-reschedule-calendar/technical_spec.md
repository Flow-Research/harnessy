# Technical Specification: Intelligent Reschedule + Calendar Mapping

> **Epic:** 07_intelligent-reschedule-calendar
> **Version:** 1.0
> **Created:** 2026-03-06
> **Status:** Reviewed draft
> **Source:** [product_spec.md](./product_spec.md)

---

## 1. Overview

### 1.1 Purpose

Define the technical implementation for adding:

1. `jarvis reorganize` (intelligent date-level task reorganization), and
2. calendar planning/apply commands that map tasks into time blocks while preserving explicit user approval.

### 1.2 Scope

**In Scope:**
- planning models for task effort and slotting
- planning services for reorganize and calendar mapping
- CLI command additions
- local plan persistence for auditability
- Google Workspace calendar provider integration via `gws`

**Out of Scope:**
- auto-daemon replanning
- multi-provider v1 support
- full bidirectional sync from calendar edits to task backends

### 1.3 Constraints

- Existing commands (`analyze`, `suggest`, `apply`, `rebalance`) must continue working.
- No silent writes to calendar.
- Deep-work-first optimization with deadline safety as hard guardrail.

---

## 2. Architecture

### 2.1 High-Level Flow

```
tasks + context + config
        |
        v
  planning_service
  (ranking + estimation + placement)
        |
        +----> reorganize recommendations (date-level)
        |
        +----> schedule plan artifact (~/.jarvis/plans/<plan_id>.json)
                          |
                          v
                  calendar_service
                  (provider abstraction)
                          |
                          v
                 gws_provider (v1)
                          |
                          v
              calendar apply result artifact
```

### 2.2 New/Updated Modules

#### New
- `src/jarvis/models/planning.py`
- `src/jarvis/services/planning_service.py`
- `src/jarvis/services/calendar_service.py`
- `src/jarvis/calendar/providers/base.py`
- `src/jarvis/calendar/providers/gws_provider.py`
- `src/jarvis/plans/state.py`

#### Updated
- `src/jarvis/cli.py` (new command group and command wiring)
- `src/jarvis/config/schema.py` (optional planner defaults)
- `src/jarvis/models/__init__.py` (new exports)

---

## 3. Data Model Design

### 3.1 Planning Models

```python
class TaskPlanningInput(BaseModel):
    task_id: str
    title: str
    description: str | None
    due_date: date | None
    priority: Priority | None
    tags: list[str]
    is_moveable: bool
    estimated_minutes: int
    deep_work_score: float  # 0..1
    urgency_score: float    # 0..1

class CalendarBusySlot(BaseModel):
    start: datetime
    end: datetime
    source: str

class PlannedBlock(BaseModel):
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
    plan_id: str
    created_at: datetime
    horizon_start: date
    horizon_end: date
    blocks: list[PlannedBlock]
    unplaced: list[UnplacedTask]
    warnings: list[str]
```

### 3.2 Persistence Format

- `~/.jarvis/plans/<plan_id>.json`
- `~/.jarvis/plans/<plan_id>.apply.json`

Artifacts include version field for forward compatibility.

---

## 4. Scheduling Algorithm (MVP)

### 4.1 Priority Stack

1. Protect deep work windows (primary objective).
2. Preserve deadline feasibility (hard constraint).
3. Smooth daily load (secondary objective).

### 4.2 Scoring

For each task, derive:

- `urgency_score` from due date proximity and overdue state.
- `deep_work_score` from task content cues and context constraints.
- `estimated_minutes` from content-aware estimation rules.

Sort key (descending):

`(deep_work_score, urgency_score, priority_weight)`

### 4.3 Duration Estimation Heuristics

Deterministic baseline before AI refinement:

- Short admin-like tasks: 30 min
- Medium implementation/review tasks: 60-90 min
- Heavy design/build tasks: 120 min+

Heuristics inspect title/description keyword patterns and length.

### 4.4 Slot Selection

- Fetch busy slots from provider in planning horizon.
- Build free slots in working hours.
- Reject slots shorter than min block.
- Place deep-work tasks in best uninterrupted slots first.
- Place remaining tasks by urgency while balancing day totals.

### 4.5 Fallback Behavior

If no suitable slot exists:
- task is emitted to `unplaced` with explicit reason
- planning still succeeds with warning

---

## 5. Service Interfaces

### 5.1 `planning_service.py`

```python
def build_reorganize_recommendations(tasks: list[Task], start: date, end: date, context: UserContext) -> list[Suggestion]:
    ...

def build_calendar_plan(tasks: list[Task], busy_slots: list[CalendarBusySlot], start: date, end: date, context: UserContext) -> SchedulePlan:
    ...
```

### 5.2 `calendar/providers/base.py`

```python
class CalendarProvider(Protocol):
    def get_busy_slots(self, start: datetime, end: datetime) -> list[CalendarBusySlot]:
        ...

    def create_event(self, title: str, start: datetime, end: datetime, description: str | None = None) -> str:
        ...
```

### 5.3 `gws_provider.py`

Implementation uses `gws` CLI shell boundary and parses JSON/text output into provider model.

---

## 6. CLI Specification

### 6.1 Command Additions

#### `jarvis reorganize`

Flags:
- `--days` (default 14)
- `--space`
- `--backend`
- `--dry-run`

Behavior:
- computes recommendations only (no calendar writes)
- optional apply path can reuse existing suggestion mechanics

#### `jarvis calendar plan`

Flags:
- `--days` (default 14)
- `--min-block` (default 30)
- `--max-blocks` (optional cap)
- `--dry-run`

Behavior:
- builds and persists a plan artifact
- prints plan ID and summary

#### `jarvis calendar apply`

Flags:
- `--plan <id>`
- `--yes`

Behavior:
- loads plan artifact
- requires explicit confirmation if `--yes` absent
- writes events through provider
- persists apply result artifact

### 6.2 Apply Semantics (v1)

- Apply is **idempotent by `plan_id` + block correlation key**.
- If apply artifact already marks a block as created, rerun must skip with `already_applied` status.
- V1 apply writes calendar events only; it does not auto-update task due dates.
- Any task-date changes remain a separate explicit command path.

---

## 7. Error Handling

| Failure | Handling |
|---------|----------|
| Missing provider auth | Show actionable login/config message |
| Busy-slot fetch failure | Abort plan with clear provider error |
| Partial event creation failure | Continue remaining items; persist failed list |
| Invalid plan ID | Show available plan IDs and exit non-zero |
| Empty task set | Return graceful no-op plan |
| Replayed apply on same plan | Return idempotent statuses without duplicate event writes |

---

## 8. Backward Compatibility and Migration

- Existing adapters are untouched for task/journal CRUD.
- Planner is additive; no breaking changes to current command arguments.
- Legacy suggestion state remains valid.

---

## 9. Testing Strategy

### 9.1 Unit Tests

- `tests/planning/test_estimation.py`
- `tests/planning/test_slot_selection.py`
- `tests/planning/test_balancing.py`
- `tests/plans/test_state.py`

### 9.2 CLI Tests

- `tests/cli/test_reorganize_command.py`
- `tests/cli/test_calendar_plan_command.py`
- `tests/cli/test_calendar_apply_command.py`

### 9.3 Integration Tests

- Provider contract tests for gws boundary behavior
- Regression tests for existing scheduling commands
- Idempotency replay test: repeated `calendar apply --plan <id>` creates no duplicates

### 9.4 Quality Gates

- zero regressions in existing schedule commands
- deterministic plan serialization format
- apply report generated for all write attempts

---

## 10. Implementation Work Plan

1. Add planning models + plan state persistence.
2. Implement deterministic estimator + scoring.
3. Implement slot builder and placement algorithm.
4. Add `jarvis reorganize` command.
5. Add calendar provider abstraction.
6. Implement `gws_provider`.
7. Add `jarvis calendar plan` and `jarvis calendar apply`.
8. Add tests and run full verification.

---

## 11. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Overbooking due to weak estimation | conservative default durations + user override |
| Provider output format drift | isolate parser in provider module + contract tests |
| User distrust from opaque placement | include per-block rationale in plan output |

---

## 12. Open Decisions for Implementation Start

1. Work-hour defaults source (`config.yaml` vs context override precedence).
2. Whether `reorganize` should immediately emit `Suggestion` objects or a new plan type.
3. Whether apply should support rollback attempt for created events in same run.

---

## 13. Iteration Notes

### Iteration 2 Refinements (2026-03-06)

- Added explicit apply idempotency contract and replay handling.
- Clarified v1 write behavior: calendar writes only, no implicit task-date mutation.
- Added integration coverage requirement for replay-safe apply behavior.

---

*Prepared for build-e2e Tech Spec checkpoint.*
