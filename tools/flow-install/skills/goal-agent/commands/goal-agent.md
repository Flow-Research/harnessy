---
description: Two-intelligence goal orchestrator — decompose, drive worker(s), verify, adapt, and persist runtime state
argument-hint: "run <goal-file> [--background] [--session <name>] | status [<run-id>] | list | resume <run-id> | approve <run-id> | learn | guard <run-id> --tool <name> --target <path> | record-outcome <run-id> --outcome <status> --pass-rate <0-1>"
---

# Command Contract: goal-agent

## Purpose

Achieve a user-defined goal by orchestrating a Claude Code worker through phased implementation with objective verification.

## Ownership

- Owner: julian
- Source of truth: `${AGENTS_SKILLS_ROOT}/goal-agent/`

## User Input

$ARGUMENTS

## Context

- Current directory: !`pwd`
- Git branch: !`git branch --show-current 2>/dev/null || echo "N/A"`

## Command Router

### `run <goal-file>`

Execute the full orchestration loop for a goal.

**Flags:**
- `--background` — Launch in a tmux session (requires tmux)
- `--session <name>` — Name for the tmux session (default: `goal-<run-id>`)
- `--max-iterations <N>` — Override max iterations from goal file (default: 10)
- `--budget <N>` — Override total budget from goal file (default: $10.00)

### `status [<run-id>]`

Show current state of a run. If no run-id, show the most recent run.

### `list`

List all runs in `.goal-agent/` with their status.

### `resume <run-id>`

Resume a paused or interrupted run from its last checkpoint.

### `approve <run-id>`

Approve or reject generated verification proposals persisted in run state.

### `learn`

Aggregate outcome records into `.goal-agent/.learning/registry.json`.

### `guard <run-id>`

Evaluate a proposed orchestrator action against the run's runtime policy.

**Required flags:**
- `--tool <tool-name>` — The tool being proposed (Write, Edit, Bash)
- `--target <path-or-command>` — The file path (for Write/Edit) or command string (for Bash)

**Returns:** JSON with `allowed: true|false` and `reason` explaining the decision.

### `record-outcome <run-id>`

Persist a run's outcome for cross-run learning.

**Required flags:**
- `--outcome <completed|failed|partial>` — The run's final status
- `--pass-rate <0.0-1.0>` — Fraction of verification checks that passed

**Optional flags:**
- `--strategy <label>` — Strategy label for learning aggregation (default: "default")
- `--failure-modes <modes>` — Comma-separated failure mode tags

---

## Execution Flow for `run`

### Step 0: Setup

Run the setup script to initialize:

```bash
goal-agent run "$GOAL_FILE" --setup-only
```

Read the JSON output. It provides:
- `run_id` — unique identifier for this run
- `worker_session_id` — UUID for the worker's persistent session
- `goal_file` — absolute path to the goal specification
- `state_dir` — path to `.goal-agent/<run-id>/`
- `constraints` — parsed from goal file: max_iterations, budget, model, allowed_tools

The setup script also writes:
- `identity.json` — on-disk orchestrator identity anchor
- `runtime-policy.json` — machine-enforced allowlist for orchestrator writes and shell command classes
- `prepared-goal.md` or `prepared-goals/` — mutable copies used for injected context or approved checks

If `--background` was specified, the script launches a tmux session with a deterministic supervisor (`background-runner`) that drives the orchestration via sequential `claude -p --resume` calls. The output includes `"action": "background"`, the `tmux_session` name, and commands to check status or attach. Report these to the user. The goal runs autonomously to completion — no further action needed from you.

### Step 1: Analyze Goal

Read the goal file thoroughly:

```bash
cat "$GOAL_FILE"
```

Identify and extract:
1. **Objective** — what must be true when done
2. **Constraints** — iterations, budget, model, tools
3. **Verification commands** — the commands that determine success (exit code 0 = pass)
4. **File checks** — files that must exist
5. **Context** — background info, architecture, conventions
6. **Approach hints** — user's guidance on methodology

### Step 2: Decompose into Phases

Think carefully about how to break the objective into 2-7 phases. Each phase should:
- Have a clear, verifiable deliverable
- Build on the previous phase's output
- Be achievable in a single worker call (with retries)

If the input is a meta-goal (`.meta.yaml`), decompose at the goal-graph level first and only then decompose each sub-goal into phases.

Write the phase plan:

```
# Phase Plan
## Phase 1: <name>
Deliverable: <what the worker should produce>
Output files: [<paths this phase is allowed to modify>]
Depends on: [<phase ids or empty>]
Verification: <how to check this phase succeeded>
Worker prompt strategy: <what to emphasize>

## Phase 2: <name>
...
```

