---
name: api-integration-codegen
description: "Generate API integration test suites from Harnessy regression artifacts using a QA profile plus optional delivery-profile adapters."
disable-model-invocation: false
allowed-tools: Read, Write, Grep, Glob, Bash, ApplyPatch
argument-hint: "[--suite <X>] [--profile .flow/delivery-profile.json] [--delta]"
---

# API Integration Codegen

## Purpose

Generate API integration test suites from the project's API regression spec without assuming one repository layout, helper module path, or fixture naming scheme.

## Required contract

- canonical regression source from the active QA profile, typically `.harnessy/qa-profile.json`
- optional adapter metadata from `.flow/delivery-profile.json` for suite metadata, helper imports, fixture imports, and DB helper rules

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/api-integration-codegen/`.

## Steps

1. Follow `${AGENTS_SKILLS_ROOT}/api-integration-codegen/commands/api-integration-codegen.md` exactly.
2. Run `qa ids --profile <qa-profile>` first and use the QA profile as the source of truth for API regression inputs.
3. Parse only canonical API scenarios from the QA profile's configured regression sources.
4. Generate the suite file using delivery-profile adapter data only for suite metadata, helper imports, fixture imports, and optional DB helper rules.
5. Refine the generated suite when business logic requires stronger assertions than the scaffolder can infer automatically.

## Output

- generated `.api.test.ts` suite content or files in the QA-profile-configured API suites directory
- generation summary with suite/scenario counts and any unresolved adapter gaps
