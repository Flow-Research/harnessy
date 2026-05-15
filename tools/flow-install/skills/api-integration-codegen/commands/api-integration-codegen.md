---
description: Generate API integration suites from canonical QA regression specs using a QA profile plus optional delivery-profile adapters
argument-hint: "[--suite <X>] [--qa-profile .harnessy/qa-profile.json] [--profile .flow/delivery-profile.json] [--delta]"
---

# API Integration Codegen Command

## Inputs

- API regression spec from the active QA profile
- optional `--suite <X>` to scope generation
- optional `--qa-profile .harnessy/qa-profile.json`
- optional `--profile .flow/delivery-profile.json`

## Workflow

1. Resolve the QA profile. Default to `.harnessy/qa-profile.json`, then `.flow/qa-profile.json`, then `qa/qa-profile.json`.
2. Run a deterministic preflight:

```bash
qa ids --profile <qa-profile> --json
```

3. Load the optional delivery profile.
4. Resolve the API regression spec and generated suite destination from the QA profile and adapter data.
5. Parse the regression spec with:

```bash
pnpm exec tsx ${AGENTS_SKILLS_ROOT}/api-integration-codegen/scripts/parse-api-regression.ts <api-regression-spec> [--suite <X>]
```

6. Generate suite content with:

```bash
pnpm exec tsx ${AGENTS_SKILLS_ROOT}/api-integration-codegen/scripts/generate-api-suite.ts <api-scenarios-json> [--suite <X>] [--profile .flow/delivery-profile.json]
```

7. Write the output into the QA-profile-configured API suites directory.
8. Refine assertions, seeds, and unauthorized coverage where the scaffolder leaves TODOs.

## Completion criteria

- generated suite uses QA-profile paths and only delivery-profile-configured imports and helper modules
- scenario count matches the parsed regression source for the target suite
- unresolved assertions are called out explicitly
- generated scenarios preserve canonical ID references from the regression spec

## Decision Trace Protocol

This skill participates in the skill evolution system by capturing decision traces at gate resolutions and consulting accumulated feedback.

### Trace Consultation (short loop)

Before executing any step with a quality or human gate, query accumulated decision traces:

```bash
python3 "${AGENTS_SKILLS_ROOT}/_shared/trace_query.py" recent \
    --skill "api-integration-codegen" --gate "<gate_name>" --limit 5 --min-loops 1
```

If patterns or recent feedback exist, incorporate them as additional constraints. Do not cite traces to the user unless asked.

### Trace Capture (after gate resolution)

After every gate resolves, capture a decision trace:

```bash
python3 "${AGENTS_SKILLS_ROOT}/_shared/trace_capture.py" capture \
    --skill "api-integration-codegen" \
    --gate "<gate_name>" --gate-type "<human|quality>" \
    --outcome "<approved|rejected|passed|failed>" \
    --refinement-loops <N> \
    [--feedback "<user's feedback text>"] \
    [--category <CATEGORY>]
```

### Post-Run Retrospective

After completion, ask: **"Any feedback on this api-integration-codegen run? (skip to finish)"**
If provided, capture via trace_capture.py with gate "run_retrospective" and gate-type "retrospective".
