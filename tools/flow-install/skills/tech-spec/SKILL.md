---
name: tech-spec
description: "Generate production-ready technical specifications from product specs."
disable-model-invocation: true
allowed-tools: Read, Write, ApplyPatch, Grep, Glob, WebSearch
argument-hint: "[review] or path to specs folder"
---

# Tech Spec

## Purpose
Create a comprehensive technical specification from product requirements.

## Inputs
- Optional argument: `review` to review an existing technical_spec.md
- Path to specs folder containing product_spec.md

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/tech-spec/`.

## Steps
1. Follow the command specification in `${AGENTS_SKILLS_ROOT}/tech-spec/commands/tech-spec.md` exactly.
2. Use `templates/technical_spec.md` as the output template.
3. Write `technical_spec.md` to the target specs folder.

## Output
- `technical_spec.md` created or updated per template.
