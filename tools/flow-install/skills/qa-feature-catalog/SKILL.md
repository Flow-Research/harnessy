---
name: qa-feature-catalog
description: "Maintain a semantic QA feature catalog for Harnessy-compatible repositories by consolidating raw spec suites into stable feature slugs, prefixes, result files, and optional result-sink tabs."
disable-model-invocation: false
allowed-tools: Read, Write, Grep, Glob, Bash, ApplyPatch
argument-hint: "[--dry-run] [--write-overrides] [--features <slug,...>] [--apps <app,...>]"
---

# QA Feature Catalog

## Purpose

Keep a repo's QA feature catalog stable and human-meaningful while preserving
deterministic runtime behavior. The catalog maps scenario ID prefixes to feature
slugs, display names, apps, regression suites, result snapshots, and optional
external result sinks.

Template paths are resolved from `${AGENTS_SKILLS_ROOT}/qa-feature-catalog/`.

## Inputs

- Canonical QA profile and parsed `qa ids` output.
- Optional catalog artifacts:
  - `qa/features.generated.yaml`
  - `qa/features.overrides.yaml`
  - `qa/features.changelog.md`
- Optional result snapshots under `qa/run-results/`.
- Optional result-sink metadata from the QA profile or delivery profile.

## Steps

1. Follow `${AGENTS_SKILLS_ROOT}/qa-feature-catalog/commands/qa-feature-catalog.md`.
2. Parse all specs with `qa ids --json`.
3. Group scenarios by ID prefix, app, layer, suite annotation, and spec source.
4. Compare the deterministic grouping to existing generated catalog and overrides.
5. Propose semantic decisions: accept, rename, merge, split, archive, or add.
6. When `--write-overrides` is requested, update only the hand-maintained
   override/changelog artifacts. Do not hand-edit generated catalog files owned
   by repo-local generators.
7. Run the repo-local catalog generator/validator when available, then run
   `qa drift`.

## Output

- Decision table with each proposed feature catalog change.
- Optional updates to `qa/features.overrides.yaml` and `qa/features.changelog.md`.
- Instructions for any repo-local generated files or external result sinks that
  need migration.

## Guardrails

- Do not rename an ID prefix that already has committed results or external rows
  without an explicit migration plan.
- Do not invent features with no spec backing unless they are explicit manual
  or cross-feature entries.
- Keep generated files generated. Use overrides for semantic tie-breaking.
- Preserve existing result snapshots and note any orphaned rows.