Save to state directory: write the plan to `.goal-agent/<run-id>/plan.md`

### Step 3: Execute Phases

For each phase in the plan:

#### 3pre. Delegation Reinforcement Check

Before starting this phase, reinforce your orchestrator identity:

1. Re-read `.goal-agent/<run-id>/identity.json` — this is a compression-resistant anchor
2. Verify your role is `orchestrator` and review the `delegation_rules`
3. If you are about to write application code directly, STOP — craft a worker prompt instead

This step is critical for long runs where context compression may have dropped the SKILL.md instructions that define your role.

#### 3a. Craft the Worker Prompt

Build a focused prompt for THIS phase only. Structure:

```
## Task
[Specific thing to implement — one phase, not the whole goal]

## Context
[What has been done so far — list files created, what they contain]
[Current state of the working directory relevant to this phase]

## Expected Output
[What files to create/modify, what behavior to implement]
[Be specific about file names, function signatures, expected content]

## Constraints
[Language, framework, style constraints from the goal]
[Do NOT include constraints about budget or iterations — those are your concern, not the worker's]
```

#### 3b. Call the Worker

**Write the prompt to a file first**, then use the Agent tool to dispatch.

```
# Step 1: Write prompt to file
# (use the Write tool to write the prompt to .goal-agent/$RUN_ID/current-prompt.md)

# Step 2: Use the Agent tool to dispatch the worker
Agent(
  description: "<3-5 word summary of this phase>",
  prompt: "<contents of current-prompt.md>",
  subagent_type: "general-purpose",
  run_in_background: false  # true for parallel phases
)
```

The Agent tool runs within the same Claude Code session — no separate process, no permission prompts, full tool access. The worker result is returned directly.

For parallel phases, dispatch multiple Agent calls in a single message with `run_in_background: true`.

#### 3c. Evaluate the Worker's Output

After the worker returns:

1. **Parse the JSON response.** Extract the `result` field for the text output.
2. **Check the actual filesystem.** Read files the worker should have created or modified. Don't trust the worker's claims — verify.
3. **Run phase-specific verification** if defined in the plan.
4. **Decide:**
   - **Phase passed** → Mark complete, move to next phase
   - **Phase failed, retryable** → Craft a corrective prompt that includes the error/failure details. Retry (max 3 per phase).
   - **Phase failed, plan is wrong** → Re-decompose. Update plan.md. Restart from the adjusted phase.

#### 3d. Update State

After each phase attempt, update the state file `.goal-agent/<run-id>/state.json`:

```json
{
  "run_id": "<uuid>",
  "worker_session_id": "<uuid>",
  "goal_file": "<path>",
  "status": "running",
  "current_phase": 2,
  "total_phases": 4,
  "iteration": 5,
  "max_iterations": 10,
  "budget_used_estimate": 2.50,
  "budget_limit": 10.00,
  "phases": [
    {"name": "Phase 1", "status": "completed", "iterations": 1},
    {"name": "Phase 2", "status": "running", "iterations": 2},
    {"name": "Phase 3", "status": "pending"},
    {"name": "Phase 4", "status": "pending"}
  ],
  "started_at": "2026-03-29T10:00:00Z",
  "last_updated_at": "2026-03-29T10:15:00Z"
}
```

### Step 4: Final Verification

After all phases are complete, run EVERY verification command from the goal spec:

```bash
# For each command in the Verification section:
<command>
echo "EXIT_CODE: $?"
```

Also check all file checks:
```bash
test -f <file_path> && echo "EXISTS" || echo "MISSING"
```

Report each check's pass/fail status.

If ALL pass → goal is achieved. Proceed to Step 5.
If ANY fail → decide whether to add a correction phase or report partial completion.

### Step 4a: Auto-Verification Approval Gate

If `state.json.auto_verification.status` is `awaiting_approval`, do not continue execution silently.

- In foreground mode: present the proposals and wait for the user.
- In background mode: instruct the user to run `goal-agent approve <run-id>`.
- Persist approved checks in run state and `prepared-goal.md`, never in the source goal file.

### Step 4b: Parallel Dispatch Rule

You may dispatch phases concurrently only when all of the following are true:

1. Every phase in the group has `Depends on` satisfied.
2. Their `Output files` are disjoint.
3. The group size does not exceed `max_parallel_workers`.

If two phases modify the same file, serialize them. Same-file parallel edits are forbidden in v2.

