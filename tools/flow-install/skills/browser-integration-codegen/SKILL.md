---
name: browser-integration-codegen
description: "Generate browser integration suites from Harnessy regression artifacts using a QA profile plus optional delivery-profile adapters for fixtures, routes, and helper imports."
disable-model-invocation: false
allowed-tools: Read, Write, Grep, Glob, Bash, ApplyPatch
argument-hint: "[--suite <NN>] [--profile .flow/delivery-profile.json] [--delta] [--inspect-first]"
---

# Browser Integration Codegen

## Purpose

Generate Playwright-style browser integration suites from structured browser regression scenarios while keeping selector discovery and project adapters explicit and portable.

## Required contract

- canonical regression source from the active QA profile, typically `.harnessy/qa-profile.json`
- optional adapter metadata from `.flow/delivery-profile.json` for fixture mappings, route helpers, import shims, and DOM inspection paths

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/browser-integration-codegen/`.

## Steps

1. Follow `${AGENTS_SKILLS_ROOT}/browser-integration-codegen/commands/browser-integration-codegen.md` exactly.
2. Run `qa ids --profile <qa-profile>` first and use the QA profile as the source of truth for browser regression inputs.
3. Parse only canonical browser scenarios from the QA profile's configured regression sources.
4. Read the relevant source components and optional DOM inspection artifacts to verify selectors. When selectors, redirects, auth state, or responsive behavior are uncertain, run or request a Playwright walkthrough through `/browser-qa` before writing assertions.
5. Generate suite files using delivery-profile adapter data only for imports, fixtures, and project-specific test helpers.
6. Preserve `DB Assert:` expectations from the regression spec in the generated test plan. If persistence cannot be asserted in the target environment, leave an explicit TODO or skip reason.
7. Leave explicit TODOs instead of guessing selectors, DB assertions, or auth setup.

## Output

- generated `.spec.ts` suite content or files in the QA-profile-configured browser suites directory
- summary of selector certainty, unresolved TODOs, and suite/scenario counts
