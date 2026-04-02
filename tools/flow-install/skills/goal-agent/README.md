# Goal Agent

A two-intelligence orchestrator that decomposes goals into phases and drives a separate Claude Code worker to implement each one. You define the goal, the agent handles decomposition, execution, verification, and adaptation.

`flow-install` manages the goal-agent runtime dependency for meta-goal parsing by installing `PyYAML` automatically when the skill is installed or refreshed.

## How it works

```
You write a goal file
    -> Orchestrator reads it, breaks it into phases
        -> Worker (Claude Code -p) implements each phase
            -> Orchestrator verifies results, adapts if needed
                -> Repeat until all verification passes
```

The orchestrator and worker are separate Claude Code instances. The orchestrator reasons about strategy; the worker writes code. Both run in the same working directory.

## Quick start

```bash
# 1. Write a goal file (see format below)
# 2. Run it
/goal-agent run my-goal.md

# Or run in the background (tmux)
/goal-agent run my-goal.md --background
```

## Commands

### `run <goal-file>`

Execute the full orchestration loop.

```bash
/goal-agent run goal.md                          # foreground
/goal-agent run goal.md --background             # background (tmux)
/goal-agent run goal.md --background --session x  # custom tmux session name
/goal-agent run goal.md --max-iterations 20      # override max iterations
/goal-agent run goal.md --budget 15.00           # override budget cap
/goal-agent run goal.md --dry-run                # validate and print plan, no execution
```

Supports both normal markdown goals and `.meta.yaml` goal chains.

### `status [<run-id>]`

Show current state of a run. Defaults to the most recent run if no ID given.

```bash
/goal-agent status
/goal-agent status 20260329-100445-392cc285
```

### `list`

List all runs with their status.

```bash
/goal-agent list
```

### `resume <run-id>`

Resume a paused or interrupted run from its last checkpoint.

```bash
/goal-agent resume 20260329-100445-392cc285
```

### `approve <run-id>`

Approve generated verification proposals for a paused run.

```bash
/goal-agent approve 20260329-100445-392cc285 --approve-all
```

### `learn`

Aggregate recorded outcomes into the learning registry.

```bash
/goal-agent learn
```

## Goal file format

Goal files are markdown with required sections. The agent validates structure before running.

```markdown
# Goal: Build a REST API for user management

## Objective

Build a REST API with CRUD endpoints for users, backed by SQLite.
Include input validation and error handling.

## Verification

```bash
npm run build
npm test
curl -s http://localhost:3000/api/users | jq .
```

- [ ] `src/routes/users.ts` exists
- [ ] `src/db.ts` exists
- [ ] `package.json` exists

## Constraints

- Max iterations: 10
- Total budget: $10.00
- Model: sonnet
- Allowed tools: Bash,Read,Write,Edit,Glob,Grep

## Context

Optional background info, architecture notes, or conventions
the worker should follow.

## Approach

Optional hints on methodology (e.g., "use Express, not Hono").
```

**Required sections:**
- `## Objective` — what must be true when done
- `## Verification` — bash commands (exit 0 = pass) and/or file existence checks

**Optional sections:**
- `## Constraints` — iterations, budget, model, allowed tools (all have defaults)
- `## Context` — background info for the worker
- `## Approach` — methodology hints

Additional optional constraints:
- `Max parallel workers`
- `Role reinforcement interval`
- `Approval timeout`
- `Auto verify`

### Constraint defaults

| Constraint | Default |
|-----------|---------|
| Max iterations | 10 |
| Budget per phase | $2.00 |
| Total budget | $10.00 |
| Model | sonnet |
| Allowed tools | Bash,Read,Write,Edit,Glob,Grep |

## Monitoring a background run

When running with `--background`, a tmux session is created.

```bash
# List tmux sessions
tmux ls

# Attach to watch live
tmux attach-session -t <session-name>

# Detach without stopping (inside tmux)
# Press: Ctrl-b then d
```

You can also check progress without tmux:

```bash
# Quick status check
/goal-agent status

# Read state directly
cat .goal-agent/<run-id>/state.json
```

## State files

All state is persisted under `.goal-agent/<run-id>/`:

| File | Contents |
|------|----------|
| `state.json` | Current phase, iteration count, budget used, verification results |
| `plan.md` | Phase decomposition plan (created during execution) |
| `report.md` | Final completion report (created on finish) |
| `identity.json` | Orchestrator identity anchor |
| `runtime-policy.json` | Machine-enforced allowlist for orchestrator actions |
| `prepared-goal.md` | Mutable copy of the goal with approved auto-verification metadata |

Cross-run learning lives under `.goal-agent/.learning/`.

### Example state.json

```json
{
  "run_id": "20260329-100445-392cc285",
  "status": "running",
  "current_phase": 2,
  "total_phases": 4,
  "iteration": 5,
  "max_iterations": 10,
  "budget_used_estimate": 2.50,
  "budget_limit": 10.00,
  "phases": [
    {"name": "Phase 1: Scaffold", "status": "completed", "iterations": 1},
    {"name": "Phase 2: API routes", "status": "running", "iterations": 2},
    {"name": "Phase 3: Tests", "status": "pending"},
    {"name": "Phase 4: Build verify", "status": "pending"}
  ]
}
```

## Safety

- **Budget cap**: The agent tracks approximate spend per worker call and stops at the limit.
- **Iteration cap**: Each worker call counts as one iteration. Stops at max.
- **Retry limit**: If a phase fails 3 times with the same approach, the agent re-evaluates its plan instead of looping.
- **Corruption check**: After each worker call, the agent verifies the working directory is intact.
- **Scope lock**: Only implements what the goal asks for — no extras.
- **Delegation enforcement**: The orchestrator is expected to honor `runtime-policy.json`; application-file edits belong to workers, not the orchestrator.
- **Parallelism rule**: v2 parallelism is file-disjoint only. Same-file parallel edits are intentionally unsupported.
