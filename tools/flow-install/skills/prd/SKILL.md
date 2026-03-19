---
name: prd
description: "Transform brainstorm.md into a comprehensive Product Specification Document."
disable-model-invocation: true
allowed-tools: Read, Write, ApplyPatch, Grep, Glob, WebSearch
argument-hint: "[review] or path to brainstorm.md"
---

# PRD

## Purpose
Generate a production-ready Product Specification Document from brainstorm inputs.

## Inputs
- Optional argument: `review` to review an existing product_spec.md
- Path to `brainstorm.md`

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/prd/`.

## Steps
1. Follow the command specification in `${AGENTS_SKILLS_ROOT}/prd/commands/prd.md` exactly.
2. Use `templates/product_spec.md` as the output template.
3. Write `product_spec.md` in the same folder as the source brainstorm.

## Output
- `product_spec.md` created or updated per template.
