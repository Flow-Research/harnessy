---
description: Autonomous issue-flow runner with self-improving skill evolution loop
argument-hint: "<start|status|pause|resume|metrics|history>"
---

# Autoflow Command Specification

## Mission

Autonomously process GitHub issues through issue-flow, measure quality via a multiplicative composite metric, and improve skills when quality thresholds are breached. This is the autoresearch ratchet: run → measure → improve → evaluate → keep or revert → repeat.

## User Input

$ARGUMENTS

## Context

- Current directory: !`pwd`
- Git branch: !`git branch --show-current 2>/dev/null || echo "N/A"`
- Program file: !`cat program.md 2>/dev/null | head -5 || echo "No program.md found"`

## State Directory

All autoflow operational state lives per-project at `.jarvis/context/autoflow/`:

```
.jarvis/context/autoflow/
├── state.json            # Loop state: status, checkpoint, issues processed
├── queue.json            # Approved execution plan: waves, packets, dependencies, holdbacks
├── pool.json             # Concurrency pool state (if max_concurrent > 1)
├── runs.ndjson           # Run-by-run log with extended metrics
├── improvements.ndjson   # Improvement cycle log with ratchet decisions
└── ratchet_*.json        # Per-skill ratchet state: baseline, candidate, decision
```

This directory must be gitignored (runtime state, not source). Decision traces remain global at `~/.agents/traces/<skill>/traces.ndjson` (per-skill, cross-project).

Create `.jarvis/context/autoflow/` on first run if it doesn't exist.

## Command Router

### `start`

Begin the autonomous loop. Executes the full startup sequence:
1. Read `program.md`
2. Prompt for approval checkpoint (trust level)
3. Fetch and deep-inspect eligible issues
4. Build a dependency-aware execution plan against project strategy and architecture coherence rules
5. Present the proposed waves, packets, and holdbacks for human approval
6. Begin experiment loop on approved runnable issues

### `status`

Show current loop state: active issue, approval checkpoint, queue position, ratchet score, improvement history, pool state, next action.

### `pause`

Set the loop to pause after the current issue completes. Does not interrupt an active issue-flow run.

### `resume`

Resume from where the loop was paused. Re-read `program.md` for any updated configuration. Queue and checkpoint are preserved from the original `start`.

### `metrics`

Show aggregate quality metrics and ratchet score:

```bash
python3 "${AGENTS_SKILLS_ROOT}/_shared/ratchet.py" score --skill issue-flow --json
python3 "${AGENTS_SKILLS_ROOT}/_shared/ratchet.py" gates --skill issue-flow --json
python3 "${AGENTS_SKILLS_ROOT}/_shared/run_metrics.py" compute --skill issue-flow
```

### `history`

Show the run log from `.jarvis/context/autoflow/runs.ndjson`.

---

## Startup Sequence

The `start` command executes these steps before entering the experiment loop.

### Startup Step 1: Load Program

Read `program.md` from the repository root. Parse all sections:
- `Optimization Metric` → composite formula, hard constraints, significance threshold
- `Time Budgets` → max time per run, max time per improvement
- `Approval Checkpoint` → default preset, max_autonomy
- `Issue Source` → label filter, skip labels
- `Quality Standards` → thresholds for refinement loops, first-pass rate, max failures
- `Skill Improvement Rules` → auto-accept criteria, human review triggers, evaluation window
- `Escalation Policy` → failure limits, revert triggers, pause conditions
- `Loop Cadence` → concurrency, improvement frequency, drain and stop conditions

If `program.md` is missing, HARD STOP.

### Startup Step 2: Approval Checkpoint

Ask the user to choose their approval checkpoint (trust level):

```
What's your approval checkpoint for this session?

  after-brainstorm  — Human reviews brainstorm, then autonomous
  after-design      — Human reviews design, then autonomous
  after-spec        — Human reviews tech spec, then autonomous (default)
  after-scope       — Human reviews execution scope, then autonomous
  after-qa          — Autonomous through QA, human reviews before PR
  after-pr          — Autonomous through PR, human does final acceptance only
  full-auto         — No human gates (quality gates only)
  all-gates         — Every human gate pauses (safest)
```

