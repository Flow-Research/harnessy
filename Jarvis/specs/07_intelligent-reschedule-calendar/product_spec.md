# Product Specification: Intelligent Reschedule + Calendar Mapping

> **Epic:** 07_intelligent-reschedule-calendar
> **Version:** 1.0
> **Created:** 2026-03-06
> **Status:** Draft for PRD checkpoint review

---

## 1. Executive Summary

### Product Name
Jarvis Intelligent Reschedule + Calendar Mapping

### Vision Statement
Extend Jarvis from date-level task movement into a practical execution planner that protects deep work, keeps deadlines safe, and turns prioritized tasks into explicit calendar blocks with user approval.

### One-Liner
Jarvis should not just move due dates; it should propose when focused work actually happens.

### Problem Statement
Current Jarvis can `analyze`, `suggest`, and `rebalance` tasks, but users still manually do the hardest part: translating tasks into realistic, conflict-free calendar time.

### Proposed Solution
Add a planning flow that:

1. Reorganizes tasks with stronger optimization logic.
2. Estimates effort from task content and context.
3. Maps selected tasks into free calendar slots.
4. Requires explicit preview/confirmation before writes.

---

## 2. Goals and Objectives

### Primary Goals

| Goal | Description | Success Metric |
|------|-------------|----------------|
| Protect Deep Work | Preserve high-quality focus windows before filling low-value work | Planned schedules include dedicated uninterrupted focus blocks |
| Deadline Safety | Never place plans that cause deadline misses | No overdue tasks introduced by planner |
| Balanced Load | Reduce daily workload spikes | Daily variance decreases vs baseline |
| User Trust | Keep user in control with review gates | 100% of calendar writes require explicit confirmation |

### Secondary Goals

| Goal | Description |
|------|-------------|
| Explainability | Every move/block includes rationale |
| Adapter Compatibility | Preserve adapter-first architecture |
| Extensibility | Add calendar provider abstraction for future providers |

### Non-Goals (v1)

- Continuous autonomous replanning daemon
- Two-way sync from external calendar edits back into task backend
- Multi-provider calendar support in first release (Google first)
- Perfect AI duration estimation for all domains

---

## 3. User Personas

### Persona 1: Solo Builder (Primary)

Needs protected maker time and predictable execution from a messy backlog.

**Core need:** "Plan my week like a real calendar, not just a list of due dates."

### Persona 2: Operator/Manager (Secondary)

Handles many short tasks and meetings; needs balancing and deadline integrity.

**Core need:** "Keep me on track without overbooking my day."

### Persona 3: Power User of Jarvis (Secondary)

Already uses `analyze/suggest/rebalance`; wants an upgraded workflow without losing control.

**Core need:** "Give me smarter plans, but let me approve everything."

---

## 4. Product Principles

1. **Deep-work-first optimization**: optimize for uninterrupted focus first.
2. **Hard deadline constraint**: suggestions must preserve deliverability.
3. **Balanced distribution**: avoid concentration of heavy work on single days.
4. **Explain every decision**: always include machine rationale.
5. **No silent writes**: preview + confirm is mandatory before apply.

---

## 5. User Stories and Requirements

### US-01: Intelligent Reorganization
**As a** Jarvis user
**I want** `jarvis reorganize` to propose improved task placement
**So that** my schedule preserves deep work and avoids overload

**Acceptance Criteria:**
- [ ] `jarvis reorganize --days N --dry-run` outputs ordered recommendations
- [ ] Recommendations include rationale (deep work / deadline / balancing)
- [ ] Existing immovable semantics are respected (`bar_movement`, ongoing constraints)
- [ ] No write occurs in dry-run mode

**Priority:** P0

---

### US-02: Content-Aware Effort Estimation
**As a** user
**I want** duration estimates inferred from task content/context
**So that** slotting decisions are realistic

**Acceptance Criteria:**
- [ ] Estimator uses title + description (+ optional context files)
- [ ] Estimation outputs deterministic duration bands for v1
- [ ] Estimates are visible in plan preview
- [ ] User can override inferred duration before apply (v1 minimal override path)

**Priority:** P0

---

### US-03: Calendar Plan Generation
**As a** user
**I want** Jarvis to map selected tasks to free calendar slots
**So that** my plan is execution-ready

**Acceptance Criteria:**
- [ ] `jarvis calendar plan --days N --dry-run` generates a plan artifact
- [ ] Plan avoids conflicting existing events
- [ ] Plan enforces minimum block size and work-hour constraints
- [ ] Plan shows unplaced tasks with reasons

