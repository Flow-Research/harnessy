# Brainstorm: Intelligent Reschedule + Calendar Mapping

## Problem

Jarvis currently rebalances due dates but does not convert tasks into real execution windows.
Users still manually translate task lists into calendar blocks.

## Product Direction

Evolve Jarvis into an execution planner that does two connected jobs:

1. Reorganize tasks intelligently.
2. Map tasks into available calendar blocks.

## Prioritized Optimization Objectives

The optimization stack for v1 is:

1. **Protect deep work first** (primary objective).
2. **Never miss deadlines** (hard constraint).
3. **Distribute workload evenly by day** (secondary objective).

This means Jarvis should avoid fragmenting focus windows, while still respecting due dates and preventing overloaded days.

## Scheduling Strategy (v1)

Default behavior should be **estimate + autoslot**:

- Jarvis infers expected task duration and effort.
- Estimation uses task content/context, not only title.
- Slotting uses calendar free/busy + context constraints.

## Non-Negotiable Guardrails

- **Always preview + confirm** before any calendar writes.
- No silent writes to calendar or task backend.
- Explain why each recommendation/block is proposed.
- Respect immovable tasks and fixed commitments.

## Candidate Command Surface

- `jarvis reorganize --days 14 --dry-run`
- `jarvis calendar plan --days 14 --dry-run`
- `jarvis calendar apply --plan <id>`

## Architecture Alignment

The feature should extend current extension points without breaking existing flows:

- `src/jarvis/cli.py` (`suggest`, `apply`, `rebalance`)
- `src/jarvis/analyzer.py` (workload model)
- `src/jarvis/models/task.py` (task metadata and moveability)
- `src/jarvis/adapters/base.py` (capabilities/contracts)
- `context/calendar.md` + context loader inputs

## Risks to Manage Early

- Bad duration estimates can cause overbooking.
- Partial apply failures can desync task dates and calendar events.
- Added planning complexity can reduce trust if rationale is opaque.

## MVP Acceptance Shape

v1 is successful when:

1. Jarvis reorganizes tasks with explicit deep-work protection.
2. Jarvis produces a calendar plan from inferred task effort.
3. User reviews plan before any writes.
4. Apply flow gives deterministic per-item success/failure report.

## Review Gate

User requested a document review checkpoint before proceeding to PRD.
