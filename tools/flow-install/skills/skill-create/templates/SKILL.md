---
name: <skill-name>
description: "<short description>"
disable-model-invocation: true
allowed-tools: Read, Grep, Glob
argument-hint: "[args]"
---

# <Skill Name>

## Purpose
Describe what this skill does and when to use it.

## Inputs
- List required inputs

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/<skill-name>/`.

## Steps
1. Provide clear, ordered instructions.
2. Keep actions explicit and verifiable.
3. If this skill uses external command specs, reference them with placeholder paths: `${AGENTS_SKILLS_ROOT}/<skill-name>/commands/<file-name>.md`.
   - Avoid fragile repo-root relative paths like `./commands/<file-name>.md`.
4. If this skill uses `templates/...` relative paths, resolve them from `${AGENTS_SKILLS_ROOT}/<skill-name>/`.
5. If this skill needs executable scripts, place them under `${AGENTS_SKILLS_ROOT}/<skill-name>/scripts/` (source path in repo: `.agents/skills/<skill-name>/scripts/`).
6. Split intelligence vs determinism:
   - Use the LLM for intent parsing and decision-making.
   - Use scripts in `tools/` for parsing, transforms, formatting, and API calls.
   - Define strict input/output contracts for each script.
7. If the skill must be discoverable by OpenCode, run `pnpm skills:register`.

## Deterministic Logic (Scripts)
- List scripts in `tools/` and their exact input/output schema.
- Prefer JSON in/out for machine-readability.
- Keep scripts idempotent and testable.

## Output
- Expected output format or success criteria.
