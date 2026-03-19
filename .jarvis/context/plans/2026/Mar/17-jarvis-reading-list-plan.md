# Jarvis Reading List Organization - Implementation Plan

## Context
The Jarvis CLI has a reading-list organization feature that:
1. Fetches articles from AnyType/Notion
2. Uses AI to prioritize them
3. Returns markdown

## Problems to Fix

### 1. Silent AI Fallback ✅ DONE
**File:** `Jarvis/src/jarvis/reading_list/prioritizer.py`
**Location:** Line ~203 (the except block)
**Issue:** Bare `except Exception:` silently falls back to heuristic scoring when Anthropic API fails (e.g., "credit balance too low")
**Fix:** Added warning to stderr — implemented in `prioritizer.py:203-211`.

### 2. Poor Markdown Formatting ✅ DONE
**File:** `Jarvis/src/jarvis/reading_list/cli.py`
**Location:** `_result_to_markdown()` function
**Issue:**
- Repetitive rationales (same text repeated 100+ times)
- No topic grouping within tiers
- Raw URLs as titles (bad for SSRN/S3 pre-signed URLs)
- URL on separate line making docs visually noisy

**Fix:** Rewrote with `_readable_title()`, `_type_badge()`, topic grouping within tiers, and deduplicated shared rationales. See `cli.py:108-176`.

### 3. Update Jarvis Skill for Agent Orchestration ✅ DONE
**File:** `plugins/opencode/jarvis/commands/jarvis.md`
**Changes:**
- Replaced lightweight "Reading List Workflow" section with a comprehensive 7-step agent-orchestrated protocol (Path A)
- Path A: Agent extracts items via `reading-list extract` (JSON), researches/scores using its own context and WebFetch, formats markdown, writes back via `reading-list write-back`
- Path B: Preserved CLI-native AI flow as terminal fallback
- Added scoring rubric and topic taxonomy directly in skill docs
- Added two new CLI commands to support agent orchestration:
  - `jarvis reading-list extract <target>` — returns raw unscored items as JSON
  - `jarvis reading-list write-back <target> --file/--stdin` — writes agent-formatted markdown to source
- Updated SKILL.md description and added `WebFetch` to allowed tools
- Updated command mapping table with new commands

### 4. Verify JSON Output
**Command:** `jarvis rl --no-fetch --format json`
**Status:** Code exists. The new `reading-list extract` command is the preferred agent path (returns cleaner unscored data).

## Execution Order

1. ~~Fix `prioritizer.py` - silent fallback warning~~ ✅
2. ~~Rewrite `_result_to_markdown()` in `cli.py`~~ ✅
3. ~~Update Jarvis skill docs in `commands/jarvis.md`~~ ✅
4. ~~Add `extract` and `write-back` CLI subcommands~~ ✅
5. Re-register skill and reinstall CLI ✅
6. Test end-to-end agent orchestration flow

## Files Modified

- `Jarvis/src/jarvis/reading_list/cli.py` — Added `extract` and `write-back` subcommands
- `plugins/opencode/jarvis/commands/jarvis.md` — Full agent orchestration protocol
- `plugins/opencode/jarvis/SKILL.md` — Updated description, added WebFetch tool
- `plugins/opencode/jarvis/manifest.yaml` — Updated description
- `Jarvis/AGENTS.md` — Updated command table with new commands

## Architecture Note

The reading list reorganization now supports two paths:

**Path A (Agent-Orchestrated, Primary):**
```
Agent extracts items (CLI JSON) → Agent researches each URL → Agent scores with project context → Agent formats markdown → CLI writes back to source
```

**Path B (CLI-Native, Preserved Fallback):**
```
User runs `jarvis rl` → CLI fetches URLs → CLI calls Anthropic API → CLI formats and outputs
```

Path A is preferred when running as an agent skill because the agent already has full project context, can use WebFetch, and reasons better than a one-shot API call.
