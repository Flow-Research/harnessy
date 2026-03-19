---
name: build-e2e
description: "End-to-end product development orchestrator with human-in-the-loop reviews."
disable-model-invocation: true
allowed-tools: Read, Write, ApplyPatch, Grep, Glob, Bash, Question
argument-hint: "[continue|status|skip|epic <name>]"
---

# Build E2E

## Purpose
Orchestrate the full product development lifecycle from idea to local deployment.

## Inputs
- Optional arguments: `continue`, `status`, `skip`, or `epic <name>`

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/build-e2e/`.

## Steps
1. Follow the command specification in `${AGENTS_SKILLS_ROOT}/build-e2e/commands/build-e2e.md` exactly.
2. Invoke child skills in the defined order with checkpoints.

## Output
- Complete pipeline execution with artifacts under `specs/<epic>/`.
