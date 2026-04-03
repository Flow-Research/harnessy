# Goal Agent v2 Design Specification
## From Single-Worker Orchestration to Delegated, Parallel, Chained Goal Execution

> Building on four days of production runs and the Meta-Harness design methodology.
> This document specifies five layers of evolution for the goal-agent system.
>
> Status note: this document now serves as a design-and-gap spec, not an execution-ready implementation plan. The repository contains meaningful Layer 1 scaffolding plus partial setup support for later layers, but the core orchestrator loop, external enforcement boundary, parallel worker runtime, and chain executor are not yet implemented as deterministic runtime code.

---

## 1. Executive Summary

This document is the design specification for Goal Agent v2 — the next evolution of Flow's two-intelligence orchestration system. It is a design artifact, not code. Its audience is the implementer (human or AI) who will build these features, and the architect (Julian) who must approve the direction before any code is written.

Goal Agent v1 has proven the core thesis: a strategic orchestrator driving a tactical worker through `claude -p --session-id` calls, with objective verification gates, reliably produces complex artifacts. Three production runs completed with zero plan revisions and perfect first-pass verification. The architecture works — but it has a ceiling.

In repository reality, Goal Agent v2 is unevenly implemented. The current helper script already creates `identity.json`, `runtime-policy.json`, approval state for generated verification proposals, meta-goal scaffolding, outcome records, and a simple learning registry. However, that should not be confused with a fully implemented v2 runtime. The strongest missing pieces are still the ones that matter most operationally: an enforced external delegation boundary, a deterministic phase-execution loop, real parallel dispatch, real goal-graph execution, and runtime integration between these pieces.

This specification defines five enhancement layers that raise that ceiling, ordered by criticality and dependency:

**Layer 1: Delegation Enforcement** is the foundation everything else depends on. In long sessions, Claude's context window compressor can lose the SKILL.md instructions that define the orchestrator's identity as a delegator. When this happens, the orchestrator stops calling `claude -p` and starts writing code directly — a catastrophic mode failure. This layer introduces session anchoring, structural delegation guards, and a role reinforcement protocol to make the orchestrator's identity compression-resistant.

**Layer 2: Multi-Worker Parallelism** eliminates the sequential bottleneck. Independent phases (e.g., writing separate sections of a spec, implementing unrelated features) currently wait in a queue. This layer adds dependency graph analysis and concurrent worker dispatch, potentially halving wall-clock time for parallelizable goals.

**Layer 3: Goal Chaining** extends the system from isolated goals to dependency graphs. Goal B can declare that it depends on Goal A's output, enabling multi-goal workflows where artifact outputs flow between runs.

**Layer 4: Self-Generated Verification** addresses the fact that verification quality is currently bounded by the goal author's foresight. The orchestrator will propose additional verification checks — subject to human approval — catching edge cases the author didn't anticipate.

**Layer 5: Cross-Run Learning** closes the feedback loop. Decomposition patterns, phase timing data, and failure modes from historical runs feed back into future planning, so the orchestrator improves its strategy over time rather than starting from zero each run.

Layer 1 is non-negotiable. Without reliable delegation enforcement, every other layer inherits a mode-failure risk — a parallel orchestrator that forgets it's an orchestrator is worse than a sequential one that remembers. The remaining layers can be implemented in order or selectively based on which bottleneck matters most for the goals being run.

---

## 2. Current Architecture

### 2.1 The Two-Intelligence Model

Goal Agent v1 implements a target separation between strategic reasoning and tactical execution. Two distinct Claude instances collaborate through a well-defined protocol, but some of the enforcement is still procedural rather than hard runtime policy:

The **orchestrator** is a Claude Code session running interactively (or in a tmux background session). It reads the user's goal specification, decomposes the objective into sequential phases, crafts focused prompts for each phase, evaluates results against objective verification criteria, and adapts the plan when phases fail. Critically, the intended model is that the orchestrator never writes application code — its tools are limited to `Read`, `Write`, `Edit`, `Bash`, `Grep`, and `Glob`, used for state management, verification command execution, and prompt file generation. In the current repo this separation is partially scaffolded, not fully guaranteed: the helper script can generate policy artifacts and evaluate proposed actions, but it does not yet prove that every orchestrator side effect is routed through an authoritative external guard.

The **worker** is a headless Claude Code instance invoked via `claude -p` with `--output-format json` and `--permission-mode auto`. It receives a single, focused prompt for one phase, executes it using the full Claude Code tool suite, and returns a structured JSON response. The worker persists its conversation history across calls via `--session-id` (a UUID generated at run initialization), which means later phases benefit from the worker's accumulated understanding of the codebase — without the orchestrator needing to re-explain prior work in every prompt.

This keeps the orchestrator's context clean — it sees only strategic reasoning, state, and pass/fail results. The worker builds deep tactical context but never reasons about multi-phase strategy or budget.

### 2.2 The Three-File Contract

Every goal-agent run is governed by three files that form a strict contract:

1. **Goal file** (user-authored, immutable) — A markdown specification containing the objective, constraints (max iterations, budget, model, allowed tools), verification commands, file checks, context, and optional approach hints. The orchestrator reads but never modifies this file. The setup script (`scripts/goal-agent`) parses it to extract structured data: constraints are matched via regex from the `## Constraints` section, verification commands are extracted from fenced code blocks in `## Verification`, and file checks are parsed from checkbox-formatted lines.

2. **State file** (`.goal-agent/<run-id>/state.json`) — The run's persistent checkpoint. Updated after every phase attempt, it records: `run_id`, `worker_session_id`, `goal_file` path, `status` (initialized/running/completed/failed), current and total phases, iteration count, budget estimates, per-phase status with iteration counts, verification commands, and timestamps. This file enables the `resume` command — a crashed or interrupted run can restart from its last checkpoint.

3. **Plan file** (`.goal-agent/<run-id>/plan.md`) — The orchestrator's phase decomposition, written before execution begins and revised if phases fail repeatedly (3 consecutive identical failures trigger mandatory re-planning). Each phase entry specifies a deliverable, verification strategy, and worker prompt strategy.

A fourth artifact, the **report file** (`.goal-agent/<run-id>/report.md`), is generated at completion and provides a human-readable summary with phase tables, verification results, and statistics.

### 2.3 Worker Communication Protocol

