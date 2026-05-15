---
name: qa-sweep
description: "Full-cycle QA orchestrator for Harnessy-compatible repositories: discovers feature surfaces, uses Playwright/browser walkthroughs when available, maps scenario gaps, updates regression artifacts, runs drift/validation, and reports coverage."
disable-model-invocation: false
allowed-tools: Read, Write, Grep, Glob, Bash, ApplyPatch
argument-hint: "[--all] [--apps <app,...>] [--features <slug,...>] [--phase discover|walk|map|codegen|execute|report] [--dry-run] [--skip-walk] [--env local|staging|production]"
---

# QA Sweep

## Purpose

Run a complete QA coverage cycle in any repository that follows the Harnessy QA
profile contract. The sweep coordinates deterministic runtime checks with
model-assisted discovery and browser inspection:

1. discover app routes, APIs, actions, and existing regression coverage
2. walk browser surfaces with Playwright when UI behavior or selectors matter
3. map positive, negative, unauthorized, boundary, destructive, and persistence scenarios
4. update regression specs and tests using codegen skills where appropriate
5. execute or plan tests through repo-local commands
6. report coverage gaps, failures, skips, and follow-up work

Template paths are resolved from `${AGENTS_SKILLS_ROOT}/qa-sweep/`.

## Required Inputs

- A canonical QA profile: `.harnessy/qa-profile.json`, `.flow/qa-profile.json`,
  or `qa/qa-profile.json`.
- Regression specs and test roots declared by that profile.
- Optional delivery profile metadata from `.flow/delivery-profile.json` for
  roles, routes, fixtures, helpers, selector inspection scripts, seeded account
  flows, and result sinks.

## Steps

1. Follow `${AGENTS_SKILLS_ROOT}/qa-sweep/commands/qa-sweep.md`.
2. Run `qa ids`, `qa tests`, and `qa drift` before changing files.
3. Discover source surfaces from the repo's actual framework and profile paths:
   route files, API handlers, server actions/controllers, middleware/guards,
   schemas, database migrations/policies, and shared workflow modules.
4. Use `/browser-qa` or repo-local Playwright helpers for real browser
   walkthroughs before writing browser assertions when selectors, redirects,
   auth state, or persisted UI state are uncertain.
5. Map scenarios with explicit roles and scenario types. Browser scenarios that
   verify a persisted mutation or workflow transition must include a `DB Assert:`
   or explain why persistence cannot be checked.
6. Use `/browser-integration-codegen` and `/api-integration-codegen` for test
   scaffolding. Preserve canonical scenario IDs.
7. Run `/test-quality-validator` after generating or editing tests.
8. Finish with `qa drift` and, when the target repo provides result-sink
   commands, run the repo-local plan/execute/sync commands documented by that repo.

## Outputs

- `.qa-sweep/<timestamp>/discover-*.md`
- `.qa-sweep/<timestamp>/walk-*.md` when browser walkthroughs run
- `.qa-sweep/<timestamp>/map-*.md`
- `.qa-sweep/<timestamp>/report.md`
- optional updates to regression specs, test files, feature catalog, and run results

## Guardrails

- Keep repo-specific auth, seed, sheet, dashboard, and CI behavior in the
  target repo. This skill coordinates those commands but does not invent them.
- Do not guess selectors from source when browser behavior can be walked.
- Do not mark scenarios as implemented unless matching tests exist or are added
  in the same change.
- Gate destructive flows behind explicit user intent or a repo-local destructive
  flag.
- Never run destructive flows against production.
- Preserve existing scenario IDs. Add new IDs only for genuinely new scenarios.
