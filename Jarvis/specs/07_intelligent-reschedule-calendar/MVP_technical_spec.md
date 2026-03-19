# MVP Technical Spec: Intelligent Reschedule + Calendar Mapping

## Goal

Add a new planning flow that can reorganize tasks and optionally map selected tasks to calendar time blocks, while preserving Jarvis' explicit approval model.

## Current Extension Points

- `src/jarvis/cli.py`: existing `suggest`, `apply`, and `rebalance` flows already support preview + apply.
- `src/jarvis/analyzer.py`: workload analysis currently works at date granularity; can be extended with capacity signals.
- `src/jarvis/models/task.py`: task has due date and priority but no duration/effort metadata.
- `src/jarvis/adapters/base.py`: backend protocol supports task CRUD; no calendar capability yet.
- `src/jarvis/context_reader.py` + `context/calendar.md`: user calendar intent can already be captured as text context.

## MVP Scope

### In Scope

1. New command: `jarvis reorganize` (date-level intelligent reorganizer).
2. New command: `jarvis calendar plan` (create calendar block plan from task candidates).
3. New command: `jarvis calendar apply` (apply approved plan to calendar provider).
4. Local plan persistence under `~/.jarvis/` with stable plan IDs.
5. Provider abstraction for calendar, implemented first with Google Workspace (`gws`).

### Out of Scope

- Two-way live sync from calendar edits back into tasks.
- Multi-provider calendar support in v1 (e.g. Outlook, Apple Calendar).
- Automatic continuous replanning daemon.

## Proposed Architecture

### 1) Models

Add new models:

- `TaskPlanningInput`: task + inferred duration + flexibility score.
- `CalendarBusySlot`: start/end + source.
- `PlannedBlock`: task_id + start/end + rationale.
- `SchedulePlan`: plan_id + horizon + tasks + blocks + warnings.

### 2) Services

- `planning_service.py`: produces date-level reorganize plan.
- `calendar_service.py`: provider-neutral free/busy + event create interface.
- `calendar_providers/gws_provider.py`: `gws` command wrapper.

### 3) Capability Gate

Extend adapter/service capability checks with optional calendar capability:

- no calendar capability -> `jarvis calendar *` commands fail with clear guidance.
- `jarvis reorganize` still works without calendar integration.

### 4) CLI Flow

- `jarvis reorganize --days 14 --dry-run`:
  - fetch tasks,
  - score urgency/load,
  - output move recommendations.
- `jarvis calendar plan --days 14 --max-blocks N --dry-run`:
  - fetch free/busy from provider,
  - map selected tasks into candidate slots,
  - save plan file.
- `jarvis calendar apply --plan <id>`:
  - apply event creation,
  - report success/fail per block,
  - persist apply status.

## Planning Heuristics (MVP)

1. Prioritize overdue/high-priority tasks first.
2. Respect weekdays and user constraints from context.
3. Avoid creating blocks shorter than minimum threshold.
4. Limit per-day cognitive load (task count + estimated duration).

## Data Persistence

Store under `~/.jarvis/plans/`:

- `<plan_id>.json` for generated plan,
- `<plan_id>.apply.json` for apply result and failures.

## Verification Strategy

1. Unit tests for slot matching and prioritization.
2. CLI tests for dry-run output stability.
3. Integration tests for provider command contract (mocked shell boundary, not scheduling core).
4. Regression tests to ensure existing `rebalance` and `suggest/apply` commands remain functional.

## Work Items

- WI-701: Add planning and calendar models.
- WI-702: Implement planning service for reorganize recommendations.
- WI-703: Add CLI `jarvis reorganize` command.
- WI-704: Implement provider-neutral calendar service.
- WI-705: Implement GWS provider adapter.
- WI-706: Add CLI `jarvis calendar plan` and `jarvis calendar apply`.
- WI-707: Persist plans and apply audit files.
- WI-708: Add tests for planner logic and CLI behavior.

## Acceptance Criteria

- User can generate reorganize recommendations with `--dry-run` and see rationale.
- User can generate a calendar plan and inspect it before apply.
- User can apply a plan and get deterministic success/failure report.
- Existing commands (`analyze`, `suggest`, `apply`, `rebalance`) still run unchanged.