The orchestrator communicates with the worker through a carefully structured prompt format. Each worker prompt contains four sections: **Task** (the specific phase deliverable — never the whole goal), **Context** (what previous phases produced, including file paths and current state), **Expected Output** (concrete file names, function signatures, expected content), and **Constraints** (language, framework, and style requirements from the goal — budget and iteration limits are deliberately withheld from the worker since those are the orchestrator's concern).

Worker prompts are written to `.goal-agent/<run-id>/current-prompt.md`. In current command guidance, the reliable invocation method is to pass the prompt through stdin rather than command substitution, because quoted multi-line prompt content is fragile on the shell path. The `--max-budget-usd` flag caps per-phase spend, calculated as total budget divided by number of phases with a buffer.

### 2.4 Verification-Driven Completion

The system's most important property is that **no phase is considered complete until its verification passes objectively**. The orchestrator runs verification commands itself via the Bash tool — it never trusts the worker's textual claims about success. For each command in the goal's `## Verification` section, exit code 0 means pass, anything else means fail. File checks use `test -f <path>`.

Final verification runs every command from the goal spec. If all pass, the goal is achieved. If any fail, the orchestrator can add correction phases or report partial completion. This is a binary gate, not a fuzzy assessment.

### 2.5 Safety and Adaptation

The system enforces four safety boundaries: **budget tracking** (approximate spend per worker call, stop if total estimate exceeds limit), **iteration caps** (each worker call counts as one iteration, hard stop at max), **corruption checks** (verify working directory structure after each worker call), and **infinite loop prevention** (3 consecutive identical failures force a plan revision, not another retry).

When a phase fails but is retryable, the orchestrator crafts a corrective prompt that includes the error details and what specifically went wrong. When a phase fails and the plan is wrong, the orchestrator re-decomposes, updates `plan.md`, and restarts from the adjusted phase.

### 2.6 Production Performance Data

Three completed production runs demonstrate the system's current capabilities:

| Run | Goal | Phases | Iterations | Cost | Model | Plan Revisions |
|-----|------|--------|------------|------|-------|----------------|
| `20260329-153231` | Accelerate Africa Tier 1 Deliverables (Fellowship JD + Partnership Brief) | 3 | 3 | $0.94 | Sonnet | 0 |
| `20260331-080137` | Sentinel Requirements Spec (9,617 words, 19 verification checks) | 5 | 4 | $1.54 | Sonnet | 0 |
| `20260401-150019` | Meta-Harness Design Spec (11,999 words, 20 verification checks, 21+ code blocks) | 6 | 6 | $7.34 | Opus | 0 |

Key observations from these runs:

- **Zero plan revisions** across all runs. Initial decompositions have been correct — likely because goals are well-specified; adversarial or ambiguous goals would force re-planning.
- **Perfect first-pass verification.** 100% pass rates without retries across all runs.
- **Cost scales with model.** Sonnet: $0.94 and $1.54 for 3- and 4-call runs. Opus: $7.34 for 5 calls (~5x per call).
- **Sequential bottleneck.** All phases execute sequentially. Independent phases could run in parallel.
- **Orchestrator amnesia.** The orchestrator re-reads state.json each iteration but does not persist strategic reasoning. In long runs, it may lose nuanced understanding of its evolving strategy.

### 2.7 Current Limitations Summary

| Limitation | Impact | Proposed Layer |
|-----------|--------|----------------|
| Orchestrator loses strategic context between worker calls | Drift in prompt quality over long runs | Layer 1: Delegation Enforcement |
| All phases execute sequentially | Unnecessary wall-clock time for independent work | Layer 2: Multi-Worker Parallelism |
| Goals are standalone; no dependencies between goals | Cannot express "Goal B depends on Goal A's output" | Layer 3: Goal Chaining |
| Verification is author-defined only; no generated checks | Missing edge cases the goal author didn't anticipate | Layer 4: Self-Generated Verification |
| Each run starts from zero; no learning across runs | Same decomposition mistakes repeated; no pattern reuse | Layer 5: Cross-Run Learning |
| No lightweight progress visibility from outside tmux | Users must attach to session to check status | Deferred (improve `status` subcommand) |
| No mid-run intervention or steering | Only option is kill and restart | Deferred (requires interactive channel design) |
| Verification checks structure, not substance | Analytical rigor depends on orchestrator judgment | Partially addressed by Layer 4 |

### 2.8 Implementation Reality Check

The current repository should be understood in four buckets:

1. **Implemented scaffolding**
   - run setup and state directory initialization
   - `identity.json` and `runtime-policy.json`
   - generated verification proposal persistence and approval state
   - meta-goal parsing and chain-state scaffolding
   - outcome recording and simple learning registry generation
2. **Partially scaffolded but not operationally complete**
   - Layer 1 delegation enforcement
   - Layer 4 self-generated verification
   - Layer 5 cross-run learning
3. **Specified but absent as runtime code**
   - deterministic orchestrator phase loop inside the helper runtime
   - external pre-action enforcement wrapper for all orchestrator side effects
   - real multi-worker pool and parallel dispatch engine
   - real goal DAG executor and artifact handoff engine
4. **Strategically deferred for current workspace priorities**
   - broad Layer 2-5 rollout while Flow Platform POC runtime work remains on the critical path

---

## 3. Delegation Enforcement — Solving Orchestrator Amnesia (Layer 1)

The orchestrator's most valuable property is that it *never writes application code*. It decomposes, delegates via `claude -p`, verifies, and adapts. Every other guarantee in the system — objective verification, budget control, strategic adaptation — depends on this property holding. Layer 1 exists to make it hold reliably, even in sessions long enough to trigger context compression.

### 3.1 Problem Statement

Claude Code's context window is finite. When a conversation grows long — many worker calls, verbose verification output, plan revisions — the system compresses earlier messages to make room. This compression is lossy. It prioritizes recent exchanges and summarizes or drops older content.

The orchestrator's identity is defined in SKILL.md, which is loaded into the conversation at the start of a session. The Critical Rules section — "Call the worker ONLY via `claude -p`", the allowed-tools restriction, the verification protocol — forms the behavioral constitution of the orchestrator. But these instructions occupy the *oldest* position in the context window. They are the first candidates for compression.

When SKILL.md instructions are compressed or lost, the orchestrator experiences **identity drift**. It retains its general intelligence but loses the specific constraint that it must delegate. It sees a failing test and, instead of crafting a corrective prompt for the worker, it opens the file and fixes the code itself. It sees a missing function and writes it inline. From the orchestrator's perspective, this feels efficient — it can see the problem, it has `Write` and `Edit` tools, why not just fix it? But this violates the two-intelligence separation that makes the entire architecture work.

The consequences of identity drift are severe:

- **Context pollution.** The orchestrator's context fills with implementation details — thousands of lines of code, debugging output, import chains — that belong in the worker's context. This accelerates further compression, creating a doom spiral.
- **Verification bypass.** An orchestrator doing work directly tends to skip objective verification. It "knows" what it just wrote is correct because it just wrote it. The verification-driven completion guarantee is lost.
- **Budget invisibility.** Worker calls are budget-tracked via `--max-budget-usd`. Direct orchestrator work is invisible to the budget system — it's just tool calls in an interactive session.
- **Session persistence loss.** The worker accumulates codebase understanding via `--session-id`. When the orchestrator does work directly, that understanding doesn't flow back to the worker. Subsequent worker calls lack context about changes the orchestrator made "off-book."

This has not manifested in production yet (runs were 3-6 worker calls), but the system targets goals requiring 10-20+ phases. At that scale, orchestrator amnesia becomes near-certain without countermeasures. We evaluate three approaches below, then recommend a combined strategy. The critical design constraint for Layer 1 is this: delegation must be enforced by something outside the orchestrator's own reasoning. A drifted orchestrator cannot be trusted to reliably self-police.

### 3.2 Approach 1: Session Anchoring / Runtime Policy File

**Mechanism.** Rather than relying solely on SKILL.md instructions loaded at conversation start, we persist the orchestrator's identity to the filesystem and re-read it before every significant action. The identity file acts as a **session anchor** — a stable reference point that survives context compression because it is re-loaded from disk, not recalled from memory.

At run initialization, the orchestrator writes its identity contract to a file:

```json
// .goal-agent/<run-id>/identity.json — the session anchor
{
  "role": "orchestrator",
  "run_id": "20260401-150019",
  "worker_session_id": "a1b2c3d4-...",
  "identity_version": 1,
  "core_rules": [
    "I am the ORCHESTRATOR. I decompose, delegate, verify, and adapt.",
    "I NEVER write application code. My tools are for state management and verification ONLY.",
    "I delegate ALL implementation work via: claude -p --session-id $WORKER_SESSION_ID",
    "A phase is complete ONLY when verification commands return exit code 0.",
    "If I am about to use Write or Edit on a non-state file, I am violating my role."
  ],
  "allowed_file_patterns": [
    ".goal-agent/*",
    "plan.md",
    "state.json",
    "current-prompt.md",
    "report.md"
  ],
  "delegation_command_template": "claude -p --session-id \"$SID\" --output-format json --permission-mode auto"
}
```

Before every phase iteration, the orchestrator re-reads this file. This is a filesystem read, not a memory recall — it injects fresh identity instructions into the most recent part of the context window, where they are least likely to be compressed.

Instead of mutating the shared project-root `AGENTS.md`, the setup script writes a run-scoped `runtime-policy.json` under `.goal-agent/<run-id>/`. This file is consumed by the launcher and by any shell wrapper or hook that validates orchestrator actions. The repository's checked-in agent protocol remains untouched, avoiding dirty-worktree churn, merge races, and accidental persistence of ephemeral run state.

**Weaknesses.** Session anchoring is still passive. It improves recall, but by itself it does not stop a drifted orchestrator from taking a forbidden action.

**When it fails.** In long sessions where the orchestrator stops consulting `.goal-agent/` state entirely. This is why anchoring is necessary but not sufficient.

### 3.3 Approach 2: External Structural Delegation Guards

**Mechanism.** Instead of relying on the orchestrator to remember its role, we build a **delegation guard** — a monitoring layer that detects when the orchestrator violates its delegation contract and intervenes. The guard operates on observable behavior (tool calls) rather than internal reasoning.

The core insight: an orchestrator that is functioning correctly produces a predictable tool-call signature. Its primary tool calls are `Bash` (for `claude -p` and verification commands), `Read` (for state files and goal files), and `Write`/`Edit` (for state files, prompts, plans, and reports). An orchestrator that has drifted produces a different signature: `Write`/`Edit` calls targeting application source files, `Bash` calls running implementation commands (not `claude -p` or verification).

The guard is implemented as an **external enforcement boundary** around the orchestrator's write/edit/shell path, not as self-check instructions in SKILL.md. In practice this can be a wrapper script, command interceptor, or hook that validates each attempted action against the run's runtime policy before execution. The orchestrator is still instructed to self-check, but that instruction is advisory; the external gate is authoritative. The logic is equivalent to:

```python
# Delegation guard pseudocode — runs before every tool call

ORCHESTRATOR_ALLOWED_PATHS = {
    ".goal-agent/*/state.json",
    ".goal-agent/*/plan.md",
    ".goal-agent/*/current-prompt.md",
    ".goal-agent/*/report.md",
    ".goal-agent/*/identity.json",
    ".goal-agent/*/runtime-policy.json",
}

DELEGATION_COMMANDS = {
    "claude -p",           # Worker delegation
    "test -f",             # File existence check
    "echo \"EXIT_CODE:",   # Verification exit code capture
    "python3 *trace_capture.py",  # Trace capture
    "cat .goal-agent/",    # State file reads
    "ls .goal-agent/",     # Run listing
}

def is_delegation_compliant(tool_name: str, tool_args: dict) -> bool:
    if tool_name in ("Read", "Grep", "Glob"):
        return True

    if tool_name in ("Write", "Edit"):
        target_path = tool_args["file_path"]
        return any(fnmatch(target_path, pat) for pat in ORCHESTRATOR_ALLOWED_PATHS)

    if tool_name == "Bash":
        command = tool_args["command"]
        return any(marker in command for marker in DELEGATION_COMMANDS)

    return False

def delegation_guard(tool_name: str, tool_args: dict) -> str:
    if not is_delegation_compliant(tool_name, tool_args):
        return (
            "⚠️ DELEGATION VIOLATION DETECTED.\n"
            f"Tool: {tool_name}, Target: {tool_args}\n"
            "You are the ORCHESTRATOR. You do not write application code.\n"
            "Craft a worker prompt and delegate via: claude -p --session-id $SID\n"
            "Re-read .goal-agent/<run-id>/identity.json NOW."
        )
    return "OK"
```

The guard also tracks a **delegation ratio** — the proportion of tool calls that are delegation-related (calling `claude -p`, reading/writing state files) versus direct-work-related (editing application code, running implementation commands). A healthy orchestrator has a delegation ratio above 0.8. If the ratio drops below 0.5 over a sliding window of 10 tool calls, the guard triggers a hard intervention: block further non-state actions until the orchestrator refreshes identity and advances through a valid state transition.

**Weaknesses.** The delegation guard is only as good as its pattern matching. A subtly drifted orchestrator might use an unusual shell construct to mutate files indirectly. The mitigation is to treat shell commands as deny-by-default except for whitelisted delegation and verification forms.

**When it fails.** When the launcher cannot intercept an action path, or when policy patterns are too broad and accidentally admit an implementation-side command. This is an implementation risk in the wrapper, not in the model prompt.

### 3.4 Approach 3: Role Reinforcement Protocol

**Mechanism.** The **role reinforcement protocol** treats delegation as a state machine rather than a static instruction. At any given moment, the orchestrator should be in one of a small number of defined states, and only certain actions are valid in each state. By making the state explicit and persistent, the orchestrator can detect when it's about to take an action that doesn't match its current state — even if it has forgotten *why* the state matters.

The state machine:

```
INIT → ANALYZE_GOAL → DECOMPOSE → [PHASE_LOOP] → FINAL_VERIFY → REPORT

PHASE_LOOP:
  CRAFT_PROMPT → CALL_WORKER → EVALUATE_RESULT → UPDATE_STATE
                                    ↓ (fail, retryable)
                               CRAFT_CORRECTIVE_PROMPT → CALL_WORKER
                                    ↓ (fail, plan wrong)
                               RE_DECOMPOSE → CRAFT_PROMPT
```

Each state has an **allowed action set**:

| State | Allowed Actions | Forbidden Actions |
|-------|----------------|-------------------|
| `ANALYZE_GOAL` | Read goal file, Read context files | Write, Edit, Bash (non-read) |
| `DECOMPOSE` | Write plan.md, Write state.json | Edit application files, Bash (non-state) |
| `CRAFT_PROMPT` | Write current-prompt.md, Read state | Edit application files |
| `CALL_WORKER` | Bash (`claude -p` only) | Write, Edit, Read (non-state) |
| `EVALUATE_RESULT` | Read any file, Bash (verification only) | Write application files, Edit application files |
| `UPDATE_STATE` | Write state.json, Write plan.md | Edit application files |
| `FINAL_VERIFY` | Bash (verification commands only) | Write, Edit |
| `REPORT` | Write report.md, Bash (trace capture) | Edit application files |

The orchestrator persists its current state in `state.json`:

```json
{
  "run_id": "20260401-150019",
  "orchestrator_state": "CRAFT_PROMPT",
  "phase": 3,
  "delegation_count": 7,
  "direct_action_count": 0,
  "last_role_reinforcement": "2026-04-01T15:30:00Z",
  "role_reinforcement_interval": 3
}
```

The `role_reinforcement_interval` field triggers periodic re-injection. Every N phase iterations (default: 3), the orchestrator prepends a **delegation checkpoint** to its next action:

> **DELEGATION CHECKPOINT — Iteration 7, Phase 3**
> I am the orchestrator for run 20260401-150019.
> My current state is CRAFT_PROMPT. I am about to write a worker prompt.
> My delegation count is 7. My direct action count is 0.
> I must NOT write application code. I must delegate via `claude -p --session-id <sid>`.
> If my next action is not consistent with CRAFT_PROMPT, I must STOP and re-read identity.json.

This checkpoint is not just a reminder — it's a self-diagnostic. By forcing the orchestrator to explicitly state its current state and next intended action, it creates a moment of reflection that can catch drift before it manifests as a tool call. Unlike Approach 2, however, it is not a hard boundary.

**Weaknesses.** The state machine adds complexity to the orchestrator's reasoning. Each phase iteration now includes state transition logic on top of the actual strategic reasoning. For simple, short runs (3-4 phases), this overhead is disproportionate. The allowed-action table also needs careful calibration — too strict and legitimate orchestrator work is blocked; too loose and violations slip through.

The periodic reinforcement is only effective if the orchestrator hasn't drifted *between* checkpoints. With an interval of 3, the orchestrator could drift during iterations 4, 5, and 6 before being corrected at iteration 7. In a fast-moving session, three iterations of unchecked drift could cause significant damage.

**When it fails.** When the orchestrator's context is so compressed that it no longer processes the delegation checkpoint text meaningfully — it sees the text but doesn't internalize the constraint. Also fails if the state machine itself becomes a source of confusion (e.g., the orchestrator misidentifies its current state and takes actions valid for a different state).

### 3.5 Recommended Combined Approach

No single approach is sufficient. Session anchoring provides the *content* (what the orchestrator should do) but not the *enforcement* (ensuring it actually does it). External delegation guards provide enforcement but still need a clear runtime policy to enforce against. Role reinforcement provides structure but adds complexity and has gaps between checkpoints. The recommended approach combines all three into a layered defense:

**Layer A: Always-On Context Pin (from Approach 1).** At run initialization, write `identity.json` and `runtime-policy.json` to the run directory. The orchestrator re-reads `identity.json` before each phase, and the launcher consults `runtime-policy.json` before every orchestrator side-effect. This is the baseline — low-cost, always present, but not sufficient alone.

**Layer B: State-Driven External Guard (from Approaches 2 + 3).** Merge the structural guard with the state machine. The `state.json` file tracks the current orchestrator state (`CRAFT_PROMPT`, `CALL_WORKER`, `EVALUATE_RESULT`, etc.). Before every tool call, the external launcher validates the attempted action against *both* the allowed-path patterns (Approach 2) and the current-state allowed-action set (Approach 3). This dual check catches violations that either approach alone would miss.

The orchestrator is instructed to think through the same check in its own reasoning, but the authoritative decision is made by the wrapper:

```python
# Combined delegation guard — wrapper-enforced pre-action check

def pre_action_check(intended_tool, intended_args, current_state, identity):
    """
    Called before every tool invocation in the phase loop.
    Returns: "PROCEED" or a correction instruction.
    """
    # 1. Path-based check (Approach 2)
    if not is_delegation_compliant(intended_tool, intended_args):
        return f"BLOCKED: {intended_tool} on {intended_args} is not in allowed paths. Delegate instead."

    # 2. State-based check (Approach 3)
    allowed = STATE_ACTION_TABLE[current_state]
    if intended_tool not in allowed:
        return (
            f"BLOCKED: {intended_tool} is not valid in state {current_state}. "
            f"Allowed: {allowed}. Transition to correct state first."
        )

    # 3. Delegation ratio check (Approach 2)
    ratio = identity["delegation_count"] / max(1,
        identity["delegation_count"] + identity["direct_action_count"])
    if ratio < 0.6:
        return "WARNING: Delegation ratio below 0.6. Re-read identity.json and confirm role."

    return "PROCEED"
```

**Layer C: Periodic Role Reinforcement (from Approach 3).** Every 2 phase iterations (not 3 — tighter interval to reduce drift window), inject a delegation checkpoint into the orchestrator's reasoning. This checkpoint includes the core rules from `identity.json`, the current delegation ratio, and an explicit statement of the next expected state transition. The checkpoint is triggered by checking `iteration % role_reinforcement_interval == 0` when reading `state.json`.

**Why this combination works.** The three layers defend against different failure modes:

- Context pin (Layer A) handles **gradual drift** — the orchestrator's identity is always reachable on disk.
- Delegation guard (Layer B) handles **acute violations** — a specific tool call that violates the contract is caught before execution by an external boundary.
- Role reinforcement (Layer C) handles **strategic drift** — the orchestrator's overall behavior pattern is periodically audited against its intended role.

A fully drifted orchestrator would need to simultaneously: ignore the on-disk identity anchor, be blocked repeatedly by the external guard, and remain unable to recover through periodic checkpoints. This is still possible in theory, but materially less likely than a prompt-only solution failing silently.

**File changes required for Layer 1:**

| File | Change |
|------|--------|
| `SKILL.md` | Add delegation guard instructions to Critical Rules; add identity file creation to Steps |
| `goal-agent.md` | Add pre-action check to Step 3a-3d loop; add identity.json write to Step 0 |
| `scripts/goal-agent` (setup) | Generate `identity.json` and `runtime-policy.json` alongside `state.json`; route orchestrator actions through the policy wrapper |
| `state.json` schema | Add fields: `orchestrator_state`, `delegation_count`, `direct_action_count`, `last_role_reinforcement`, `role_reinforcement_interval` |
| New: `identity.json` schema | Core rules, allowed file patterns, delegation command template |
| New: `runtime-policy.json` | Machine-enforced allowlist for orchestrator file writes and shell command classes |

---

## 4. Multi-Worker Parallelism (Layer 2)

Layer 2 introduces a **Parallel Worker** execution model that allows the orchestrator to spawn multiple concurrent workers for independent phases. This is the single largest performance improvement available to the system — it targets the sequential bottleneck identified in Section 2.7 without changing the fundamental two-intelligence architecture.

### 4.1 Problem Statement

Every production run to date has executed phases strictly in sequence. The Meta-Harness run (Section 2.6) used 6 phases, each waiting for the prior phase to complete before starting. But not all phases depend on each other. Consider a design-spec goal with this phase plan:

1. Write Section 1 (Executive Summary)
2. Write Section 2 (Architecture Overview)
3. Write Section 3 (Feature Design A) — depends on Section 2
4. Write Section 4 (Feature Design B) — depends on Section 2
5. Write Section 5 (Feature Design C) — depends on Section 2
6. Write Section 6 (Implementation Plan) — depends on Sections 3, 4, 5

Phases 3, 4, and 5 are independent of each other — they all depend on Phase 2's output but not on each other. In sequential execution, total wall-clock time is `T1 + T2 + T3 + T4 + T5 + T6`. With parallelism, Phases 3-5 execute concurrently: `T1 + T2 + max(T3, T4, T5) + T6`. For the Meta-Harness run, where each worker call averaged ~80 seconds, parallelizing 3 independent phases would save approximately 160 seconds — a 40% reduction in wall-clock time with no change in output quality.

The savings scale with goal complexity. The constraint is not compute — Claude Code can spawn multiple headless instances — but coordination: workers share a filesystem, and two workers editing the same file simultaneously will corrupt each other's work. For this reason, v2 parallelism is file-disjoint only. If two phases need to change the same file, they are sequential by definition in this version.

### 4.2 Dependency Graph Analysis

Before the orchestrator can run phases in parallel, it must determine which phases are independent. This requires analyzing the phase plan to produce a dependency DAG (directed acyclic graph) where nodes are phases and edges represent "must complete before" relationships.

Three types of dependencies exist:

- **Data dependencies.** Phase B reads or modifies a file that Phase A creates.
- **Ordering dependencies.** Phase B refines or extends Phase A's output in the same file — even without logical dependency, they touch the same file and cannot run concurrently.
- **Independence.** Phases touch entirely different files and have no logical dependency.

The orchestrator extracts dependency information during decomposition (the `DECOMPOSE` state from Layer 1). Each phase in `plan.md` already specifies its deliverable files. The dependency analysis algorithm uses these file lists plus explicit dependency declarations:

```python
# Dependency graph construction — runs during DECOMPOSE state

def build_dependency_dag(phases: list[Phase]) -> dict[int, set[int]]:
    """
    Produces a DAG as adjacency list: {phase_id: set of phase_ids it depends on}.
    A phase with an empty dependency set can run as soon as the DAG allows.
    """
    dag = {p.id: set() for p in phases}
    file_producers = {}  # file_path -> phase_id that first creates/modifies it

    for phase in phases:
        # 1. Explicit dependencies declared in the plan
        for dep_id in phase.depends_on:
            dag[phase.id].add(dep_id)

        # 2. File-based dependencies: if this phase reads or modifies a file
        #    that a prior phase produces, add an implicit dependency
        for file_path in phase.input_files:
            if file_path in file_producers:
                dag[phase.id].add(file_producers[file_path])

        # 3. File conflict dependencies: if this phase writes to a file
        #    that a prior phase also writes to, they cannot be parallel
        for file_path in phase.output_files:
            if file_path in file_producers:
                dag[phase.id].add(file_producers[file_path])
            file_producers[file_path] = phase.id

    # Validate: detect cycles (should not occur with sequential phase numbering,
    # but defensive check for manually declared depends_on)
    if has_cycle(dag):
        raise PlanError("Dependency cycle detected — phases cannot form a DAG")

    return dag


def compute_parallel_groups(dag: dict[int, set[int]]) -> list[list[int]]:
    """
    Topological sort into parallel execution groups.
    Each group contains phases that can run simultaneously.
    """
    groups = []
    remaining = dict(dag)
    completed = set()

    while remaining:
        # Find all phases whose dependencies are fully satisfied
        ready = [p for p, deps in remaining.items()
                 if deps.issubset(completed)]
        if not ready:
            raise PlanError("Unsatisfiable dependencies — stuck phases remain")
        groups.append(sorted(ready))
        completed = completed.union(ready)
        for p in ready:
            del remaining[p]

    return groups
```

For the 6-phase example above, this algorithm produces three groups: `[[1], [2], [3, 4, 5], [6]]` — confirming that phases 3-5 can run as a **concurrent phase** batch because they write to different output files. The orchestrator uses `compute_parallel_groups` to determine execution waves rather than iterating phases one by one.

### 4.3 Parallel Execution Model

The **Multi-Worker** execution model extends the v1 phase loop. Instead of a single `CALL_WORKER` state, the orchestrator enters a `DISPATCH_PARALLEL` state that spawns multiple workers, monitors their progress, and collects results before proceeding.

Each parallel worker gets its own `--session-id` (a fresh UUID), because workers cannot share sessions. This means parallel workers do not benefit from each other's accumulated context — they each start with only the orchestrator's prompt and whatever files exist on disk. This is acceptable because independent phases, by definition, don't need each other's context.

The orchestrator manages a **Worker Pool** with a configurable concurrency limit. The limit exists for three reasons: (1) API rate limits — Anthropic's API has per-organization request concurrency limits; (2) resource consumption — each `claude -p` instance consumes local CPU, memory, and file descriptors; (3) budget control — more concurrent workers means faster spend with less time to react if something goes wrong. The default concurrency limit is 3, configurable in the goal file's `## Constraints` section via `max_parallel_workers`.

The worker pool state is tracked in `state.json` under a new `parallel_dispatch` field:

```json
{
  "run_id": "20260405-120000",
  "orchestrator_state": "DISPATCH_PARALLEL",
  "phase": 3,
  "parallel_dispatch": {
    "group_id": 2,
        "workers": [
      {
        "phase_id": 3,
        "session_id": "f1a2b3c4-...",
        "pid": 48201,
        "status": "running",
        "started_at": "2026-04-05T12:01:00Z",
        "budget_allocated_usd": 1.20,
        "budget_spent_usd": 0.00,
        "output_files": ["feature-a.md"],
        "last_heartbeat": "2026-04-05T12:01:30Z"
      },
      {
        "phase_id": 4,
        "session_id": "a5b6c7d8-...",
        "pid": 48202,
        "status": "running",
        "started_at": "2026-04-05T12:01:01Z",
        "budget_allocated_usd": 1.20,
        "budget_spent_usd": 0.00,
        "output_files": ["feature-b.md"],
        "last_heartbeat": "2026-04-05T12:01:31Z"
      },
      {
        "phase_id": 5,
        "session_id": "e9f0a1b2-...",
        "pid": 48203,
        "status": "completed",
        "started_at": "2026-04-05T12:01:02Z",
        "completed_at": "2026-04-05T12:02:15Z",
        "budget_allocated_usd": 1.20,
        "budget_spent_usd": 0.87,
        "output_files": ["feature-c.md"],
        "exit_code": 0
      }
    ],
    "max_concurrent": 3,
    "completion_policy": "wait_all"
  }
}
```

The spawn → monitor → collect pattern works as follows. **Spawn:** The orchestrator writes prompt files for all phases in the current parallel group, then launches each worker as a background process with output redirected to a per-worker file: `claude -p --session-id "$SID" --output-format json --permission-mode auto --max-budget-usd $PHASE_BUDGET "$(cat .goal-agent/$RUN_ID/current-prompt-phase-$N.md)" > .goal-agent/$RUN_ID/worker-output-$N.json 2>&1 &`. Output redirection is essential — without it, concurrent workers interleave JSON on stdout, corrupting all results. **Monitor:** The orchestrator polls worker processes using `kill -0 $PID` at 10-second intervals, updating liveness timestamps. At this layer, monitoring is intentionally limited to process liveness, exit state, and post-run cost reported in worker output. Real-time token and cost telemetry is out of scope unless the worker runtime exposes it explicitly. If a worker disappears without a completion marker, it's marked `crashed`. Workers that exceed 2× the average phase duration from past runs (or 10 minutes if no history) are marked `timed_out` and killed via `kill $PID`. **Collect:** When all workers in the group reach a terminal state (`completed`, `failed`, or `crashed`), the orchestrator transitions to `EVALUATE_RESULT` and runs verification for each phase's deliverables.

The `completion_policy` supports `wait_all` (default) and `fail_fast` (kill remaining workers on any failure — useful for tightly coupled phases).

### 4.4 Result Aggregation and Conflict Resolution

Two workers writing to the same file simultaneously produce corrupted output. Therefore v2 does **not** support same-file parallel edits.

The system uses a **file-disjoint scheduling** strategy combined with post-run validation:

**Prevention (hard scheduling rule).** During decomposition, any two phases that declare the same file in `output_files` are automatically serialized by the DAG builder. This is the primary protection, and it is structural rather than advisory.

**Detection (post-completion diff analysis).** After all parallel workers complete, the orchestrator runs `git diff` (or a content-based diff against pre-dispatch snapshots) to verify that each worker changed only its declared output files. The pre-dispatch snapshot is taken by the orchestrator copying target files to `.goal-agent/<run-id>/snapshots/` before spawning workers.

**Resolution.** Three options ranked by preference: (1) **Re-run the offending phase** with a corrected file contract. (2) **Sequential fallback** — re-run conflicting phases sequentially (v1 behavior). (3) **Pause for human intervention** on complex conflicts. The orchestrator never attempts automatic merge — the risk of incoherent output is too high.

### 4.5 Budget Distribution Across Workers

Budget allocation must balance two goals: give each worker enough budget to complete its phase, and don't over-allocate such that a runaway worker consumes the entire remaining budget before other phases can execute.

The allocation algorithm uses phase complexity estimates derived from the plan:

**Base allocation.** Divide the remaining budget equally among phases in the current parallel group: `base = remaining_budget / num_phases_remaining` (not just the current group — reserve budget for future groups). For a 6-phase goal with $6.00 total budget and phases 3-5 running in parallel (3 phases remaining after phases 1-2 cost $2.00), each parallel worker gets: `$4.00 remaining / 4 phases remaining = $1.00 base`.

**Complexity weighting.** If the orchestrator's plan annotates phases with relative complexity (e.g., "Phase 3 is a simple enumeration, Phase 4 is a complex design"), weights adjust the allocation. A phase marked `complexity: high` gets 1.5x base; `complexity: low` gets 0.7x base. The weights are normalized so the total allocation for the group doesn't exceed the group's budget envelope.

**Safety margin.** The *group's* total allocation includes a 20% buffer (not per-worker — applying 120% to each worker in a 3-worker group would overshoot). For 3 workers with $1.00 base each, the group envelope is $3.00 × 1.2 = $3.60, split as $1.20 per worker. The orchestrator tracks actual spend from worker JSON output after each group completes and adjusts the remaining budget for subsequent groups. Real-time throttling during the group is intentionally limited to the hard per-worker `--max-budget-usd` cap.

**Failure budget.** 10% of the total budget is held in reserve as a "retry pool" — not allocated to any phase upfront. If a parallel worker fails and needs re-execution, the retry comes from this reserve rather than stealing from other phases' allocations.

### 4.6 File Changes

| File | Change |
|------|--------|
| `SKILL.md` | Add parallel dispatch instructions; document `DISPATCH_PARALLEL` state and Worker Pool management |
| `goal-agent.md` | Replace sequential phase loop (Step 3) with group-based dispatch loop; add parallel prompt crafting, spawn, monitor, collect substeps |
| `scripts/goal-agent` (setup) | Add `max_parallel_workers` constraint parsing from goal file; create `snapshots/` directory in run folder; reject parallel groups with overlapping `output_files` |
| `state.json` schema | Add `parallel_dispatch` field with worker array, `group_id`, `max_concurrent`, `completion_policy` |
| Goal file format | Add optional `max_parallel_workers` field to `## Constraints`; add optional `depends_on` field to phase specifications |
| New: `.goal-agent/<run-id>/snapshots/` | Pre-dispatch file snapshots for conflict detection |
| New: `current-prompt-phase-N.md` | Per-phase prompt files (replacing single `current-prompt.md` during parallel dispatch) |

---

## 5. Goal Chaining and Dependency Graphs (Layer 3)

Layer 3 extends the system from isolated, single-goal runs to **Goal Dependency** graphs — directed acyclic graphs of sub-goals where the output of one goal becomes the input context for the next. This enables multi-goal workflows that tackle objectives too large or too varied for a single goal specification.

### 5.1 Problem Statement

Some objectives cannot be expressed as a single goal. Consider "redesign the authentication system." This requires at least four distinct stages, each with different deliverables, verification criteria, and even model requirements:

1. **Audit current auth** — read all auth-related code, produce a report documenting endpoints, middleware, token storage, session handling, and security gaps. Deliverable: `auth-audit.md`. Verification: report covers all auth files, identifies at least N security concerns.
2. **Design new auth** — using the audit as input, produce an architecture spec for the replacement system. Deliverable: `auth-design-spec.md`. Verification: spec addresses every gap from the audit, includes migration strategy.
3. **Implement new auth** — using the design spec as input, write the code. Deliverable: working auth system. Verification: tests pass, endpoints respond correctly.
4. **Write migration guide** — using both the design spec and the implementation as input, produce a migration guide for downstream consumers. Deliverable: `auth-migration-guide.md`. Verification: guide covers every changed endpoint and breaking change.

Each stage is a well-defined goal with its own phases, verification, and budget — but they must execute in order, and each depends on artifacts from the previous stage. In v1, the user manually runs four separate goals, copying context between them. This is error-prone, slow, and loses the orchestrator's ability to reason about the overall objective.

A **Goal Chain** solves this by expressing the four stages as a single meta-goal with declared dependencies. The system executes them in topological order, automatically passing artifacts from completed goals to downstream goals as context.

### 5.2 Goal Dependency Specification Format

A meta-goal is a YAML file (`.meta.yaml`) that defines a **Goal DAG** — a set of sub-goals with dependency relationships. Each sub-goal references an independent goal file (which follows the existing markdown goal format from Section 2.2), plus declarations of which upstream goals it depends on and which artifacts it expects as input.

```yaml
# Meta-goal specification: .goals/redesign-auth.meta.yaml
# (parsed by scripts/goal-agent, not by the orchestrator directly)

title: "Redesign Authentication System"
objective: >
  Replace the legacy session-based auth with JWT-based auth,
  including audit, design, implementation, and migration documentation.

sub_goals:
  - id: audit
    goal_file: .goals/auth-audit.md
    depends_on: []
    produces:
      - artifact: auth-audit-report
        path: .goal-agent/{run-id}/artifacts/auth-audit.md

  - id: design
    goal_file: .goals/auth-design.md
    depends_on:
      - goal: audit
        consumes:
          - artifact: auth-audit-report
            inject_as: context  # appended to the goal's ## Context section
    produces:
      - artifact: auth-design-spec
        path: .goal-agent/{run-id}/artifacts/auth-design-spec.md

  - id: implement
    goal_file: .goals/auth-implement.md
    depends_on:
      - goal: design
        consumes:
          - artifact: auth-design-spec
            inject_as: context
    produces:
      - artifact: auth-code
        path: src/auth/  # directory artifact

  - id: migration-guide
    goal_file: .goals/auth-migration-guide.md
    depends_on:
      - goal: design
        consumes:
          - artifact: auth-design-spec
            inject_as: context
      - goal: implement
        consumes:
          - artifact: auth-code
            inject_as: file_list  # list of changed files, not full content
    produces:
      - artifact: migration-guide
        path: .goal-agent/{run-id}/artifacts/auth-migration-guide.md

constraints:
  max_total_budget_usd: 25.00
  model: sonnet
  allow_parallel_goals: true   # goals with satisfied deps can run concurrently
  on_failure: pause            # pause (default) | skip_failed
```

The `inject_as` field controls how upstream artifacts become downstream context: `context` appends the artifact's content to the goal's `## Context` section before the orchestrator reads it; `file_list` injects only the file paths (useful when the downstream goal should read the files itself rather than receiving a potentially huge dump); `reference` adds a pointer without injecting content (the downstream goal knows the artifact exists and where to find it).

### 5.3 DAG Execution Engine

The meta-goal execution engine is a higher-level orchestrator that manages goal-level dependencies. It uses the same topological sort approach described in Layer 2's phase-level parallelism (Section 4.2), but operates on goals instead of phases. This is an algorithmic reuse, not a requirement that Layer 2 be implemented first.

```python
# Goal DAG execution engine — runs in the meta-orchestrator

class GoalDAGExecutor:
    def __init__(self, meta_goal: MetaGoal):
        self.meta_goal = meta_goal
        self.goal_runs = {}         # goal_id -> run_id
        self.artifact_registry = {} # artifact_name -> ArtifactRecord
        self.status = {}            # goal_id -> "pending"|"running"|"completed"|"failed"

    def execute(self):
        dag = self._build_goal_dag()
        groups = compute_parallel_groups(dag)  # reuse from Layer 2

        for group in groups:
            # Inject upstream artifacts into each goal's context
            for goal_id in group:
                self._inject_artifacts(goal_id)

            if len(group) == 1 or not self.meta_goal.allow_parallel_goals:
                # Sequential execution — one goal at a time
                for goal_id in group:
                    self._run_goal(goal_id)
            else:
                # Parallel execution — leverage Layer 2's Worker Pool
                self._run_goals_parallel(group)

            # After group completes, register produced artifacts
            for goal_id in group:
                if self.status[goal_id] == "completed":
                    self._register_artifacts(goal_id)
                else:
                    self._handle_goal_failure(goal_id, group)

    def _inject_artifacts(self, goal_id: str):
        """
        For each dependency of goal_id, resolve consumed artifacts and
        inject them into a PREPARED COPY of the goal file (never the original).
        """
        goal_spec = self.meta_goal.sub_goals[goal_id]
        prepared = self._prepare_goal_copy(goal_spec.goal_file, goal_id)
        for dep in goal_spec.depends_on:
            for consumed in dep.consumes:
                artifact = self.artifact_registry[consumed.artifact]
                if consumed.inject_as == "context":
                    self._append_to_context(prepared, artifact.content)
                elif consumed.inject_as == "file_list":
                    self._append_to_context(prepared, artifact.file_listing)
                elif consumed.inject_as == "reference":
                    self._append_to_context(prepared, f"See: {artifact.path}")

    def _run_goal(self, goal_id: str):
        """Launch a full goal-agent run for this sub-goal."""
        self.status[goal_id] = "running"
        # Each sub-goal gets its own run-id, session-id, and state.json
        run_id = invoke_goal_agent(
            goal_file=self.meta_goal.sub_goals[goal_id].goal_file,
            budget=self._allocate_budget(goal_id),
        )
        self.goal_runs[goal_id] = run_id
        result = wait_for_completion(run_id)
        self.status[goal_id] = "completed" if result.success else "failed"
```

When `allow_parallel_goals` is true, the executor dispatches independent goals concurrently using the same Worker Pool infrastructure from Layer 2. In the auth example, the `audit` goal runs alone (no dependencies), then `design` runs alone (depends on `audit`), then `implement` runs alone (depends on `design`), then `migration-guide` runs alone (depends on both `design` and `implement`). No parallelism is possible here because the chain is strictly linear. But consider a different meta-goal — "set up monitoring" — with sub-goals: (1) instrument backend, (2) instrument frontend, (3) configure dashboards (depends on 1 and 2). Goals 1 and 2 are independent and run as a **concurrent phase** pair, then goal 3 runs after both complete.

### 5.4 Inter-Goal Artifact Passing

Artifacts are the currency of the **Goal Graph**. Each sub-goal declares what it `produces`, and downstream sub-goals declare what they `consume`. The artifact registry bridges the gap.

An artifact record contains:

- **name** — unique identifier within the meta-goal (e.g., `auth-audit-report`)
- **path** — filesystem path to the artifact (file or directory)
- **type** — `file` (single file), `directory` (all files under a path), or `structured` (JSON data extracted from a file)
- **checksum** — SHA-256 hash of the artifact content at registration time, used to detect if a downstream goal accidentally modifies an upstream artifact
- **produced_by** — goal_id that created it
- **produced_at** — timestamp
- **content** — for `file` type, the full content (cached at registration to avoid re-reading); for `directory` type, a listing of files with sizes

The registry is persisted to `.goal-agent/<meta-run-id>/artifact-registry.json`. When a downstream goal starts, the executor resolves consumed artifacts and injects them into a prepared copy at `.goal-agent/<meta-run-id>/prepared-goals/<goal-id>.md` — the original goal file is never modified.

Artifact injection is size-aware. The executor follows these rules:

- Inline full content only for small text artifacts below a configured threshold.
- Prefer summaries or file listings for medium artifacts.
- Use `reference` mode for large documents, code directories, or any artifact that would consume a material fraction of the downstream prompt budget.

This keeps goal chaining from reintroducing the same context-pressure problem that Layer 1 is trying to control.

Artifact integrity is verified after each sub-goal completes. If the checksum of an upstream artifact has changed (meaning a downstream worker accidentally modified it), the executor flags this as a conflict and pauses for human review. This is the inter-goal equivalent of Section 4.4's conflict detection.

### 5.5 Failure Propagation and Partial Completion

When a sub-goal fails in a **Goal Chain**, the system must decide what to do with downstream goals that depend on it. The failure propagation strategy has three tiers:

**Tier 1: Retry within the goal.** Before propagating failure, the sub-goal's own orchestrator exhausts its retry logic (corrective prompts, plan revision — the existing v1 mechanisms from Section 2.5). Only if the sub-goal's orchestrator declares the goal `failed` does failure propagate to the DAG level.

**Tier 2: Skip dependents.** When a sub-goal fails, all downstream goals that transitively depend on it are marked `skipped`. They cannot execute because their required input artifacts don't exist. Goals that are independent of the failed goal continue executing normally. In the auth example, if `design` fails, both `implement` and `migration-guide` are skipped, but a hypothetical independent goal (e.g., `update-docs-index`) would still run.

**Tier 3: Preserve partial state for resume.** The meta-goal's state file records exactly which sub-goals completed, which failed, and which were skipped. A `resume` command on the meta-goal restarts from the first failed sub-goal, using the artifact registry from the completed goals. This means if `audit` succeeded and produced its artifact, resuming after a `design` failure does not re-run `audit` — the executor reads the artifact registry and finds the audit artifact already available.

The meta-goal state file extends the existing `state.json` schema:

```json
{
  "meta_run_id": "meta-20260405-140000",
  "meta_goal_file": ".goals/redesign-auth.meta.yaml",
  "status": "partial",
  "sub_goals": {
    "audit":           { "status": "completed", "run_id": "20260405-140100", "cost_usd": 1.54 },
    "design":          { "status": "failed",    "run_id": "20260405-141500", "cost_usd": 2.10,
                         "failure_reason": "Verification failed: spec does not address session fixation gap" },
    "implement":       { "status": "skipped",   "blocked_by": "design" },
    "migration-guide": { "status": "skipped",   "blocked_by": "design" }
  },
  "artifact_registry_path": ".goal-agent/meta-20260405-140000/artifact-registry.json",
  "total_cost_usd": 3.64,
  "budget_remaining_usd": 21.36,
  "resumable": true,
  "resume_from": "design"
}
```

When the user runs `goal-agent resume meta-20260405-140000`, the executor loads this state, finds `resume_from: "design"`, injects the `audit` artifact (already registered), and re-runs the `design` sub-goal. If `design` now succeeds, execution continues to `implement` and `migration-guide` as normal.

### 5.6 File Changes

| File | Change |
|------|--------|
| `SKILL.md` | Add meta-goal awareness; document Goal DAG execution as an orchestrator capability |
| `goal-agent.md` | Add meta-goal detection (check for `.meta.yaml` extension); add DAG execution loop alongside existing single-goal loop |
| `scripts/goal-agent` (setup) | Parse `.meta.yaml` format; create `prepared-goals/` and `artifacts/` directories; generate `artifact-registry.json`; support `resume` for meta-goals |
| `state.json` schema | Add `meta_run_id`, `sub_goals` map, `artifact_registry_path`, `resume_from` fields for meta-goal runs |
| Goal file format | No changes — sub-goals use the existing format; the meta-goal format (`.meta.yaml`) is a new file type |
| New: `.meta.yaml` format | Meta-goal specification with sub-goal DAG, artifact declarations, and dependency graph |
| New: `.goal-agent/<meta-run-id>/artifact-registry.json` | Artifact metadata: name, path, type, checksum, producer, timestamp |
| New: `.goal-agent/<meta-run-id>/prepared-goals/` | Modified copies of sub-goal files with injected artifact context |

---

## 6. Self-Generated Verification with Human Approval (Layer 4)

Layer 4 addresses a fundamental asymmetry in the current system: the orchestrator can decompose objectives, craft prompts, and evaluate results — but it relies entirely on the goal author to anticipate what "correct" looks like. This layer gives the orchestrator the ability to propose its own verification checks, subject to human approval before any execution begins.

### 6.1 Problem Statement

Verification commands are the hardest part of goal files to write well. The goal author must anticipate the output structure before any work has been done — predicting file paths, section headings, word counts, and behavioral properties of artifacts that don't yet exist. In practice, most authors default to structural checks: `test -f output.md`, `grep -c "## " output.md`, `wc -w output.md | awk '{print ($1 >= 500)}'`. These catch gross failures (file missing, empty document) but miss semantic gaps (a section that exists but says nothing useful, a code block that's syntactically valid but logically wrong, a document that hits word count by padding).

