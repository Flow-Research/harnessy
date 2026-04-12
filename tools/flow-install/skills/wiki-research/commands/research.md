# wiki-research/commands/research.md

> Phase specification for the `wiki-research` skill. The orchestrator (`jarvis-cli/src/jarvis/wiki/research.py`) implements these phases. The autoflow ratchet reads the gate outcomes from traces.

## Phases

### Phase 1 — Target Selection (gate: `target_selection`)

**Goal:** pick the next thing to research.

**Inputs:**
- `<domain>/program.md` (active topics, avoid topics, cadence)
- `<domain>/seeds.md` (pending user-supplied URLs/topics/notes)
- CLI flags: `--topic`, `--seeds-only`

**Procedure:**
1. Load program and seeds.
2. If `--seeds-only`, pick the highest-priority pending seed.
3. Otherwise: if `--topic` is given, use it verbatim. Else if pending seeds exist, prefer them. Else pick the highest-depth program topic with the oldest `last_researched`.

**Gate outcome:**
- `approved` (loops=0): a non-trivial target was selected
- `rejected` (loops=1): no targets available (empty program AND empty seeds)

### Phase 2 — Agent Session (gate: `agent_session`)

**Goal:** spawn the Claude agent and let it search/fetch.

**Inputs:**
- The rendered prompt template (`agents/research_agent_prompt.md`)
- Allowed dirs: `<domain>/` (read), `<domain>/raw/articles/` (write)
- Allowed tools: `WebSearch`, `WebFetch`, `Read`, `Write`, `Glob`, `Grep`, `LS`
- Max turns: `25` (configurable)
- Timeout: `1800s`

**Procedure:**
1. Snapshot `raw/articles/` filenames before spawn.
2. Invoke `claude -p --allowed-tools ... --max-turns N --output-format json` with the prompt on stdin.
3. Parse the trailing JSON envelope from the agent's output.
4. Diff `raw/articles/` after to detect actual file deltas (trust the filesystem, not the agent's claims).

**Gate outcome:**
- `approved` (loops=0): subprocess exited cleanly, JSON envelope parsed, no `agent_session_failed` error
- `rejected` (loops=1): any of those failed

### Phase 3 — File Validation (gate: `file_validation`)

**Goal:** ensure each new file in `raw/articles/` is well-formed.

**Procedure:** for each new file:
1. Check it exists and is at least 200 bytes
2. Check it has YAML frontmatter
3. Check the frontmatter contains `source_url:` and `research_session:`

**Gate outcome:**
- `approved` (loops=0): zero files rejected
- `rejected` (loops=N): N = number of files that failed validation

### Phase 4 — Compilation (gate: `compilation`)

**Goal:** the new files compile cleanly into the wiki.

**Procedure:**
1. Run `WikiCompiler.compile()` on the new files (incremental — hash check skips unchanged sources).
2. Read the compile stats: `sources_compiled`, `concepts_created`, `concepts_updated`, `concepts_aliased`, `errors`.

**Gate outcome:**
- `approved` (loops=0): `len(errors) == 0`
- `rejected` (loops=1): any compile error

### Phase 5 — Dedup Check (gate: `dedup_check`)

**Goal:** the new concepts didn't introduce duplicates of existing ones.

**Procedure:**
1. Run `WikiLinter.lint()` after the compile pass.
2. Filter `duplicate_concept` warnings whose article slug was modified during this session (mtime ≥ session start).
3. Count = number of new duplicate-concept warnings introduced.

**Gate outcome:**
- `approved` (loops=0): zero new duplicate warnings
- `rejected` (loops=N): N = new duplicate warnings introduced

This is the most important quality signal. The dedup logic in Track 1 is supposed to prevent these — if the agent's prompt tells it to ignore the index, this gate will catch the regression and the ratchet will revert.

## Hard Constraint Vetoes

The ratchet rejects any improvement (regardless of score) that breaches:
- **new duplicate_concept warnings > 0** for ≥1 session in the evaluation window
- **agent_session rejection rate > 30%** over the evaluation window
- **file_validation rejection rate > 50%** over the evaluation window
- **compilation errors > 10%** of sessions in the evaluation window

## Auto-Improvement Triggers

The ratchet fires an improvement cycle when, over the most recent 5 sessions:
- `dedup_check` average loops > 0.2 → propose tighter agent prompt or stronger `is_same_entity` prompt
- `file_validation` average loops > 0.5 → propose clearer file format instructions in the agent prompt
- `compilation` first-pass rate < 0.8 → propose better source-quality filtering in the agent prompt
- `target_selection` rejection rate > 0 with non-empty program → bug in selection logic, escalate (don't auto-improve — this is fixed infrastructure)
