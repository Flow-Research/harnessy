---
description: Full-cycle QA sweep workflow for Harnessy-compatible repositories
argument-hint: "[--all] [--apps <app,...>] [--features <slug,...>] [--phase discover|walk|map|codegen|execute|report] [--dry-run] [--skip-walk] [--env local|staging|production]"
---

# QA Sweep Command

## Workflow

### 1. Resolve Runtime Inputs

Find the QA profile using the standard lookup order:

1. `.harnessy/qa-profile.json`
2. `.flow/qa-profile.json`
3. `qa/qa-profile.json`

Load optional `.flow/delivery-profile.json` if present. Treat it as adapter
metadata, not as the QA source of truth.

Run:

```bash
qa ids --profile <qa-profile>
qa tests --profile <qa-profile>
qa drift --profile <qa-profile>
```

If drift fails before the sweep, report the defects and continue only when the
user asked for repair work.

### 2. Discover

For each selected app from the QA profile:

- enumerate browser routes/pages from framework files
- enumerate API handlers/controllers/server actions
- enumerate auth/role/tenant guards
- enumerate DB policies/migrations when available
- cross-reference each surface against parsed regression scenarios and test IDs

Write `.qa-sweep/<timestamp>/discover-<app>.md`.

### 3. Walk

For browser-capable apps, use `/browser-qa` or repo-local Playwright utilities
unless `--skip-walk` is set.

Capture:

- actual URL after navigation
- visible headings, buttons, links, forms, tables, empty states, and errors
- role-specific redirects or forbidden states
- selectors with confidence notes
- screenshots/traces when failures or ambiguity occur

Write `.qa-sweep/<timestamp>/walk-<app>-<role>.md`.

### 4. Map

Create a scenario map by feature with these scenario types:

- positive
- negative
- unauthorized
- boundary
- destructive
- persistence/workflow-state
- accessibility/mobile when relevant

Every scenario needs:

- role or actor
- route/function/entry point
- expected result
- target layer
- status recommendation
- DB assertion when persistence or workflow state matters

Write `.qa-sweep/<timestamp>/map-<app>.md`.

### 5. Codegen

When not in `--dry-run` mode:

- update regression specs using canonical IDs
- scaffold browser tests with `/browser-integration-codegen`
- scaffold API tests with `/api-integration-codegen`
- use `/qa-feature-catalog` if new feature prefixes or semantic merges are needed
- preserve manual-only scenarios as manual

### 6. Execute

Prefer repo-local QA wrappers when they exist. Otherwise use deterministic gates:

```bash
qa drift --profile <qa-profile>
qa coverage --profile <qa-profile>
```

If the repo has feature-scoped execution commands, run a plan before execution
and document skipped/not-run rows explicitly.

### 7. Validate And Report

Run `/test-quality-validator` for generated or edited tests.

Write `.qa-sweep/<timestamp>/report.md` with:

- apps and features covered
- new/changed scenarios
- gaps by route/API/action/role
- execution summary
- skipped/not-run explanations
- validator findings
- next actions

## Completion Criteria

- drift status is known and clean unless the sweep is explicitly a gap audit
- browser selectors are based on walkthroughs or marked as unresolved TODOs
- persistence-sensitive browser flows have DB assertions or documented blockers
- new feature prefixes are cataloged
- security-relevant new surfaces are queued for `/qa-security-sweep`