- Use the default from `program.md` if set, show it as "(default)"
- If `max_autonomy` is set in `program.md`, reject presets beyond that level
- `full-auto` requires explicit confirmation: "Full auto mode skips ALL human gates. Quality gates still enforce. Confirm?"

Store the choice in `.jarvis/context/autoflow/state.json` as `approval_checkpoint`.

**Checkpoint-to-phase mapping:**

```
after-brainstorm → Phase 1
after-design     → Phase 5
after-spec       → Phase 7
after-scope      → Phase 8
after-qa         → Phase 13
after-pr         → Phase 15
full-auto        → Phase 99 (no human gates)
all-gates        → Phase -1 (all human gates active)
```

### Startup Step 3: Fetch Eligible Issues (Deep Inspection)

Fetch all eligible issues with full content — not just titles:

```bash
gh issue list --label "<label from program.md>" --state open \
    --json number,title,body,labels,assignees,createdAt,milestone,comments \
    --jq '[.[] | select(.labels | map(.name) | all(. != "blocked" and . != "wontfix" and . != "duplicate"))]'
```

Read the **full body and comments** of each issue. This is essential for prioritization.

If no eligible issues found, PAUSE and report.

### Startup Step 4: Load Project Strategy Context

Read from `.jarvis/context/`:
- `status.md` — current project status, active priorities
- `roadmap.md` — upcoming milestones, strategic direction
- `docs/strategy/README.md` — strategic context (if exists)
- Active specs in `.jarvis/context/specs/` — ongoing epic work

These provide the strategic lens for prioritization.

### Startup Step 5: Build Execution Plan

For each eligible issue, assess:

| Factor | Signal |
|--------|--------|
| **Strategic alignment** | Does it advance current roadmap priorities? |
| **Dependency order** | Does it block or depend on other eligible issues? |
| **Architecture overlap** | Does it touch the same models, contracts, schema, abstractions, or auth boundaries as another issue? |
| **Readiness** | Well-specified? Clear acceptance criteria? No open questions? |
| **Complexity estimate** | Bug fix vs. feature — affects time budget and risk |
| **Risk** | Does it touch high blast_radius areas? |

Use a hybrid dependency model:
- explicit issue links and issue-body references first
- conservative inferred dependencies when issues overlap on shared domain models, API contracts, schema, migrations, auth, shared abstractions, or verification surfaces

Autoflow must then build:
- **serial foundation issues** — prerequisites for shared contracts or risky overlapping work
- **parallel packets** — bounded groups of issues that are safe to run together
- **holdbacks** — issues blocked by unresolved dependencies, ambiguity, or high coherence risk

Each packet must include one-line rationale covering why it is safe to parallelize.

### Startup Step 6: Present Execution Plan for Approval

Present the dependency-aware execution plan to the human:

```
Proposed execution plan (N eligible issues):

Wave 0 — Serial foundation
  #42 — Add input validation to registration flow
    Why first: Establishes shared validation contract used by #48.

Wave 1 — Parallel packet A
  #45 — Fix auth redirect on expired sessions
    Why parallel-safe: Separate user-facing bug path, no shared contract dependency.
  #51 — Improve admin empty-state copy
    Why parallel-safe: UI-only change, isolated verification path.

Wave 2 — Dependent follow-up
  #48 — Registration flow end-to-end
    Why later: Depends on Wave 0 validation contract.

Holdbacks
  #57 — Billing sync edge cases
    Why held: Touches shared finance workflow and requires human policy judgment.

Approval checkpoint: after-spec
Max concurrent active issues: 3

Approve this plan? (y / adjust waves / adjust concurrency / skip issues)
```

The human can:
- **Approve** (`y`) — process using this plan
- **Adjust waves** — change sequencing or packetization
- **Adjust concurrency** — lower or raise bounded parallelism for this session
- **Skip** — remove specific issues from this session

Store the approved execution plan in `.jarvis/context/autoflow/queue.json`:

```json
{
  "session_id": "session_<YYYYMMDD>_<NNN>",
  "approved_at": "<ISO 8601>",
  "approval_checkpoint": "after-spec",
  "max_concurrent": 3,
  "waves": [
    {
      "id": "wave_0",
      "mode": "serial",
      "reason": "foundation",
      "issues": [
        { "number": 42, "title": "...", "plan_reason": "Defines shared validation contract" }
      ]
    },
    {
      "id": "wave_1",
      "mode": "parallel",
      "reason": "independent packet",
      "issues": [
        { "number": 45, "title": "...", "plan_reason": "Separate bugfix path" },
        { "number": 51, "title": "...", "plan_reason": "UI-only isolated work" }
      ]
    }
  ],
  "holdbacks": [
    { "number": 57, "title": "...", "holdback_reason": "Needs human policy judgment" }
  ],
  "dependency_edges": [
    { "from": 42, "to": 48, "type": "explicit", "reason": "Validation contract prerequisite" }
  ],
  "skipped": [51],
  "context_files_read": ["status.md", "roadmap.md"]
}
```

---

## State Machine

After the startup sequence completes, the experiment loop begins.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         AUTOFLOW STATE MACHINE                          │
│                                                                         │
│  STARTUP ──→ LOAD_PROGRAM ──→ NEXT_RUNNABLE ──→ CHECK_DRAIN_STATE      │
│                                    │                    │               │
│                              (none runnable)      (no runnable work)    │
│                                    ↓                    ↓               │
│                                  PAUSE               PAUSE              │
│                                                                         │
│  CHECK_LIMITS ──→ RUN_ISSUE ──→ CAPTURE_METRICS ──→ EVALUATE_QUALITY   │
│                       │                                   │             │
│                  (human gate,         ┌───────────────────┤             │
│                   pool mode)          │            (threshold breach)    │
│                       ↓               ↓                   ↓             │
│                    WAITING          LOOP           IMPROVEMENT_CYCLE    │
│                                      ↓                   │             │
│                              LOAD_PROGRAM          ┌─────┘             │
│                                                    ↓                    │
│  IMPROVEMENT_CYCLE:                                                     │
│    SNAPSHOT ──→ RUN_SKILL_IMPROVE ──→ EVALUATION_WINDOW                │
│                                            │                            │
│                                      (window complete)                  │
│                                            ↓                            │
│                                      RATCHET_DECIDE                    │
│                                       ┌────┴────┐                      │
│                                      KEEP    REVERT                    │
│                                       └────┬────┘                      │
│                                            ↓                            │
│                                          LOOP                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### State Transitions

| From | To | Condition |
|------|----|-----------|
| STARTUP | LOAD_PROGRAM | Startup sequence complete (queue approved) |
| LOAD_PROGRAM | NEXT_RUNNABLE | `program.md` parsed successfully |
| LOAD_PROGRAM | HARD_STOP | `program.md` not found |
| NEXT_RUNNABLE | CHECK_DRAIN_STATE | Next approved runnable issue available |
| NEXT_RUNNABLE | PAUSE | No runnable issues remain |
| CHECK_DRAIN_STATE | RUN_ISSUE | Runnable issue exists within approved concurrency/wave constraints |
| CHECK_DRAIN_STATE | PAUSE | All remaining issues are waiting_human, held back, escalated, or completed |
| RUN_ISSUE | CAPTURE_METRICS | Issue-flow completed or failed |
| RUN_ISSUE | WAITING | Issue paused at human gate (pool mode) |
| CAPTURE_METRICS | EVALUATE_QUALITY | Metrics captured |
| EVALUATE_QUALITY | IMPROVEMENT_CYCLE | Threshold breached |
| EVALUATE_QUALITY | LOOP | Within thresholds |
| IMPROVEMENT_CYCLE | LOOP | Improvement cycle complete |
| LOOP | LOAD_PROGRAM | Re-read program.md, continue |
| PAUSE | LOAD_PROGRAM | `resume` command received |

---

## The Experiment Loop

### State: LOAD_PROGRAM

Re-read `program.md` on every iteration (human may have updated thresholds). Do NOT re-plan silently — the approved execution plan from startup remains the source of truth unless a human explicitly changes it.

### State: NEXT_RUNNABLE

Select the next issue from the approved execution plan that is both:
- unstarted or resumable
- not blocked by an incomplete dependency edge
- allowed by the current wave/packet constraints

If no runnable issue exists, transition to PAUSE.

### State: CHECK_DRAIN_STATE

Before dispatch, verify whether the remaining issues are:
- completed
- escalated
- held_back
- waiting_human

If every remaining issue is in one of those states and no runnable issue remains, transition to PAUSE and report the waiting-human review queue.

