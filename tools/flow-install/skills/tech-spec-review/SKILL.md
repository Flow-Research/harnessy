---
name: tech-spec-review
description: "Six-perspective engineering review for technical_spec.md files."
disable-model-invocation: true
allowed-tools: Read, Write, ApplyPatch, Grep, Glob, WebSearch
argument-hint: "[quick] or path to technical_spec.md"
---

# Tech Spec Review

## Purpose
Review and refine technical specifications using multi-perspective engineering analysis.

## Inputs
- Optional argument: `quick` for abbreviated review
- Path to `technical_spec.md`

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/tech-spec-review/`.

## Steps
1. Follow the command specification in `${AGENTS_SKILLS_ROOT}/tech-spec-review/commands/tech-spec-review.md` exactly.
2. Update `technical_spec.md` as needed based on findings.

## Output
- Updated `technical_spec.md` and a review summary.