Production data confirms this: the three v1 runs used 19-20 checks each, nearly all structural or quantitative. None checked internal consistency, code block validity, or cross-reference resolution. The verification passed — but it verified the skeleton, not the substance.

The system should generate deeper checks by analyzing the objective. An orchestrator that understands "write a design spec with code examples" should propose checks like "every code block parses without syntax errors" — checks the author would write with unlimited patience.

### 6.2 Verification Generation Strategy

The orchestrator generates verification checks during the DECOMPOSE state, after reading the goal file but before dispatching any worker calls. The generation follows a four-category analysis of the objective:

**Structural checks** verify that expected artifacts exist with the right shape. These are the easiest to generate and most reliable: file existence, section headings, required subsections.

**Semantic checks** verify content quality through keyword and pattern detection. For a design spec, this means checking that technical terms from the objective appear in the output. For code goals, checking that function names match the specification.

**Quantitative checks** verify measurable properties: word counts, code block counts, table row counts, heading depth. These are derived from any explicit constraints in the goal file plus reasonable defaults for the goal type.

**Behavioral checks** verify that generated artifacts actually work: scripts execute without error, JSON parses correctly, markdown renders without broken links. These are the highest-value checks but also the least reliable to auto-generate.

```python
# Verification generation pipeline — runs during DECOMPOSE state
# Input: parsed goal file (objective, constraints, existing verification commands)
# Output: list of proposed checks with confidence scores

def generate_verification_checks(goal):
    proposed = []

    # 1. Structural: infer expected files and sections from objective
    for deliverable in goal.extract_deliverables():
        proposed.append(Check(
            command=f'test -f "{deliverable.path}"',
            category="structural",
            confidence=0.95,
            rationale=f"Objective explicitly names {deliverable.path} as a deliverable"
        ))
        if deliverable.type == "markdown":
            for section in deliverable.infer_sections():
                proposed.append(Check(
                    command=f'grep -q "## {section}" "{deliverable.path}"',
                    category="structural",
                    confidence=0.7,
                    rationale=f"Section '{section}' implied by objective structure"
                ))

    # 2. Semantic: extract key terms from objective for content verification
    key_terms = goal.extract_technical_terms()
    for term in key_terms[:10]:  # cap to avoid check explosion
        proposed.append(Check(
            command=f'grep -qi "{term}" "{goal.primary_deliverable}"',
            category="semantic",
            confidence=0.6,
            rationale=f"Term '{term}' is central to the objective"
        ))

    # 3. Quantitative: derive from constraints or goal-type defaults
    if goal.has_word_count_constraint():
        min_words, max_words = goal.word_count_range()
        proposed.append(Check(
            command=f'word_count=$(wc -w < "{goal.primary_deliverable}"); '
                    f'[ "$word_count" -ge {min_words} ] && [ "$word_count" -le {max_words} ]',
            category="quantitative",
            confidence=0.9,
            rationale=f"Goal specifies {min_words}-{max_words} word range"
        ))

    # 4. Behavioral: if deliverable is code or script, verify it parses
    SYNTAX_CHECKERS = {
        "python": 'python3 -c "import ast; ast.parse(open(\'{path}\').read())"',
        "bash":   'bash -n "{path}"',
        "javascript": 'node --check "{path}"',
    }
    for deliverable in goal.extract_deliverables():
        if deliverable.type in SYNTAX_CHECKERS:
            proposed.append(Check(
                command=SYNTAX_CHECKERS[deliverable.type].format(path=deliverable.path),
                category="behavioral",
                confidence=0.8,
                rationale=f"Verify {deliverable.path} is syntactically valid"
            ))

    # Deduplicate against existing human-written checks
    existing = set(normalize(c) for c in goal.verification_commands)
    proposed = [p for p in proposed if normalize(p.command) not in existing]

    return proposed
```

