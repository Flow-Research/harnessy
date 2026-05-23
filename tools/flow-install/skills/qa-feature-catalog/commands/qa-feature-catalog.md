---
description: Semantic maintenance workflow for QA feature catalogs
argument-hint: "[--dry-run] [--write-overrides] [--features <slug,...>] [--apps <app,...>]"
---

# QA Feature Catalog Command

## Workflow

### 1. Load Sources

Resolve the QA profile, then run:

```bash
qa ids --profile <qa-profile> --json
qa tests --profile <qa-profile> --json
```

Read existing catalog files when present:

- `qa/features.generated.yaml`
- `qa/features.overrides.yaml`
- `qa/features.changelog.md`
- `qa/run-results/*.json`

Read result-sink metadata only when configured by the target repo.

### 2. Build Raw Feature Groups

Group by scenario ID prefix first. For each group, capture:

- prefix
- candidate slug
- human display name
- apps
- layers
- spec sources
- scenario count
- existing result snapshot path
- external sink/tab name if configured

### 3. Propose Semantic Changes

Use these decisions:

- `accept`: raw group is already clean
- `rename`: name or slug is unclear but prefix remains stable
- `merge`: multiple raw suite names describe one product feature
- `split`: one group actually contains distinct product features
- `archive`: group is deprecated or no longer backed by specs
- `add`: manual/E2E feature is intentional but not discoverable from raw suites

### 4. Write Safely

Default mode is read-only.

With `--write-overrides`, update hand-maintained override files and append a
dated changelog entry. Do not edit generated catalog files directly.

After writing, run the repo-local generator/validator if the repo exposes one.
Always finish with:

```bash
qa drift --profile <qa-profile>
```

## Completion Criteria

- every active prefix maps to one feature
- every feature has spec backing or an explicit manual/E2E reason
- result snapshots and external result sinks are either aligned or called out
- no generated file was manually edited