**Priority:** P0

---

### US-04: Explicit Apply Gate
**As a** user
**I want** to approve plan writes explicitly
**So that** Jarvis never changes my calendar unexpectedly

**Acceptance Criteria:**
- [ ] `jarvis calendar apply --plan <id>` requires confirmation
- [ ] Apply reports per-item success/failure
- [ ] Failed writes are recorded in apply artifact
- [ ] No hidden background writes

**Priority:** P0

---

### US-05: Provider-Aware Integration
**As a** maintainer
**I want** calendar integration behind provider abstraction
**So that** additional providers can be added without rewriting core planning

**Acceptance Criteria:**
- [ ] Calendar provider interface is defined
- [ ] First implementation works with Google Workspace CLI auth/session
- [ ] Clear capability error for users without provider configuration

**Priority:** P1

---

## 6. Functional Requirements

### FR-01: New CLI Commands

| Command | Purpose | Required Flags |
|---------|---------|----------------|
| `jarvis reorganize` | Date-level intelligent schedule recommendations | `--days`, `--dry-run` |
| `jarvis calendar plan` | Convert task candidates into proposed calendar blocks | `--days`, `--dry-run` |
| `jarvis calendar apply` | Apply selected plan to calendar provider | `--plan` |

### FR-02: Planning Model Requirements

- Planner SHALL rank tasks using deep-work-first priority.
- Planner SHALL enforce deadline feasibility checks.
- Planner SHALL include balancing penalty for overloaded days.
- Planner SHALL output auditable rationale per recommendation.

### FR-03: Calendar Mapping Requirements

- Mapper SHALL fetch free/busy from active calendar provider.
- Mapper SHALL avoid overlap with existing events.
- Mapper SHALL schedule only within configured planning window.
- Mapper SHALL produce a persisted plan artifact with stable ID.

### FR-04: Apply & Audit Requirements

- Apply SHALL require confirmation.
- Apply SHALL return deterministic result summary.
- Apply SHALL persist result artifact for traceability.

### FR-05: Backward Compatibility

- Existing `analyze/suggest/apply/rebalance` commands SHALL remain functional.
- Existing backend adapter operations SHALL remain unchanged for task and journal flows.

### FR-06: Plan/Apply Consistency Contract

- Calendar apply SHALL be idempotent per `plan_id` (same plan cannot silently double-create events).
- V1 calendar apply SHALL NOT mutate task due dates automatically; task backend changes remain explicit and separate.
- Each planned block SHALL carry a stable correlation key to support audit and retry behavior.

---

## 7. Non-Functional Requirements

- **Safety:** no silent calendar writes.
- **Reliability:** partial failures produce explicit itemized report.
- **Performance:** planning for 14-day horizon should complete within interactive CLI expectations.
- **Transparency:** generated plans and apply results are inspectable local artifacts.

---

## 8. Edge Cases and Failure Modes

- No free slots available in horizon -> return unplaced tasks with reasons.
- Ambiguous or missing task descriptions -> fallback estimate band.
- Provider unavailable/auth expired -> clear actionable error.
- Partial write failure -> continue best effort, report failed items.
- Re-running apply on same plan -> detect prior applied blocks and skip or report as already applied.

---

## 9. Metrics and Success Criteria

### Product Metrics

- % of planned tasks that remain within deadline window.
- Daily load variance before vs after reorganize.
- % of users accepting generated plans without major edits.

### Quality Metrics

- Planner unit test pass rate: 100%.
- Critical regressions in existing scheduling commands: 0.
- Calendar apply error visibility: 100% itemized.

---

## 10. Rollout Plan (MVP)

1. Implement `reorganize` planner command and model.
2. Add plan persistence and explainability output.
3. Add calendar provider abstraction.
4. Integrate Google Workspace provider.
5. Add `calendar plan` and `calendar apply` commands.
6. Run regression tests for existing commands.

---

## 11. Open Questions (to resolve in technical spec)

1. Duration override UX: inline prompt vs flag-based override file.
2. Default work-hour boundaries source: context file vs config schema.
3. Retry policy for provider write failures.

---

## 12. Iteration Notes

### Iteration 2 Refinements (2026-03-06)

- Added explicit idempotency requirement for `calendar apply` by `plan_id`.
- Added consistency contract to avoid hidden task-backend mutations in v1.
- Added replay edge case for repeated plan apply attempts.

---

*Created for build-e2e Phase 2 checkpoint.*