### 6.3 Human Approval Gate for Generated Checks

Generated checks are **proposals, not decisions**. The orchestrator presents them to the human before any worker dispatch occurs. This is a hard gate — no auto-generated check executes without explicit approval.

The approval UX renders in the orchestrator's interactive output. Each proposed check is displayed with its category, confidence score, and the rationale for why it was generated. The human can approve, modify, or reject each check individually:

```
┌─ Auto-Generated Verification Proposals ─────────────────────┐
│                                                              │
│ [✓] structural (0.95) test -f "auth-design-spec.md"         │
│     → Objective names this as primary deliverable            │
│                                                              │
│ [✓] semantic (0.60) grep -qi "JWT" "auth-design-spec.md"    │
│     → "JWT" is a key technical term in the objective         │
│                                                              │
│ [?] behavioral (0.80) bash -n "migrate.sh"                   │
│     → Verify migration script parses without errors          │
│                                                              │
│ Actions: [a]pprove all  [r]eject all  [1-N] toggle/edit     │
└──────────────────────────────────────────────────────────────┘
```

The approval prompt is rendered by the orchestrator via its interactive session. Since the orchestrator is a Claude Code session running in tmux, it uses standard output with a structured format the human reads and responds to.

**Timeout and background behavior:** In foreground mode, the orchestrator waits for the human's response. If no response within 120 seconds, the conservative default applies: checks with confidence ≥ 0.85 are auto-approved; all others are dropped. In `--background` (tmux) mode, the orchestrator writes proposals to `.goal-agent/<run-id>/verification-proposals.json` and pauses the run (status: `awaiting_approval`). The human reviews proposals via `goal-agent approve <run-id>` from any terminal. This avoids auto-approving checks in a session the human may not be watching. Timeout and threshold are configurable in the goal file's `## Constraints` section.