### State: RUN_ISSUE

Record the start time.

Invoke issue-flow on the next queued issue:

```
/issue-flow issue <number>
```

**Approval checkpoint enforcement**: Pass the `approval_checkpoint` to issue-flow. At each human gate in issue-flow:

1. Look up the gate's phase number:
   ```
   brainstorm_approval       → Phase 1
   issue_append_approval     → Phase 1
   prd_approval              → Phase 3
   design_approval           → Phase 5
   tech_spec_approval        → Phase 7
   execution_scope_approval  → Phase 8
   final_acceptance          → Phase 16
   ```

2. If gate phase < checkpoint phase → **auto-approve**:
   ```bash
   python3 "${AGENTS_SKILLS_ROOT}/_shared/trace_capture.py" capture \
       --skill "issue-flow" \
       --gate "<gate_name>" --gate-type "human-bypassed" \
       --outcome "auto-approved" --refinement-loops 0 \
       --feedback "Auto-approved: checkpoint is <preset>, gate before checkpoint"
   ```
   Continue to next phase without pausing.

3. If gate phase >= checkpoint phase → **pause for human review** (normal behavior).

4. Quality gates are NEVER bypassed regardless of checkpoint.

**Time budget enforcement**: At each phase transition, check elapsed time:
```
if elapsed > time_budget_seconds from program.md:
    mark run as "timed_out", capture partial metrics, transition to CAPTURE_METRICS
```

**Human gate handling in pool mode**:
- If `max_concurrent == 1`: wait for user input at active human gates
- If `max_concurrent > 1`: move issue to WAITING state, then continue dispatching other approved runnable issues only if their dependencies and wave constraints remain satisfied

### Test-First Integration

Before implementation begins (after specs are approved at Phase 8), generate tests from specifications:

1. **Generate regression tests from specs**: `/spec-to-regression` — Creates test cases from PRD acceptance criteria and tech spec contracts
2. **Generate API integration tests**: `/api-integration-codegen` — Creates API test scaffolds from tech spec endpoint definitions  
3. **Generate browser tests**: `/browser-integration-codegen` — Creates Playwright tests from design spec routes and UX flows
4. All generated tests MUST fail initially (nothing implemented yet) — this confirms test validity
5. Implementation phase (Phase 9) then writes code to make these tests pass

Test-first is mandatory when the pipeline trigger launches autoflow. Human-initiated autoflow sessions may skip test generation if the issue is a simple bug fix.

### Testing Skills Reference

The following testing skills are available for pipeline use:
- `/spec-to-regression` — Generate regression test cases from approved specifications
- `/api-integration-codegen` — Generate API integration test scaffolds
- `/browser-integration-codegen` — Generate Playwright browser tests from design specs
- `/test-quality-validator` — Detect false-green tests and validate coverage quality
- `/browser-qa` — Playwright-driven UI/UX validation walkthrough

### State: CAPTURE_METRICS

After issue-flow completes (or fails or times out), compute metrics:

```bash
python3 "${AGENTS_SKILLS_ROOT}/_shared/run_metrics.py" compute \
    --skill issue-flow --last <number_of_traces_from_this_run> --json
```

Capture a run completion trace:

```bash
python3 "${AGENTS_SKILLS_ROOT}/_shared/trace_capture.py" capture \
    --skill "autoflow" \
    --gate "run_completion" --gate-type "quality" \
    --outcome "<completed|failed|escalated|timed_out>" \
    --issue-number <N> --project <project>
```

Append to `.jarvis/context/autoflow/runs.ndjson`:

```json
{
  "run_id": "run_<YYYYMMDD>_<NNN>",
  "timestamp": "<ISO 8601>",
  "issue_number": 123,
  "issue_title": "<title>",
  "outcome": "completed|failed|escalated|timed_out",
  "phases_completed": 17,
  "total_refinement_loops": 3,
  "first_pass_gates": 15,
  "total_gates": 19,
  "duration_seconds": 1800,
  "skill_version": "<version from issue-flow manifest>",
  "improvement_triggered": false,
  "human_gates_triggered": 2,
  "human_gates_total": 7,
  "human_gates_bypassed": 5,
  "tests_passed": 15,
  "tests_total": 18,
  "regression_detected": false,
  "catastrophic_failure": false,
  "approval_checkpoint": "after-spec"
}
```

