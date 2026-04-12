---
name: wiki-research
description: Autonomous research orchestrator for Jarvis Wiki domains. Spawns a Claude agent with web tools to find new sources, drops them into raw/, runs the compile pipeline, and emits autoresearch traces for the autoflow ratchet.
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
argument-hint: "<domain>"
---

# wiki-research — Autonomous Research for Jarvis Wikis

## Purpose

Turn a Jarvis Wiki domain from a passive knowledge base (you ingest, it compiles) into an active autoresearch agent (it goes out and finds the sources itself, governed by per-domain steering and seeded inputs). This skill is the autoflow-discoverable wrapper around the implementation in `jarvis-cli/src/jarvis/wiki/research.py`.

## How It Works

1. **Read the steering surface** — `<domain>/program.md` (active topics, source preferences, thresholds, cadence)
2. **Read the seed queue** — `<domain>/seeds.md` (user-supplied URLs/topics/notes; pending entries get processed first)
3. **Pick a target** — pending seeds win, then highest-depth program topic with oldest `last_researched`
4. **Spawn a Claude agent** — `claude -p` with `WebSearch`, `WebFetch`, `Read`, `Write`, `Glob`, `Grep`, `LS` enabled and explicit `--add-dir` access
5. **Validate** — every file the agent dropped into `raw/articles/` must have `source_url:` and `research_session:` in its frontmatter
6. **Compile** — `WikiCompiler.compile()` runs on the new files; existing entity-dedup (Track 1) prevents new duplicates
7. **Mark consumed seeds** — entries the agent reported as processed get moved from Pending → Processed in `seeds.md`
8. **Capture traces** — five gate traces per session (`target_selection`, `agent_session`, `file_validation`, `compilation`, `dedup_check`) for the autoflow ratchet

## Approval Checkpoints

This skill currently runs unattended. Human review happens via the morning brief surfacing findings, and via the user editing `program.md` to change direction. Future work: add a `review_findings` human gate that pauses sessions when the agent flags low-confidence merges or source conflicts.

## Inputs

- Domain name (required)
- `--topic <name>` (optional, overrides program selection)
- `--max-sources <N>` (optional, overrides program cap)
- `--seeds-only` (optional, ignore program topics)
- `--max-turns <N>` (optional, default 25)
- `--dry-run` (optional, build the prompt without spawning the agent)
- `--auto-compile/--no-auto-compile` (optional, default on)

## Steps

1. Follow the phase specification in `commands/research.md` exactly.
2. Always read `<domain>/program.md` and `<domain>/seeds.md` before each session.
3. Never modify `program.md`, `seeds.md`, `compiler.py`, `lint.py`, `parser.py`, or `_shared/*.py` — these are fixed evaluation infrastructure.
4. The editable surface (what the autoflow ratchet may mutate) is:
   - `jarvis-cli/src/jarvis/wiki/agents/research_agent_prompt.md`
   - `jarvis-cli/src/jarvis/wiki/prompts.py` (specifically `IS_SAME_ENTITY_*` and prompts that affect dedup quality)
5. Capture traces for every session via `WikiResearcher._capture_traces()`.
6. Use `tools/flow-install/skills/_shared/ratchet.py` for all keep/revert decisions.

## Output

- Per-session audit trail at `<domain>/.state/research-sessions/<session-id>/` (prompt.txt, output.txt, output.json, findings.md)
- Flat findings file at `<domain>/.state/findings/YYYY-MM-DD-<session-id>.md` (read by life-orchestrator's daily brief)
- Gate traces at `~/.agents/traces/wiki-research/traces.ndjson`
- Updated `seeds.md` with consumed entries moved to Processed
- New raw files at `<domain>/raw/articles/<date>-<slug>.md` with provenance frontmatter
- Compiled concepts/summaries via the existing `WikiCompiler` pipeline
- Append-only `[ENHANCE]` log entries in `<domain>/wiki/log.md`

## The Autoresearch Protocol

See `${AGENTS_SKILLS_ROOT}/_shared/autoresearch.md` for the full protocol specification (three-file contract, metric layers, adoption checklist).

This skill applies the same pattern as autoflow but to wiki research instead of issue processing:

| Layer | autoflow | wiki-research |
|---|---|---|
| Editable | issue-flow phase prompts | agent prompt template + dedup prompts |
| Fixed | `_shared/*.py`, `_shared/ratchet.py` | `compiler.py`, `lint.py`, `parser.py`, `research.py`, `_shared/*.py` |
| Human | `program.md` at repo root | `<domain>/program.md` + `<domain>/seeds.md` |

The ratchet's keep/revert decisions apply to changes in the editable surface only. Bugs in the orchestrator or compiler are escalated, not auto-improved.

## Metric (Layer 1)

```
S = f^0.35 · p^0.25 · q^0.25 · (1-r)^0.15
```

- **f** = session success rate (sessions where agent_session, compilation, dedup_check all approved)
- **p** = first-pass rate across all five gates (loops == 0)
- **q** = file_validation pass rate (files_created / (files_created + files_rejected))
- **r** = normalized refinement burden (avg_loops / 5.0, capped)

A session that fails dedup_check (introduces a duplicate concept) drives the multiplicative score sharply down — that is the design.