### 6.4 Confidence Scoring and Check Prioritization

Not all generated checks are equally trustworthy. A file-existence check derived from an explicitly named deliverable is near-certain to be valid. A semantic keyword check inferred from the objective's prose might be irrelevant if the orchestrator misidentified a key term.

Confidence scores range from 0.0 to 1.0. The pseudocode in Section 6.2 uses simplified fixed values for illustration; the full scoring model weights four factors:

- **Derivation directness** (0.3 weight): Was the check derived from an explicit statement in the goal file (high) or inferred from the objective's language (low)?
- **Category reliability** (0.3 weight): Structural checks are inherently more reliable than semantic ones. Behavioral checks are reliable when the deliverable type is known.
- **Specificity** (0.2 weight): A check for a specific file path is more reliable than a check for a keyword pattern.
- **Historical accuracy** (0.2 weight): If cross-run learning (Layer 5) is active, past accuracy rates for similar check types adjust the score.

Checks are sorted by confidence descending. During the approval gate, high-confidence checks (≥ 0.85) are pre-selected for approval; medium-confidence checks (0.5–0.84) are shown but unselected; low-confidence checks (< 0.5) are shown with a warning. This lets the human quickly approve a batch of good checks without reviewing every one.

### 6.5 Integration with Existing Verification Flow

