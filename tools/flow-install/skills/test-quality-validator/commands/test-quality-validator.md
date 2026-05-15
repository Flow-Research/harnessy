---
description: Validate tests against the canonical QA runtime, regression artifacts, and optional delivery-profile rules
argument-hint: "[--epic <epic_name>] [--suite <X>] [--api-only] [--browser-only] [--qa-profile .harnessy/qa-profile.json] [--profile .flow/delivery-profile.json]"
---

# Test Quality Validator Command

## Inputs

- canonical QA profile
- optional delivery profile for role and validator adapter rules
- optional epic or suite scoping

See `.jarvis/context/docs/standards/qa-process.md` for the shared QA contract this validator is expected to enforce.

## Workflow

1. Resolve the QA profile. Default to `.harnessy/qa-profile.json`, then `.flow/qa-profile.json`, then `qa/qa-profile.json`.
2. Run the deterministic drift preflight:

```bash
flow-qa drift --profile <qa-profile> --json
```

3. Treat these drift findings as quality defects:

- missing `@qa-spec` / `@qa-suite` headers
- non-canonical scenario IDs
- `Status: implemented` scenarios without matching tests
- tests referencing nonexistent specs

4. If acceptance-criteria coverage is part of the request, parse criteria with:

```bash
pnpm exec tsx ${AGENTS_SKILLS_ROOT}/spec-to-regression/scripts/extract-criteria.ts <spec-root>
```

5. Parse API regression scenarios with:

```bash
pnpm exec tsx ${AGENTS_SKILLS_ROOT}/api-integration-codegen/scripts/parse-api-regression.ts <api-regression-spec>
```

6. Run coverage and correctness validators:

```bash
pnpm exec tsx ${AGENTS_SKILLS_ROOT}/test-quality-validator/scripts/validate-coverage.ts ...
pnpm exec tsx ${AGENTS_SKILLS_ROOT}/test-quality-validator/scripts/validate-correctness.ts ...
```

7. Report a merged result that includes both runtime drift defects and validator findings.

## Completion criteria

- drift defects are surfaced as blocking issues
- false-green risks are identified explicitly
- coverage gaps are tied back to criteria or regression scenarios
- output is suitable for PR review or CI gating
