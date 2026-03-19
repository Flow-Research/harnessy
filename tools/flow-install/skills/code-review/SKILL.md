---
name: code-review
description: "Expert code reviewer ensuring implementations are simple, requirement-compliant, and architecturally sound."
disable-model-invocation: true
allowed-tools: Read, Write, ApplyPatch, Grep, Glob, Bash
argument-hint: "[verify|status] or path to spec"
---

# Code Review

## Purpose
Review implemented code against the technical specification for simplicity, correctness, and architectural quality.

## Inputs
- Optional argument: `verify` to verify refinements
- Optional argument: `status` to show review status
- Path to spec file

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/code-review/`.

## Steps
1. Follow the command specification in `${AGENTS_SKILLS_ROOT}/code-review/commands/code-review.md` exactly.
2. Generate `code-review/feedback.json` and `code-review/REVIEW_REPORT.md` as specified.

## Output
- Structured feedback JSON and a human-readable review report.