Auto-generated checks **supplement** human-written checks — they never replace or override them. The merge strategy is:

1. Human-written checks from `## Verification` are loaded first and marked `source: human`.
2. Generated checks are deduped against human checks (normalized command comparison).
3. Approved generated checks are appended with `source: auto-generated, confidence: N`.
4. During verification execution, human checks run first. If any human check fails, auto-generated checks are skipped (the phase already failed on author-defined criteria).

The approved generated checks are persisted to run state and to a prepared copy of the goal under `.goal-agent/<run-id>/prepared-goal.md`. This makes the run reproducible without violating the rule from Section 2.2 that the source goal file is immutable.

```json
{
  "auto_verification": {
    "approved": [
      {
        "command": "grep -qi \"JWT\" \"auth-design-spec.md\"",
        "category": "semantic",
        "confidence": 0.60,
        "approved_by": "human",
        "approved_at": "2026-04-01T16:05:00Z"
      }
    ]
  }
}
```

### 6.6 File Changes

| File | Change |
|------|--------|
| `SKILL.md` | Add verification generation instructions; document the PROPOSE_VERIFICATION state and approval protocol |
| `goal-agent.md` | Add verification generation step between goal parsing and DECOMPOSE; add approval gate rendering and timeout handling |
| `scripts/goal-agent` (setup) | Parse existing `## Verification`; merge approved generated checks from run state or prepared-goal metadata during state initialization |
| `state.json` schema | Add `auto_verification` field with proposed checks array, approval status, confidence scores, and timeout config |
| Prepared goal artifact | Persist approved generated checks in `.goal-agent/<run-id>/prepared-goal.md` or adjacent run metadata |

