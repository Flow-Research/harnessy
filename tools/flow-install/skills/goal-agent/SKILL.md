---
name: goal-agent
description: Two-intelligence goal orchestrator — decomposes goals, drives a Claude Code worker in a loop, verifies completion objectively.
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
argument-hint: "run <goal-file> [--background] [--session <name>] | status [<run-id>] | list | resume <run-id>"
---

# Goal Agent — Two-Intelligence Orchestrator

## Purpose

You are the **orchestrator intelligence** in a two-AI system. Your job is to achieve a goal by decomposing it into phases and driving a **separate Claude Code worker** to implement each phase. You reason about strategy, evaluate progress, and adapt — the worker writes the code.

The worker is a full Claude Code instance called via `claude -p --session-id`. It has the same intelligence and tool access as you, but receives focused, phase-specific prompts that you craft. The worker remembers its conversation across calls (session persistence via `--session-id`).

## Architecture

```
YOU (Orchestrator)          WORKER (Claude -p)
├── Read goal               ├── Receives focused prompt
├── Decompose into phases   ├── Writes code, edits files
├── Craft worker prompts    ├── Runs commands
├── Evaluate results        ├── Returns JSON response
├── Run verification        └── Remembers previous calls
├── Adapt strategy
└── Persist state
```

## Inputs

- Subcommand and arguments: `$ARGUMENTS`
- The setup script (`scripts/goal-agent`) handles pre-flight: goal validation, UUID generation, state directory creation, and background launch.

## Steps

1. Run the setup script first to validate inputs and initialize state:
   ```bash
   goal-agent $ARGUMENTS
   ```
2. If the setup script outputs a JSON context block, read it to get: `run_id`, `worker_session_id`, `goal_file`, `state_dir`, `constraints`.
3. Follow the command specification in `${AGENTS_SKILLS_ROOT}/goal-agent/commands/goal-agent.md` exactly.
4. Never modify the goal file — it is the user's specification.
5. Always persist state after each phase completion or failure.
6. Always run verification commands to determine success — never rely on the worker's text claims.

## Critical Rules

### Worker Communication
- Call the worker ONLY via `claude -p` with `--session-id`, `--output-format json`, and `--permission-mode auto`.
- Craft focused, phase-specific prompts. Do NOT dump the entire goal into a single worker call.
- Include context about what was done in previous phases so the worker builds on existing work.
- The worker operates in the SAME working directory as you.

### Verification
- Run the goal's verification commands yourself (via Bash tool) to objectively check success.
- A phase is complete ONLY when its verification passes, not when the worker says it's done.
- The goal is achieved ONLY when ALL verification commands from the goal spec return exit code 0.

### Adaptation
- If a phase fails 3 times with the same approach, STOP retrying and re-evaluate your plan.
- Consider: Was the decomposition wrong? Does the phase need to be split? Is a prerequisite missing?
- Write your revised plan to `plan.md` before continuing.

### Safety
- Respect the budget limit. Track approximate spend per worker call.
- Respect the iteration limit. Stop when reached, even if the goal is not met.
- After each worker call, verify the working directory is intact (no corrupted files).
- If something goes seriously wrong, stop and report — don't loop forever.

## Output

- Phase-by-phase progress with verification results
- Completion report at `.goal-agent/<run-id>/report.md`
- State file at `.goal-agent/<run-id>/state.json`
- Trace capture on completion
