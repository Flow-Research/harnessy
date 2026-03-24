# Technical Debt Tracking Standard

## Purpose

This standard defines the minimum structure for debt captured in `.jarvis/context/technical-debt.md` and per-epic debt registers under `.jarvis/context/specs/<epic>/tech_debt.md`.

## Required Fields

Every debt item must include:

- **ID** - stable unique identifier
- **Status** - `open`, `accepted`, `resolved`, or `cancelled`
- **Type** - for example `design`, `implementation`, `security`, `performance`, `process`
- **Scope** - subsystem, project, or epic affected
- **Context** - why the shortcut or gap exists
- **Impact** - what risk, cost, or limitation it creates
- **Proposed resolution** - the intended cleanup direction
- **Target phase** - when the debt should be revisited
- **Links** - related plans, specs, PRs, or source files

## Register Format

Use a lightweight summary table for open items and fuller sections for important or resolved items.

### Summary table

| ID | Status | Type | Scope | Summary | Target Phase |
|---|---|---|---|---|---|

### Detailed entry

- **ID:**
- **Status:**
- **Type:**
- **Scope:**
- **Context:**
- **Impact:**
- **Proposed resolution:**
- **Target:**
- **Links:**

## Rules

- Track intentional compromises, deferred migrations, and known incomplete boundaries.
- Do not hide debt only in TODO comments, plans, or chat transcripts.
- Update the register when debt changes status.
- If debt affects cross-project architecture or security posture, mirror it in the project-level register.