---

## 7. Cross-Run Learning (Layer 5)

Layer 5 closes the feedback loop. Every completed goal-agent run produces rich outcome data — which decomposition strategies worked, how many iterations each phase required, which verification checks caught real problems, how budget was distributed. Currently, all of this is written to `state.json` and never read again. This layer extracts patterns from historical runs and feeds them into the orchestrator's planning for future goals.

### 7.1 Problem Statement

Each goal-agent run starts from scratch. The orchestrator decomposes objectives using only the goal file and its general reasoning — it has no memory of what worked before. If a 6-phase document-synthesis goal completed perfectly on the first attempt, the next document-synthesis goal doesn't benefit from that experience. If a particular prompt pattern ("write section N, focusing on X, referencing the output of section N-1") consistently produces clean first-pass results, there's no mechanism to reuse it.

This is especially costly for failure patterns. If a certain type of decomposition reliably causes phase 3 to fail (e.g., splitting a document into sections without specifying cross-references between them), the orchestrator will make the same mistake on every similar goal. The three production runs to date show zero plan revisions — but that's a small sample with well-specified goals. As goals become more ambitious and less precisely specified, decomposition failures will become common, and the system needs to learn from them rather than repeat them.

### 7.2 Run Outcome Data Model

Every completed run produces a **run outcome record** that captures the decision points, execution metrics, and quality signals needed for pattern extraction. The record is derived from the existing `state.json` but restructured for analytical querying.

```jsonc
// .goal-agent/.learning/outcomes/<run-id>.json
{
  "run_id": "20260401-150019-a3b2c1d4",
  "goal_type": "document-synthesis",     // classified post-hoc or from goal metadata
  "goal_hash": "sha256:abc123...",       // content hash of the goal file for dedup
  "model": "opus",
  "timestamp": "2026-04-01T15:00:19Z",
  "outcome": "success",                  // success | partial | failed
  "budget": { "limit": 10.0, "actual": 7.34 },
  "decomposition": {
    "strategy": "sequential-sections",   // label for the decomposition approach
    "phase_count": 6,
    "phases": [
      {
        "index": 0,
        "description": "Write executive summary and introduction",
        "iterations": 1,
        "verification_pass_rate": 1.0,
        "duration_seconds": 142,
        "prompt_tokens": 2400,
        "prompt_pattern": "section-with-context"  // classified prompt style
      }
      // ... one entry per phase
    ],
    "revisions": 0
  },
  "verification": {
    "total_checks": 20,
    "human_written": 18,
    "auto_generated": 2,
    "pass_rate": 1.0,
    "checks_that_caught_failures": []    // which checks actually failed, then passed on retry
  },
  "failure_modes": []                    // structured list of what went wrong, if anything
}
```

The outcome record is written by the orchestrator at run completion (in the COMPLETE or FAILED terminal states). It supplements — not replaces — the existing `state.json`, which remains the live state file during execution.

### 7.3 Pattern Extraction from Historical Runs

Pattern extraction runs as a batch process over the outcome registry, triggered either manually (`goal-agent learn`) or automatically after every N completed runs (configurable, default: 3). The extraction algorithm clusters runs by goal type, then identifies which strategies correlate with success.

**Goal type classification** uses a simple heuristic applied to the goal file's objective text: goals mentioning "spec," "document," "report," or "guide" are classified as `document-synthesis`; goals mentioning "implement," "build," "refactor," or "fix" are `code-implementation`; goals mentioning "audit," "review," or "analyze" are `analysis`. A goal can have multiple type tags. Classification is stored in the outcome record and can be corrected by the human.

**Strategy correlation** compares decomposition approaches within each goal type. For document-synthesis goals, the system tracks whether sequential-sections (one phase per section) outperforms holistic-then-refine (draft everything, then polish). "Outperforms" is defined by: fewer iterations per phase, higher first-pass verification rates, and lower cost relative to output size.

```python
# Pattern extraction — runs over outcome registry
# Input: list of RunOutcome records
# Output: updated learning registry with strategy recommendations

def extract_patterns(outcomes):
    registry = load_learning_registry()

    # Cluster by goal type
    by_type = defaultdict(list)
    for outcome in outcomes:
        by_type[outcome.goal_type].append(outcome)

    for goal_type, runs in by_type.items():
        if len(runs) < 3:
            continue  # not enough data to extract patterns (matches consultation threshold)

        # Rank decomposition strategies by composite score
        strategy_scores = defaultdict(list)
        for run in runs:
            score = compute_strategy_score(
                pass_rate=run.verification.pass_rate,
                iterations_per_phase=mean(p.iterations for p in run.decomposition.phases),
                budget_efficiency=run.budget.actual / run.budget.limit,
                revision_count=run.decomposition.revisions
            )
            strategy_scores[run.decomposition.strategy].append(score)

        # Update registry with best-performing strategies
        best = max(strategy_scores, key=lambda s: mean(strategy_scores[s]))
        registry.update_recommendation(
            goal_type=goal_type,
            recommended_strategy=best,
            confidence=len(strategy_scores[best]) / len(runs),
            sample_size=len(runs)
        )

        # Extract prompt patterns that correlate with single-iteration phases
        single_iter_prompts = [
            p.prompt_pattern for run in runs
            for p in run.decomposition.phases
            if p.iterations == 1
        ]
        if single_iter_prompts:
            most_common = Counter(single_iter_prompts).most_common(1)[0][0]
            registry.update_prompt_recommendation(goal_type, most_common)

    save_learning_registry(registry)
    return registry
```

### 7.4 Decomposition Heuristics and Goal Classification

When the orchestrator enters the DECOMPOSE state for a new goal, it consults the learning registry before generating its plan. The lookup flow:

1. **Classify the new goal** using the same heuristic as pattern extraction.
2. **Query the registry** for the goal type's recommended strategy and prompt patterns.
3. **If a recommendation exists with confidence ≥ 0.6 and sample size ≥ 3**, include it in the orchestrator's decomposition prompt as a strong suggestion: "Historical data shows that `sequential-sections` with `section-with-context` prompts produces the best outcomes for document-synthesis goals."
4. **If a recommendation exists but confidence is low**, include it as a weak signal: "Limited data suggests trying X, but adapt as needed."
5. **If no recommendation exists** (new goal type or insufficient data), decompose from first principles as in v1.

The registry is advisory, not prescriptive. The orchestrator can override recommendations based on goal-specific factors. If the recommendation leads to a failed run, that failure is itself recorded and will lower the recommendation's confidence on the next extraction cycle — a self-correcting feedback loop.

### 7.5 Integration with Autoresearch Ratchet

The goal-agent skill already participates in Flow's autoresearch system. The `manifest.yaml` configures `metric_layer: 1` (basic quality metrics) and `evaluation_window: 3` (evaluate over the last 3 runs). The `trace_capture.py` script captures execution traces at quality gates, feeding into the ratchet's performance tracking.

Cross-run learning extends this integration in two ways:

**Outcome records feed the ratchet.** When a run outcome record is written, a summary trace is also emitted via `trace_capture.py capture` with the run's composite score (pass rate × budget efficiency). This means the autoresearch system can detect when the goal-agent skill's overall quality is trending up or down — and trigger research cycles when performance degrades.

**Ratchet thresholds gate learning updates.** The learning registry should only be updated when the underlying data is trustworthy. If the autoresearch ratchet detects that recent runs are below the quality threshold (e.g., pass rates dropping), the pattern extraction pipeline skips the update cycle rather than learning from degraded runs. This prevents the system from encoding failure patterns as recommendations.

The connection point is the existing `evaluation_window: 3` config. The pattern extraction trigger ("run after every 3 completions") aligns with the ratchet's evaluation window, so both systems analyze the same data cohort.

### 7.6 File Changes

| File | Change |
|------|--------|
| `SKILL.md` | Document cross-run learning as an orchestrator capability; describe the learning registry consultation during DECOMPOSE |
| `goal-agent.md` | Add registry lookup step at the start of DECOMPOSE; add outcome record writing at COMPLETE/FAILED states; add `learn` subcommand instructions |
| `scripts/goal-agent` (setup) | Create `.goal-agent/.learning/` directory structure; add `learn` subcommand for manual pattern extraction; add outcome record serialization at run completion |
| `state.json` schema | Add `learning_recommendation` field capturing the registry advice used for this run's decomposition |
| New: `.goal-agent/.learning/outcomes/<run-id>.json` | Per-run outcome records for historical analysis |
| New: `.goal-agent/.learning/registry.json` | Aggregated strategy recommendations by goal type, prompt pattern rankings, and confidence scores |
| `manifest.yaml` | Add `learning_extraction_interval: 3` to autoresearch config for alignment with evaluation window |

---

## 8. Implementation Sequence

Layers are ordered for operational sanity, but not all are hard prerequisites. The sequencing below distinguishes hard dependencies from recommended implementation order so independent value can ship earlier.

### 8.1 Layer Ordering and Dependencies

| Layer | Name | Depends On | Why |
|-------|------|------------|-----|
| 1 | Delegation Enforcement | None (foundation) | All layers inherit orchestrator identity; if delegation fails, parallelism and chaining amplify the failure |
| 2 | Multi-Worker Parallelism | Layer 1 | Spawning multiple workers requires a delegation-stable orchestrator; without it, the orchestrator may attempt to do workers' jobs |
| 3 | Goal Chaining | Layer 1 | Chaining requires stable delegation and run-state contracts; it can execute sequentially before parallel goal dispatch exists |
| 4 | Self-Generated Verification | Layer 1 | Generated checks can augment single-goal sequential runs; awareness of chains/parallelism is an enhancement, not a prerequisite |
| 5 | Cross-Run Learning | Layer 1 | Learning can start from sequential single-goal runs and expand as new execution modes arrive |