### Step 5: Report and Cleanup

Write a completion report to `.goal-agent/<run-id>/report.md`:

```markdown
# Goal Agent Report

## Goal
<title from goal file>

## Result: <COMPLETED | PARTIAL | FAILED>

## Phases
| Phase | Status | Iterations |
|-------|--------|------------|
| Phase 1: <name> | completed | 1 |
| Phase 2: <name> | completed | 2 |
| ... | ... | ... |

## Verification Results
| Check | Result |
|-------|--------|
| `npm test` | PASS |
| `test -f src/feature.ts` | PASS |
| ... | ... |

## Statistics
- Total iterations: N
- Estimated budget used: $X.XX
- Duration: Xm Xs
- Plan revisions: N
```

Update state file with `status: "completed"` or `status: "failed"`.

Also persist an outcome record for learning:

```bash
goal-agent record-outcome "$RUN_ID" --outcome completed --strategy <strategy-label>
```

Capture trace:
```bash
python3 "${AGENTS_SKILLS_ROOT}/_shared/trace_capture.py" capture \
    --skill "goal-agent" --gate "goal_verification" --gate-type "quality" \
    --outcome "<approved|rejected>" --feedback "<summary of what happened>"
```

---

## Execution Flow for `status`

```bash
# Read state file
cat .goal-agent/<run-id>/state.json
```

Display: run ID, status, current phase, iteration count, verification results.

## Execution Flow for `list`

```bash
# List all run directories
ls -1 .goal-agent/ 2>/dev/null
```

For each, read `state.json` and display: run ID, goal title, status, last updated.

## Execution Flow for `resume`

1. Read the state file for the given run-id
2. Restore: worker_session_id, current phase, iteration count
3. Re-read the goal file and plan.md
4. Continue from the last incomplete phase

## Execution Flow for `approve`

```bash
goal-agent approve <run-id> --approve-all
```

This updates `.goal-agent/<run-id>/state.json` and regenerates `.goal-agent/<run-id>/prepared-goal.md`.

## Execution Flow for `learn`

```bash
goal-agent learn
```

This scans `.goal-agent/.learning/outcomes/*.json` and writes `.goal-agent/.learning/registry.json`.

## Execution Flow for `guard`

```bash
goal-agent guard <run-id> --tool <tool-name> --target <path-or-command>
```

The guard evaluates the proposed action against `runtime-policy.json`:
- For Write/Edit: checks if the target path matches `allowed_write_patterns`
- For Bash: checks if the command contains any `allowed_bash_markers`
- Also validates the tool is allowed in the current `orchestrator_state`

Returns JSON: `{"ok": true, "allowed": true|false, "reason": "...", "orchestrator_state": "..."}`

Use this before any orchestrator write/edit to non-state files. If blocked, delegate to the worker instead.

## Execution Flow for `record-outcome`

```bash
goal-agent record-outcome <run-id> --outcome <completed|failed|partial> --pass-rate <0.0-1.0>
```

This reads the run's state.json and persists a structured outcome record to `.goal-agent/.learning/outcomes/<run-id>.json`. The record includes decomposition strategy, phase timing, verification results, and failure modes. Used by the `learn` command to generate cross-run recommendations.

---

## Safety Rules

1. **Budget:** Track approximate spend. Assume each worker call costs roughly $0.10-0.50 depending on complexity. Stop if total estimate exceeds the budget limit.
2. **Iterations:** Each worker call counts as one iteration. Stop at max_iterations.
3. **Corruption check:** After each worker call, verify the working directory still has expected structure. If the worker deleted critical files, stop.
4. **Infinite loop prevention:** If the same verification fails with the same error 3 consecutive times, STOP. The approach is wrong. Report the failure.
5. **Scope creep prevention:** Only implement what the goal asks for. Do not add features, refactor, or "improve" beyond the specification.
6. **Delegation enforcement:** Do not modify application files directly as the orchestrator. If a runtime-policy wrapper blocks an action, treat that as authoritative.
7. **Context pressure control:** For goal chaining, inline only small upstream artifacts. Prefer summaries, file lists, or references for larger artifacts.

## Feedback Capture

After completion (success or failure), ask the user:
**"Any feedback on this goal-agent run? (skip to finish)"**

If provided:
```bash
python3 "${AGENTS_SKILLS_ROOT}/_shared/trace_capture.py" capture \
    --skill "goal-agent" --gate "run_retrospective" --gate-type "retrospective" \
    --outcome "approved" --feedback "<user's feedback>"
```