### State: EVALUATE_QUALITY

After **every completed issue**, evaluate whether improvement is needed:

1. If any gate has `avg_refinement_loops > max_loops_threshold` → flag for improvement
2. If `first_pass_rate < min_first_pass_rate` → flag for escalation
3. If this is the Nth consecutive failure → escalate per policy

Also compute the ratchet score:

```bash
python3 "${AGENTS_SKILLS_ROOT}/_shared/ratchet.py" score --skill issue-flow --json
python3 "${AGENTS_SKILLS_ROOT}/_shared/ratchet.py" gates --skill issue-flow --json
```

**Escalation**: When triggered:
- Comment on the GitHub issue: "Autoflow escalation: [reason]. Human review requested."
- Capture trace with gate "escalation_review"
- If escalation policy says "pause" → set loop to PAUSE state

If improvement flagged → transition to IMPROVEMENT_CYCLE.
Otherwise → transition to LOOP.

### State: IMPROVEMENT_CYCLE

Triggered after any completed issue where a gate exceeds the refinement threshold (checked every issue, not on a cadence).

#### Sub-state: SNAPSHOT

```bash
python3 "${AGENTS_SKILLS_ROOT}/_shared/ratchet.py" snapshot --skill issue-flow
```

Creates a git tag and records baseline score.

#### Sub-state: RUN_SKILL_IMPROVE

Record improvement start time.

```
/skill-improve issue-flow
```

**Time budget**: If elapsed exceeds `max_time_per_improvement` from program.md, abort and continue with unmodified skills.

Auto-accept rules from `program.md` apply:
- 3+ agreeing traces, additive change, medium or lower blast_radius → auto-accept
- Otherwise → pause for human review

#### Sub-state: EVALUATION_WINDOW

Process the next N approved runnable issues from the execution plan (evaluation window from program.md, default 3) with the improved skill. Normal RUN_ISSUE → CAPTURE_METRICS flow.

#### Sub-state: RATCHET_DECIDE

```bash
python3 "${AGENTS_SKILLS_ROOT}/_shared/ratchet.py" evaluate --skill issue-flow --window <N> --json
python3 "${AGENTS_SKILLS_ROOT}/_shared/ratchet.py" decide --skill issue-flow --json
```

Decision logic:
1. Hard constraint gate fails → **REVERT**
2. ΔS > 0.02 → **KEEP**
3. ΔS < -0.02 → **REVERT**
4. |ΔS| ≤ 0.02 → **KEEP** (no regression)

If the ratchet decision is **KEEP**, run descriptive attribution as a post-decision hook:

```bash
python3 "${AGENTS_SKILLS_ROOT}/_shared/attribute.py" compute --skill issue-flow --json
```

This writes:
- `~/.agents/traces/issue-flow/attributions.ndjson`
- `~/.agents/traces/issue-flow/component_index.json`

The attribution output is descriptive only. It summarizes which changed components were associated with observed per-gate deltas after the accepted improvement. It does not claim causal attribution.

Record to `.jarvis/context/autoflow/improvements.ndjson`:

```json
{
  "cycle_id": "cycle_<YYYYMMDD>_<NNN>",
  "timestamp": "<ISO 8601>",
  "skill": "issue-flow",
  "triggered_by_issue": 42,
  "metrics_before": { "score": 0.72, "f": 0.8, "p": 0.7, "q": 0.75, "r": 0.3 },
  "metrics_after": { "score": 0.76, "f": 0.85, "p": 0.75, "q": 0.78, "r": 0.25 },
  "delta": 0.04,
  "decision": "keep|revert",
  "reason": "<from ratchet.py>",
  "improvements_proposed": 2,
  "improvements_accepted": 1,
  "gates_passed": true
}
```

### State: LOOP

Return to LOAD_PROGRAM. Re-read `program.md`, select the next runnable issue from the approved plan, continue.

---

## Pool Protocol (Throughput)

When `max_concurrent > 1` in `program.md`, autoflow runs a bounded concurrency pool against the approved execution plan.

### Pool State

Tracked in `.jarvis/context/autoflow/pool.json`:

```json
{
  "max_concurrent": 3,
  "waves": [
    { "id": "wave_0", "mode": "serial", "issues": [42], "status": "active" },
    { "id": "wave_1", "mode": "parallel", "issues": [45, 51], "status": "pending" }
  ],
  "active": [
    { "issue_number": 42, "status": "running", "worktree": "../project-worktrees/42_feature", "started_at": "..." },
    { "issue_number": 57, "status": "waiting_human", "worktree": "../project-worktrees/57_fix", "gate": "prd_approval" }
  ],
  "holdbacks": [
    { "issue_number": 48, "reason": "blocked by #42" }
  ],
  "completed_this_session": 5
}
```

### Pool Rules

1. **Dispatch**: If `active.length < max_concurrent` and the approved plan has a runnable issue, start it in its own worktree
2. **Human gate at checkpoint**: When an issue hits an active human gate (at or after checkpoint), move it to `waiting_human` and continue only with other runnable issues from the approved plan
3. **Completion**: When a `waiting_human` issue gets approval, it resumes
4. **Wave discipline**: Do not start a later-wave issue while its upstream foundation issue remains unresolved unless the approved plan explicitly allows it
5. **Architecture coherence bias**: If multiple issues overlap on shared models, schema, auth, or abstractions, default to serial unless the approved plan explicitly marks the packet parallel-safe
6. **Improvement cycles are SERIAL**: No new issues dispatched during improvement
7. **Worktree isolation**: Each issue gets its own worktree

---

## State Tracking

`.jarvis/context/autoflow/state.json`:

```json
{
  "status": "running|paused|stopped",
  "session_id": "session_20260328_001",
  "session_start": "<ISO 8601>",
  "approval_checkpoint": "after-spec",
  "issues_processed": 5,
  "current_issue": null,
  "consecutive_failures": 0,
  "paused_reason": null,
  "current_ratchet_score": 0.76,
  "ratchet_trend": [0.68, 0.72, 0.74, 0.76]
}
```

---

## Hard Stop Conditions

- `program.md` not found
- GitHub CLI not authenticated
- Escalation policy triggered a full stop
- Unrecoverable git state (worktree corruption, merge conflicts)
- Hard constraint gate failure during evaluation

---

## Output Contract

For `start`: startup sequence output (checkpoint, dependency-aware execution plan, approval), then each issue as it begins/completes with ratchet score.
For `status`: current state, checkpoint, queue position, ratchet score, pool state.
For `metrics`: ratchet score breakdown + hard gate status + legacy quality metrics.
For `history`: formatted run log with outcomes, ratchet scores, improvement decisions.

---

## Pipeline Evaluation Criteria

When autoflow processes an issue through the pipeline, "done" means ALL of the following:

1. **All generated tests pass** — Unit, integration, API, and Playwright tests
2. **Test quality validated** — `/test-quality-validator` confirms no false-greens
3. **Ratchet score stable** — ΔS ≥ -0.02 (no quality regression)
4. **Hard constraints pass** — catastrophic_failure=0, regression_detected≤0.1
5. **Browser validation passes** — `/browser-qa` confirms UI/UX correctness
6. **CI pipeline passes** — All GitHub Actions checks green
7. **PR is clean** — No merge conflicts, follows PR template

If any criterion fails, the pipeline notifies the user with:
- Which criterion failed
- Specific error details
- Suggested remediation steps

## Safety Rules

1. Never dispatch work outside the human-approved execution plan.
2. Never auto-accept skill improvements for high blast_radius skills.
3. Never bypass quality gates — only human gates can be bypassed via approval checkpoint.
4. Never modify evaluation infrastructure (`_shared/*.py`, `_shared/*.md`).
5. Never modify `program.md` — it is the human control surface.
6. Always capture traces for every decision including bypassed gates — this is the audit trail.
7. If in doubt about any decision, escalate rather than proceed.
8. Always check hard constraint gates before keeping an improvement.
9. Never allow "pending_evaluation" state — every ratchet cycle ends with binary keep/revert.
10. Enforce time budgets — runs exceeding budget are timed_out.
11. Respect `max_autonomy` from program.md — never allow a checkpoint beyond this level.
12. `human-bypassed` traces do not count as "human rescue" in the ratchet `h` variable.
13. Prefer serial foundation-first sequencing whenever shared models, schema, auth, or abstractions would otherwise drift.
14. Use parallel packets only when the approved plan explicitly marks them safe and coherent.