### 8.2–8.6 Phased Implementation Plan

| Phase | Layer | Key Deliverables | Effort | Prerequisites |
|-------|-------|-----------------|--------|---------------|
| 1 | Delegation Enforcement | • `identity.json` anchor file + `runtime-policy.json` for run-scoped policy | partially scaffolded | None |
| | | • External structural delegation guard (block direct non-state writes and non-whitelisted shell actions) | not yet enforced end-to-end | |
| | | • Role reinforcement protocol injecting identity every N phases | partially scaffolded in state, not yet runtime-complete | |
| 2 | Multi-Worker Parallelism | • Dependency graph parser in `plan.md` format (`depends_on` field) | largely absent | Phase 1 actually enforced |
| | | • Worker pool with configurable concurrency, spawn/monitor/collect loop | absent | |
| | | • `parallel_dispatch` field in `state.json`, conflict detection via pre-dispatch snapshots | state field scaffolded; runtime absent | |
| 3 | Goal Chaining | • Meta-goal file format with `goals:` sequence and `depends_on` references | partially scaffolded | Phase 1 actually enforced |
| | | • Chain orchestrator state machine (SELECT → DISPATCH → GATE → NEXT) | absent | |
| | | • Artifact passing via `outputs → inputs` declarations between goals | absent | |
| 4 | Self-Generated Verification | • Verification proposal step after DECOMPOSE, producing candidate checks | partially scaffolded | Phase 1 actually enforced |
| | | • Human approval gate for proposed checks (persisted in run state / prepared goal artifacts) | partially scaffolded | |
| | | • Coverage analysis comparing proposed checks against plan phases | absent | |
| 5 | Cross-Run Learning | • Outcome record serialization at run completion (`outcomes/<run-id>.json`) | partially scaffolded | Phase 1 actually enforced |
| | | • Registry aggregation computing strategy recommendations by goal type | partially scaffolded | |
| | | • Registry consultation during DECOMPOSE with confidence-weighted suggestions | absent | |

The earlier ~19 day estimate assumes a stable runtime foundation that the repo does not yet have. In practice, the first meaningful work item is to complete and validate Layer 1. No reliable end-to-end estimate for Layers 2-5 should be trusted until that foundation exists.

**Validation strategy per layer:** Each layer is tested using the existing trivial test goal (`templates/test-trivial-goal.md`) plus a layer-specific stress goal. Layer 1: run a 10+ phase goal and verify the external policy layer blocks any orchestrator write outside `.goal-agent/`. Layer 2: run a goal with 3 declared-independent phases and verify parallel dispatch only occurs when `output_files` are disjoint. Layer 3: run a 2-goal chain where goal B consumes goal A's artifact and verify large artifacts are passed by reference rather than inline dump. Layer 4: run a goal with `auto_verify: true` and verify the approval gate fires without mutating the source goal file. Layer 5: run 3+ goals of the same type and verify registry recommendations appear.

### 8.7 Migration Path from v1

Existing v1 goal files should remain compatible. However, the current repository should not claim that full v2 fallback behavior already exists. Today, the safe claim is narrower: goal parsing and run setup remain backward-compatible, and some v2-oriented artifacts are generated opportunistically. Stronger statements about automatic fallback across Layers 2-5 should only be made once the actual runtime paths exist.

---

## 9. Risk Analysis and Failure Modes

### 9.1 Orchestrator Complexity Explosion

Each layer adds state, transitions, and decision logic to the orchestrator's context window. By Layer 5, the orchestrator must simultaneously manage delegation guards, parallel worker pools, chain state, verification proposals, and learning consultations. The mitigation is Layer 1's identity anchoring and external policy enforcement — the orchestrator's core role is reinforced from disk while enforcement lives outside the compressed prompt — combined with aggressive state externalization to `state.json` so the orchestrator can reconstruct its position from disk rather than relying on in-context memory.

### 9.2 Parallel Worker Conflicts

Two workers writing overlapping files produce corrupted output. The file-disjoint scheduling rule (Section 4.4) prevents same-file parallelism structurally, and post-completion diff analysis catches undeclared file modifications. The residual risk is workers that modify shared infrastructure files (e.g., `package.json`) as a side effect. Mitigation: the orchestrator's worker prompts explicitly list forbidden files, and the conflict detector flags any modifications outside declared output files as hard errors requiring sequential re-run.

### 9.3 Goal Chain Cascading Failures

A failed goal in a chain blocks all downstream dependents, potentially wasting the work of already-completed goals. Mitigation: chains use the `on_failure: pause` default, halting at the failed goal and preserving all prior artifacts. The chain can be resumed after manual intervention. The `skip_failed` policy exists for chains where downstream goals can operate with degraded inputs, but it requires explicit opt-in.

### 9.4 Verification Hallucination

Auto-generated verification checks (Layer 4) may test the wrong thing — e.g., writing a grep that matches boilerplate instead of substance. Mitigation: all proposed checks require human approval with rationale. In foreground mode, only checks with confidence ≥ 0.85 auto-approve on timeout; in background mode, no auto-approval occurs (Section 6.3).

### 9.5 Learning System Overfitting

With fewer than ~10 runs, the learning registry lacks statistical significance. A single successful 4-phase run could bias all future recommendations toward 4-phase plans. Mitigation: confidence scores reflect sample size, and recommendations below threshold (default: 3 matching runs) are presented as suggestions, not defaults. The `goal-agent learn --reset` command clears the registry if patterns become counterproductive.

### 9.6 Budget and Cost Control at Scale

Three parallel workers with a $3.60 group envelope can exhaust it before a human notices one is misbehaving. With chaining (5 goals × 3 workers), a meta-goal could consume $20+ before completion. Mitigation: per-worker budget caps are hard limits via `--max-budget-usd`; the chain orchestrator tracks cumulative spend after each worker and group completes and pauses if total exceeds the meta-goal's budget. Real-time spend monitoring is explicitly out of scope unless the worker runtime exposes incremental telemetry.

### 9.7 Mitigation Matrix

| Risk | Likelihood | Impact | Primary Mitigation | Fallback |
|------|-----------|--------|-------------------|----------|
| Orchestrator complexity explosion | Medium | High | Identity anchoring + external policy enforcement + state externalization | Disable higher layers, run in v1 mode |
| Parallel worker conflicts | Medium | Medium | File-disjoint scheduling + diff detection | Sequential fallback for conflicting phases |
| Goal chain cascading failures | Low | High | `on_failure: pause` + artifact preservation | Manual intervention, partial chain resume |
| Verification hallucination | Medium | Low | Human approval gate for all proposed checks | Revert to author-defined checks only |
| Learning system overfitting | High (early) | Medium | Confidence thresholds + minimum sample size | `goal-agent learn --reset` |
| Budget overrun at scale | Low | High | Per-worker hard caps + cumulative chain budget | Auto-pause at 80% budget consumed |

---

## Appendix A: File Change Inventory

### A.1 New Files

| File | Purpose | Created By |
|------|---------|------------|
| `.goal-agent/<run-id>/identity.json` | Compression-resistant orchestrator identity anchor | Layer 1 setup |
| `.goal-agent/<run-id>/runtime-policy.json` | Run-scoped machine-enforced policy for orchestrator actions | Layer 1 setup |
| `.goal-agent/<run-id>/snapshots/` | Pre-dispatch file copies for conflict detection | Layer 2 parallel dispatch |
| `goals/<name>.meta.yaml` | Meta-goal files declaring goal chains with dependencies | Layer 3 chain runner |
| `.goal-agent/.learning/outcomes/<run-id>.json` | Per-run outcome records (timing, phases, result) | Layer 5 run completion |
| `.goal-agent/.learning/registry.json` | Aggregated strategy recommendations by goal type | Layer 5 learning extraction |

### A.2 Modified Files

| File | Changes |
|------|---------|
| `SKILL.md` | Add identity reinforcement protocol, parallel dispatch instructions, chain orchestration rules, verification proposal step, learning registry consultation |
| `goal-agent.md` | Add `DISPATCH_PARALLEL` and `CHAIN_SELECT` states, registry lookup in DECOMPOSE, `learn` subcommand, verification proposal step after DECOMPOSE |
| `scripts/goal-agent` | Create identity.json and runtime-policy.json at run start, route orchestrator actions through policy enforcement, snapshot files before parallel dispatch, serialize outcome records, add `learn` and `approve` subcommands, cumulative budget tracking |
| `manifest.yaml` | Add `learning_extraction_interval` to autoresearch config |

### A.3 State Schema Changes

New fields added to `state.json`:

| Field | Type | Layer | Purpose |
|-------|------|-------|---------|
| `orchestrator_state` | string | 1 | Current state machine position (CRAFT_PROMPT, CALL_WORKER, etc.) |
| `delegation_count` / `direct_action_count` | number | 1 | Delegation ratio tracking |
| `role_reinforcement_interval` | number | 1 | Phases between identity checkpoints (default: 2) |
| `parallel_dispatch` | object | 2 | Worker pool state (workers, statuses, budgets) |
| `chain_state` | object | 3 | Current position in meta-goal chain |
| `auto_verification` | object | 4 | Generated checks, approval status, confidence scores |
| `learning_recommendation` | object | 5 | Registry advice used for this run's decomposition |
| `cumulative_spend_usd` | number | 2+ | Total spend across all workers and chain goals |

### A.4 Goal File Format Extensions

New optional sections (absence triggers v1 behavior):

| Section/Field | Location | Layer | Example |
|---------------|----------|-------|---------|
| `depends_on` in phase | `## Plan` phase entries | 2 | `depends_on: [1, 2]` |
| `max_parallel_workers` | `## Constraints` | 2 | `max_parallel_workers: 3` |
| `goals:` sequence | Meta-goal file header | 3 | `goals: [auth.md, dashboard.md]` |
| `outputs` / `inputs` | Goal file metadata | 3 | `outputs: [api-spec.md]` |
| `auto_verify: true` | `## Verification` | 4 | Enables orchestrator-proposed checks |
