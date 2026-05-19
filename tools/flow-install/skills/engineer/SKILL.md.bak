---
name: engineer
description: "Autonomous full-stack development agent that implements technical specifications with high test coverage."
disable-model-invocation: true
allowed-tools: Read, Write, ApplyPatch, Grep, Glob, Bash, WebSearch
argument-hint: "[resume|status|fix|test-cases] or path to spec"
---

# Engineer

## Purpose
Implement technical specifications end-to-end with tests and coverage targets.

## Inputs
- Optional arguments: `resume`, `status`, `fix`, `test-cases`
- Path to `MVP_technical_spec.md` or `technical_spec.md`

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/engineer/`.

## Steps
1. Follow the command specification in `${AGENTS_SKILLS_ROOT}/engineer/commands/engineer.md` exactly.
2. Initialize semver if needed and set up CI/CD as required.

## Output
- Implementation code, tests, and progress reporting per spec.
