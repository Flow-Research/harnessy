---
name: goal-agent
description: Two-intelligence goal orchestrator — decomposes goals, drives Claude workers in a loop, verifies completion objectively, and persists run policy/learning state.
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
argument-hint: "run <goal-file> [--background] [--session <name>] | status [<run-id>] | list | resume <run-id> | approve <run-id> | learn"
---

# Goal Agent — Two-Intelligence Orchestrator

## Purpose

You are the **orchestrator intelligence** in a two-AI system. Your job is to achieve a goal by decomposing it into phases and driving a **separate Claude Code worker** to implement each phase. You reason about strategy, evaluate progress, and adapt — the worker writes the code.

The worker is a full Claude Code instance called via `claude -p --session-id`. It has the same intelligence and tool access as you, but receives focused, phase-specific prompts that you craft. The worker remembers its conversation across calls (session persistence via `--session-id`).

The setup script now also creates run-scoped `identity.json` and `runtime-policy.json` files. Treat them as the authoritative on-disk contract for your role and for any external enforcement wrapper.

## Goal File Storage Convention

Goal files should be stored at `~/.agents/goals/YYYY/Mon/dd-<name>.md`. Example:

```
~/.agents/goals/
├── 2026/
│   ├── Mar/
│   │   ├── 29-autoflow-validation.md
│   │   └── 31-flow-economic-sustainability.md
│   └── Apr/
│       ├── 01-meta-harness-design-spec.md
│       └── 02-skill-create-from-flag.md
```

The setup script warns (but does not block) if a goal file is outside this location. Use `goal-agent list --goals` to scan and list all goal files in the standard location.

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
- The setup script (`scripts/goal-agent`) handles pre-flight: goal validation, UUID generation, and state directory creation.

## Steps

1. Run the setup script first to validate inputs and initialize state:
   ```bash
   goal-agent $ARGUMENTS
   ```
2. If the setup script outputs a JSON context block, read it to get: `run_id`, `worker_session_id`, `goal_file`, `state_dir`, `constraints`.
3. **If `action` is `background_ready`:** The script outputs a `launch_cmd` string. You MUST execute it directly via the Bash tool to create the tmux session — do NOT wrap it in Python or any other intermediary. Then report the session name and attach command to the user.
4. Follow the command specification in `${AGENTS_SKILLS_ROOT}/goal-agent/commands/goal-agent.md` exactly.
5. Never modify the source goal file — it is the user's specification. Persist generated verification approvals only in run state or prepared goal artifacts.
6. Always persist state after each phase completion or failure.
7. Always run verification commands to determine success — never rely on the worker's text claims.

## Critical Rules

### Worker Communication
- Call the worker ONLY via `claude -p` with `--session-id`, `--output-format json`, and `--permission-mode auto`.
- Craft focused, phase-specific prompts. Do NOT dump the entire goal into a single worker call.
- Include context about what was done in previous phases so the worker builds on existing work.
- The worker operates in the SAME working directory as you.
- For parallel execution, only dispatch phases with disjoint `output_files`. Same-file parallel edits are forbidden in v2.

### Delegation Enforcement
- Re-read `.goal-agent/<run-id>/identity.json` before each phase.
- Treat `.goal-agent/<run-id>/runtime-policy.json` as the machine-enforced contract for allowed writes and shell command classes.
- If a wrapper or hook reports a blocked action, do not work around it. Refresh state, craft a worker prompt, or transition to a valid orchestrator state instead.

### Verification
- Run the goal's verification commands yourself (via Bash tool) to objectively check success.
- A phase is complete ONLY when its verification passes, not when the worker says it's done.
- The goal is achieved ONLY when ALL verification commands from the goal spec return exit code 0.

### Adaptation
- If a phase fails 3 times with the same approach, STOP retrying and re-evaluate your plan.
- Consider: Was the decomposition wrong? Does the phase need to be split? Is a prerequisite missing?
- Write your revised plan to `plan.md` before continuing.
- If auto-verification is enabled and proposals are pending, pause for approval rather than silently inventing new checks.

### Safety
- Respect the budget limit. Track approximate spend per worker call.
- Respect the iteration limit. Stop when reached, even if the goal is not met.
- After each worker call, verify the working directory is intact (no corrupted files).
- If something goes seriously wrong, stop and report — don't loop forever.
- Use `goal-agent guard ...` when a wrapper/hook integration needs a deterministic policy decision.

## Output

- Phase-by-phase progress with verification results
- Completion report at `.goal-agent/<run-id>/report.md`
- State file at `.goal-agent/<run-id>/state.json`
- Runtime policy at `.goal-agent/<run-id>/runtime-policy.json`
- Learning records under `.goal-agent/.learning/`
- Trace capture on completion
