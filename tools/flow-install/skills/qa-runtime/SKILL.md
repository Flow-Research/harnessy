---
name: qa-runtime
description: Deterministic QA runtime for parsing regression specs, scanning tests, detecting drift, and generating coverage from a repo-local QA profile.
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash
argument-hint: "[ids|tests|drift|coverage] [--profile <path>] [--json] [--output <path>]"
---

# QA Runtime

## Purpose
Provide an installable, project-agnostic QA runtime that turns a repo-local QA profile into deterministic commands for spec parsing, test scanning, drift detection, and coverage reporting.

## Inputs
- Optional subcommand: `ids`, `tests`, `drift`, or `coverage`
- Optional flags: `--profile <path>`, `--json`, `--output <path>`, `--strict`
- Optional profile conventions for feature catalogs, run-result snapshots,
  security findings, browser walkthroughs, result sinks, and repo-local
  plan/execute/sync commands

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/qa-runtime/`.

## Steps
1. Follow the command contract in `${AGENTS_SKILLS_ROOT}/qa-runtime/commands/qa-runtime.md`.
2. Prefer the installed `qa` command for deterministic execution.
3. Store repo-specific layout, spec sources, and test roots in a profile such as `.harnessy/qa-profile.json`.
4. Keep the runtime generic; any app-specific seed, auth, or result-sink behavior belongs in the target repo profile and local scripts.

## Output
- Parsed QA scenario records.
- Test ID inventory with header metadata.
- Drift reports for spec/test mismatches.
- Coverage markdown or JSON summaries.
