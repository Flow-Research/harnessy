# Development Guidance

## Purpose

This document is the canonical workspace-level source for engineering workflow guidance. Project-specific implementation conventions still live closer to the codebase, especially in sub-project `AGENTS.md` files.

## Workspace Rules

- Follow the active project focus in `status.md`.
- Use the simplest implementation that validates the current roadmap milestone.
- Prefer project-local conventions when working inside `Flow/`, `Jarvis/`, or other nested projects.
- Keep technical debt in the debt registers, not only in comments or chat.

## Session Rhythm

### Before a focused session

- Pull the latest relevant changes.
- Read `projects.md`, `status.md`, and `roadmap.md`.
- Check sub-project instructions before editing nested code.

### Before claiming work is complete

- Run the relevant project tests or checks.
- Update roadmap or debt docs if the work changes current truth.
- Record decisions in `decisions.md` when the implementation settles an open question.

## Project-Specific Conventions

- `Flow/` Rust patterns and tooling conventions belong in `Flow/AGENTS.md`.
- `Jarvis/` CLI conventions belong in `Jarvis/AGENTS.md`.
- POC implementation constraints belong in `status.md` and `roadmap.md`.

## Note

Older overlapping root docs were removed during the context consolidation. Shared workflow guidance should now be read from this file plus the canonical root docs.
