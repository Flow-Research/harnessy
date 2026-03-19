---
name: skill-publish
description: Publish a skill after validation and approvals; updates the catalog and logs the publish event.
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, ApplyPatch, Write
argument-hint: "[skill-name]"
---

# Skill Publish — Controlled Release

## Purpose
Publish a validated skill with proper approvals, then update catalog metadata and log the publish event.

## Inputs
- Skill name
- Evidence of test gates
- Explicit approver (required for high blast radius)

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/skill-publish/`.

## Steps
1. **Run `/skill-validate <skill-name>`** and confirm PASS.
2. **Enforce approval gate**
   - If `blast_radius: high`, require explicit approval (Julian or Sayo). If missing, STOP.
3. **Update catalog entry**
   - Increment version if needed
   - Update `updated` date
4. **Write publish log** to `.jarvis/context/skills/publish-log.md` with:
   - Skill name, version, owner, blast radius
   - Approver (if required)
   - Date and summary
5. **Return confirmation**

## Output
- Confirmation message
- Link to catalog entry + publish log
