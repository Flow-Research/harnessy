# Auto-fix-and-retry for failing cron goal-agent runs — design sketch

Status: **proposal**, not implemented. Written 2026-04-19 after the weekly-content
cron stalled on a `json.loads` of a code-fenced response. Scope: bounded recovery
for scheduled goal-agent runs. Explicit non-scope: letting an agent re-architect
its own harness unattended.

## Problem

Today a scheduled run (`launchd` → `goal-agent run <goal> --background`) that
hits any failure stops dead. Detection is manual (`stale-gate-monitor` flags the
run hours later, a human investigates). Recovery is fully manual: read logs,
patch code, redeploy skill, trigger next run.

We want a mechanism that:

1. Detects the failure promptly
2. Classifies it (transient vs. infra-bug vs. goal-impossible vs. budget)
3. For infra-bug failures, proposes a code patch
4. Optionally, under strict limits, applies the patch and retries once

## Failure taxonomy

The mechanism must treat these differently — one policy does not fit all:

| Class              | Example                                             | Policy                                        |
|--------------------|-----------------------------------------------------|-----------------------------------------------|
| `transient`        | 429, network blip, tmux race                        | Retry immediately with backoff. No patch.     |
| `parser-infra`     | today's fence bug; stdout-shape drift               | Post-mortem → propose patch → `review`/`auto` |
| `goal-impossible`  | source file moved, schema drift, missing context    | Stop. Notify. No auto-action.                 |
| `budget-exhausted` | $2 phase cap tripped, 10-iteration cap hit          | Stop. Notify. Human decides to raise.         |
| `worker-wrong`     | worker hallucinated a path, produced invalid output | Retry once with stricter prompt. Then stop.   |

A classifier that gets `goal-impossible` confused with `parser-infra` will push
bad patches. That's the worst failure mode for this system.

## Components

### 1. Terminal-state watcher

A small daemon (or a post-run hook inside `background-runner`) that fires when a
goal-agent run reaches a terminal state with `action: "fail"` *or* exits
without producing `report.md`. Runs out-of-process so a runner crash can't
silently skip it.

Inputs available at this point (all under `.goal-agent/<run-id>/`):
- `session.log`
- `state.json` (terminal status, phase, iteration count)
- `step-NNN-raw.json` (full Claude response for each step)
- `runtime-policy.json`

### 2. Post-mortem agent

A separate goal-agent run (or a plain Agent-tool invocation) with:

- **Read-only tool scope by default** (`Read, Grep, Glob`)
- A structured prompt that receives the artifacts above and must return:
  ```yaml
  class: transient | parser-infra | goal-impossible | budget-exhausted | worker-wrong
  confidence: 0.0 – 1.0
  summary: one-line diagnosis
  evidence: [paths / log lines that support the classification]
  proposed_patch: unified diff  # only if class == parser-infra
  patch_targets: [file paths]   # all must be under tools/flow-install/
  test_to_add: pytest snippet that would fail before the patch and pass after
  ```
- Writes this to `.goal-agent/<run-id>/post-mortem.md` and
  `.goal-agent/<run-id>/proposed-patch.diff`.

The post-mortem agent runs with the **same** `background-runner` it's
diagnosing, which is a coupling risk (today's parser bug would have stopped
the diagnoser too). Mitigations:

- Post-mortem agent is simple enough to not need structured_output — plain text
  report parsed by the watcher with loose regex.
- The `_step_parser.py` fix landing today reduces this coupling anyway.
- Long-term: post-mortem can be a non-goal-agent process that just calls
  `claude` directly with the inputs inlined into the prompt.

### 3. Patch gate — two modes

Each scheduled cron declares its mode in its goal file or launchd plist
environment:

- `PATCH_GATE=review` (**default**)
- `PATCH_GATE=auto`

#### `review` mode

1. Post-mortem produces `proposed-patch.diff`.
2. Watcher creates branch `cron-fix/<run-id>`, applies the diff, pushes.
3. Opens a GitHub PR against `main` with the post-mortem as the PR body.
4. **Stops.** No retry. Human reviews, merges, next scheduled run uses the fix.

This is always safe: no production execution occurs between failure and human
sign-off.

#### `auto` mode

1. Post-mortem produces `proposed-patch.diff`.
2. Watcher applies the diff to a **scratch worktree** of the repo.
3. Runs the **full** `tools/flow-install/tests/` suite. If any test fails →
   fall back to `review` mode and stop.
4. If tests pass, runs the new `test_to_add` — must fail before the patch,
   pass after. If either check fails → fall back to `review` mode.
5. If all green, applies the diff to the working tree, reinstalls the skill
   (`node tools/flow-install/index.mjs`), and **retries the original run once**.
6. If the retry also fails → stop permanently. Do not loop. Drop to `review`.

### 4. Hard invariants (non-negotiable)

- **One retry max** per run. No recursion, no cascades.
- **Patch scope locked** to `tools/flow-install/`. Anything else → manual-only.
- **Never push to `main`.** Always branch + PR. Humans merge.
- **Never skip the test suite** before an auto-retry. A green suite is the
  gate that lets the fix touch the live harness.
- **Every auto-applied commit** carries a `Auto-Fix: <run-id>` trailer for
  audit.
- **Kill switch**: a file `.goal-agent/.disable-auto-fix` at repo root halts
  the auto path entirely.

### 5. Observability

- Post-mortem writes a one-line summary to `~/.agents/cron/auto-fix.log`
  regardless of outcome.
- `stale-gate-monitor` already surfaces long-running runs; add a parallel
  `auto-fix-monitor` that surfaces open `cron-fix/*` branches and PRs past a
  staleness threshold (e.g. >48h without human response).

## Build order

1. **Prereq (done today)**: extractor in its own module + `test_step_parser.py`
   covering the fence-stripping regression.
2. **Phase 1**: terminal-state watcher + post-mortem agent, `review` mode only.
   Opens PRs for human review. No retries. Ship this, use for a month.
3. **Phase 2**: test-suite-gated `auto` mode, opt-in per cron, one-retry cap.
   Enable only after `review` mode has shown >80% correct-classification rate.
4. **Phase 3** (optional, later): expand the classifier to propose
   `goal-impossible` fixes (e.g. "the source_material path moved to X, propose
   prompt update"). Still human-approved.

## Explicit non-goals

- Auto-fixing application code. Only `tools/flow-install/` is in scope.
- Auto-merging PRs. Ever.
- Detecting the same bug across multiple runs and batching fixes. Keep it
  one-run-one-fix until the primitives are proven.
- Running in CI. This is local launchd today; CI integration is a separate
  design.

## Open questions

- Where does the post-mortem agent source the repo state from — the current
  working tree, or a pinned commit at the time the run started? Current tree
  is simpler but can race with human edits. Pinned is safer.
- Does `auto` mode need a quarantine period (e.g. "don't retry inside 10
  minutes after failure — human may intervene first")? Lean yes, configurable.
- How do we handle a post-mortem that itself crashes? Retry once with a
  simpler prompt, then stop and log.
