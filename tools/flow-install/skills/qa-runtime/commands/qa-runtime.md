---
description: Deterministic QA runtime for profile-driven spec parsing, test scanning, drift checks, and coverage reports
argument-hint: "[ids|tests|drift|coverage] [--profile <path>] [--json] [--output <path>]"
---

# QA Runtime Command

Use the installed `qa` command as the canonical execution surface.
`flow-qa` remains installed as a backward-compatible alias for older projects.

See `.jarvis/context/docs/standards/qa-process.md` for the shared Harnessy QA contract that this runtime enforces.

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
    "coverage": "qa/qa-coverage.md",
    "featureCatalog": "qa/features.generated.yaml",
    "featureOverrides": "qa/features.overrides.yaml",
    "featureChangelog": "qa/features.changelog.md",
    "runResultsDir": "qa/run-results",
    "securityFindingsDir": "qa/security/findings",
    "walkthroughDir": ".qa-sweep"
  },
  "resultSinks": [],
  "commands": {
    "plan": "",
    "execute": "",
    "syncSpecs": "",
    "syncResults": ""
  }
}
```

Use `${AGENTS_SKILLS_ROOT}/qa-runtime/templates/qa-profile.json` as the starter template.

Only `specs`, `apps`, and `output.coverage` are required by the deterministic
runtime today. The other fields are shared conventions used by orchestration
skills such as `/qa-sweep`, `/qa-feature-catalog`, and `/qa-security-sweep`.

## Commands

### `qa ids`

Parse all spec sources from the profile and emit canonical scenario records.

### `qa tests`

Scan the configured test roots, extract scenario IDs from test names, and report header annotations.

### `qa drift`

Validate spec/test consistency:

- parse errors
- implemented scenarios without tests
- tests referencing nonexistent specs
- files missing `@qa-spec` / `@qa-suite` headers

### `qa coverage`

Generate a summary report from the spec and test inventories. Write to the profile's `output.coverage` path unless `--output` overrides it.

## Notes

- Keep repo-specific seed, auth, and result-sink logic outside this runtime.
- This command is intentionally deterministic and profile-driven.
- Use repo-local commands declared in `commands` for execution and result-sink
  sync. `qa` remains responsible for parse, scan, drift, and coverage.
