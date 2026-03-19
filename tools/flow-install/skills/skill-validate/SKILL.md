---
name: skill-validate
description: Validate a skill's manifest, catalog entry, and blast-radius gates. Use before publishing any skill.
disable-model-invocation: true
allowed-tools: Read, Grep, Glob
argument-hint: "[skill-name]"
---

# Skill Validate — Governance Gate

## Purpose
Verify that a skill complies with the manifest schema, catalog requirements, and blast-radius gates.

## Inputs
- Skill name

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/skill-validate/`.

## Steps
1. **Locate skill** in `.agents/skills`, `.agents/OpenClaw`, or `.agents/n8n`.
2. **Read `manifest.yaml`** and validate required fields:
   - `name`, `type`, `version`, `owner`, `status`, `blast_radius`, `description`, `permissions`, `data_categories`, `egress`, `invoke`, `location`
3. **Confirm catalog entry** exists in `.jarvis/context/skills/_catalog.md`.
4. **Blast-radius gates**
   - **Low**: self-test evidence required
   - **Medium**: self-test + peer spot-check evidence required
   - **High**: self-test + staging proof + explicit approval required
5. **Return a pass/fail** with a remediation list.

## Output
- Status: PASS or FAIL
- Missing fields or mismatches
- Required next actions (tests, approvals)
