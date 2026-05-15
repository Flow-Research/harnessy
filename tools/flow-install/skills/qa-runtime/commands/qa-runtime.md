---
description: Deterministic QA runtime for profile-driven spec parsing, test scanning, drift checks, and coverage reports
argument-hint: "[ids|tests|drift|coverage] [--profile <path>] [--json] [--output <path>]"
---

# QA Runtime Command

Use the installed `flow-qa` command as the canonical execution surface.

## Profile Contract

The runtime reads a repo-local JSON profile. Default lookup order:

1. `.harnessy/qa-profile.json`
2. `.flow/qa-profile.json`
3. `qa/qa-profile.json`

The profile must declare:

```json
{
  "version": 1,
  "specs": [
    { "path": "qa/browser/scripts/app-full-regression.md", "app": "web", "layer": "browser" }
  ],
  "apps": [
    {
      "id": "web",
      "tests": {
        "browser": ["apps/web/tests/browser-integration/suites"],
        "api": ["apps/web/tests/integration/api-routes"]
      }
    }
  ],
  "output": {
    "coverage": "qa/qa-coverage.md"
  }
}
```

Use `${AGENTS_SKILLS_ROOT}/qa-runtime/templates/qa-profile.json` as the starter template.

## Commands

### `flow-qa ids`

Parse all spec sources from the profile and emit canonical scenario records.

### `flow-qa tests`

Scan the configured test roots, extract scenario IDs from test names, and report header annotations.

### `flow-qa drift`

Validate spec/test consistency:

- parse errors
- implemented scenarios without tests
- tests referencing nonexistent specs
- files missing `@qa-spec` / `@qa-suite` headers

### `flow-qa coverage`

Generate a summary report from the spec and test inventories. Write to the profile's `output.coverage` path unless `--output` overrides it.

## Notes

- Keep repo-specific seed, auth, and result-sink logic outside this runtime.
- This command is intentionally deterministic and profile-driven.
