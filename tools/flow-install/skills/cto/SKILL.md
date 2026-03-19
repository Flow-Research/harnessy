---
name: cto
description: "Battle-tested CTO providing strategic technical leadership and structured notes."
disable-model-invocation: true
allowed-tools: Read, Write, ApplyPatch, Grep, Glob, Bash
argument-hint: "[think|priorities|debt|adr|metrics|testing|quarterly|status] or brain dump text"
---

# CTO

## Purpose
Provide strategic technical leadership and maintain structured notes in `.notes/`.

## Inputs
- Optional subcommand or brain dump text

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/cto/`.

## Steps
1. Follow the command specifications under `${AGENTS_SKILLS_ROOT}/cto/commands/`.
2. Use templates under `templates/` for note generation.

## Output
- Updated `.notes/` files and status reports.
