---
name: mvp-tech-spec
description: "Distill technical_spec.md into a focused MVP with prioritized work items."
disable-model-invocation: true
allowed-tools: Read, Write, ApplyPatch, Grep, Glob, WebSearch
argument-hint: "[items] or path to specs folder"
---

# MVP Tech Spec

## Purpose
Create an MVP-focused technical specification and prioritized work items from a full tech spec.

## Inputs
- Optional argument: `items` to extract work items only
- Path to specs folder containing technical_spec.md

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/mvp-tech-spec/`.

## Steps
1. Follow the command specification in `${AGENTS_SKILLS_ROOT}/mvp-tech-spec/commands/mvp-tech-spec.md` exactly.
2. Use `templates/mvp_technical_spec.md` as the output template.
3. Write `MVP_technical_spec.md` to the specs folder.

## Output
- `MVP_technical_spec.md` created or updated per template.
