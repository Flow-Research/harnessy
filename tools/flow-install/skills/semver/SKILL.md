---
name: semver
description: "Manage semantic versioning with VERSION file + CHANGELOG.md for any codebase."
disable-model-invocation: true
allowed-tools: Read, Write, ApplyPatch, Grep, Glob, Bash
argument-hint: "[init|status|log|release|bump] [args]"
---

# Semver

## Purpose
Initialize and manage semantic versioning for a codebase using VERSION and CHANGELOG.md.

## Inputs
- `init`, `status`, `log`, `release`, or `bump` commands with arguments

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/semver/`.

## Steps
1. Follow the command specification in `${AGENTS_SKILLS_ROOT}/semver/commands/semver.md` exactly.
2. Update VERSION and CHANGELOG.md as required.

## Output
- VERSION and CHANGELOG.md updated per the chosen action.
