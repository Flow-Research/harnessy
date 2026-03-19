---
name: prd-spec-review
description: "Multi-perspective quality review for product_spec.md files."
disable-model-invocation: true
allowed-tools: Read, Write, ApplyPatch, Grep, Glob, WebSearch
argument-hint: "[quick] or path to product_spec.md"
---

# PRD Spec Review

## Purpose
Review and refine product specification documents using multi-perspective analysis.

## Inputs
- Optional argument: `quick` for abbreviated review
- Path to `product_spec.md`

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/prd-spec-review/`.

## Steps
1. Follow the command specification in `${AGENTS_SKILLS_ROOT}/prd-spec-review/commands/prd-spec-review.md` exactly.
2. Update `product_spec.md` as needed based on findings.

## Output
- Updated `product_spec.md` and a review summary.
