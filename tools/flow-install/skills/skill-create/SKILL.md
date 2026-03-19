---
name: skill-create
description: Scaffold a new skill in the monorepo with a valid manifest and catalog entry. Use when creating any new skill.
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, ApplyPatch, Write
argument-hint: "[skill-name] [type: opencode|OpenClaw|n8n]"
---

# Skill Create — Monorepo Scaffold

## Purpose
Create a new skill in the monorepo with a valid `manifest.yaml` and a catalog entry. Enforce secure defaults and prevent duplicates.

## Inputs
- Skill name (kebab-case)
- Type: `opencode` | `OpenClaw` | `n8n`
- Owner
- Blast radius: `low` | `medium` | `high`
- Description
- Permissions (explicit list)
- Data categories (e.g., `pii`, `financial`, `credentials`, `none`)
- Egress allowlist (domains or services)
- Invoke command/trigger
- Phase(s)

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/skill-create/`.

## Steps
1. **Validate naming**
   - Ensure name is lowercase, kebab-case, and ≤ 64 chars.
2. **Check for duplicates (required)**
- Search in `.agents/skills`, `.agents/OpenClaw`, `.agents/n8n` for matching skill name.
   - Search `.jarvis/context/skills/_catalog.md` for existing entries with same name or invoke command.
   - If any match is found, STOP and report the conflict.
3. **Create directory**
   - Create `plugins/<type>/<skill-name>/`.
4. **Design the intelligence ↔ determinism split**
   - Put orchestration, intent parsing, and decision-making in `SKILL.md`.
   - Put repeatable logic (parsing, transforms, formatting, API calls) into scripts under `tools/`.
   - The skill must describe when to call scripts and what input/output contracts they expect.
5. **Write `manifest.yaml`** using `templates/manifest.yaml`.
6. **Write `SKILL.md`** using `templates/SKILL.md` (fill in purpose, inputs, steps, output).
   - If the skill delegates to command docs, reference them as `${AGENTS_SKILLS_ROOT}/<skill-name>/commands/<file-name>.md`.
   - Do not use fragile references like `./commands/<file-name>.md`.
   - Include this mandatory line in every skill doc: `Template paths are resolved from ${AGENTS_SKILLS_ROOT}/<skill-name>/.`
   - When `templates/...` is used, resolve it from `${AGENTS_SKILLS_ROOT}/<skill-name>/`.
   - Keep skill runtime scripts under `.agents/skills/<skill-name>/scripts/` so installation places them at `${AGENTS_SKILLS_ROOT}/<skill-name>/scripts/`.
7. **Add catalog entry** in `.jarvis/context/skills/_catalog.md` using `templates/catalog-entry.md`.
7. **Add catalog entry** in `.jarvis/context/skills/_catalog.md` using `templates/catalog-entry.md`.
8. **Register skills for global OpenCode discovery**
   - Run `pnpm skills:register` to install skills to `${AGENTS_SKILLS_ROOT}` (resolved from `scripts/skills-root.config.json`).
   - Skills are auto-discovered by OpenCode — no config update required.
9. **Return a checklist** for `/skill-validate` and `/skill-publish`.
   - Run `pnpm skills:register` to sync skills into `${AGENTS_SKILLS_ROOT}`.
9. **Return a checklist** for `/skill-validate` and `/skill-publish`.

## Templates
- `templates/manifest.yaml`
- `templates/SKILL.md`
- `templates/catalog-entry.md`

## Checklist (Return to User)
- [ ] Run `/skill-validate <skill-name>`
- [ ] Run `pnpm skills:register` (installs to `${AGENTS_SKILLS_ROOT}`)
- [ ] Add test evidence for blast radius
- [ ] If high blast radius: get explicit approval before publish
- [ ] Run `/skill-validate <skill-name>`
- [ ] Run `pnpm skills:register` (or `node scripts/register-opencode-skills.mjs`)
- [ ] Add test evidence for blast radius
- [ ] If high blast radius: get explicit approval before publish
