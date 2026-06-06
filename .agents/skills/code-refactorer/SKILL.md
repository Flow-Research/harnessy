---
name: code-refactorer
description: "Autonomous code refactoring agent that rewrites messy functions, splits large files, removes duplication, improves naming, enforces structure, and preserves behavior."
disable-model-invocation: true
allowed-tools: Read, Write, ApplyPatch, Grep, Glob, Bash
argument-hint: "[analyze|split|dedup|rename|status] or path to file/directory"
---

# Code Refactorer

## Purpose
Refactor existing code to be cleaner, more maintainable, and better structured — **without changing observable behavior**.

## Inputs
- Optional arguments: `analyze`, `split`, `dedup`, `rename`, `status`
- Path to a file or directory to refactor

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/code-refactorer/`.

## Steps
1. Follow the command specification in `${AGENTS_SKILLS_ROOT}/code-refactorer/commands/code-refactorer.md` exactly.
2. Generate `code-refactorer/REFACTOR_REPORT.md` and a patch/diff of all changes.

## Capabilities

| Capability | Description |
|------------|-------------|
| **Rewrite messy functions** | Flatten deep nesting, reduce complexity, simplify logic |
| **Split large files** | Break files exceeding size thresholds into focused modules |
| **Remove duplication** | Extract repeated logic into shared utilities |
| **Improve naming** | Rename symbols to clearly express intent |
| **Enforce structure** | Apply consistent layout, ordering, and module boundaries |
| **Preserve behavior** | Verify tests pass before and after every change |

## Output
- Refactored source files (in-place or via patch)
- `code-refactorer/REFACTOR_REPORT.md` summarising every change made and why
