---
name: qa
description: "Quality Assurance agent for test execution, coverage analysis, bug identification, and browser-QA delegation."
disable-model-invocation: true
allowed-tools: Read, Write, ApplyPatch, Grep, Glob, Bash
argument-hint: "[unit|integration|stress|performance|report|fix] [epic-path]"
---

# QA

## Purpose
Execute QA workflows, analyze coverage, generate test case specifications, report bugs, and delegate browser-driven checks to `browser-qa` when needed.

## Inputs
- Optional argument: `unit`, `integration`, `stress`, `performance`, `report`, or `fix`
- Optional epic path

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/qa/`.

## Steps
1. Follow the command specification in `${AGENTS_SKILLS_ROOT}/qa/commands/qa.md` exactly.
2. Use `templates/user-test-script.md` when generating manual test scripts.
3. Every generated manual test script must be delivered in both Markdown and Excel formats. After writing the Markdown source, export a matching `.xlsx` workbook with `python3 ${AGENTS_SKILLS_ROOT}/qa/scripts/export-user-test-script.py <markdown-path> [xlsx-path]`.
4. When a QA request requires Playwright/browser automation, invoke `/browser-qa` for setup, auth handoff, scripted execution, and artifact normalization.

## Output
- QA reports, bug reports, and test case specs under `qa/` or `specs/<epic>/qa/`.
- Manual test scripts as paired `.md` and `.xlsx` files.
