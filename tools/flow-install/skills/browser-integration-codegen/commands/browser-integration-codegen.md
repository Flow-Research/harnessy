---
description: Generate browser integration suites from canonical QA regression specs using a QA profile plus optional delivery-profile adapters
argument-hint: "[--suite <NN>] [--qa-profile .harnessy/qa-profile.json] [--profile .flow/delivery-profile.json] [--delta] [--inspect-first]"
---

# Browser Integration Codegen Command

## Inputs

- browser regression spec from the active QA profile
- optional `--suite <NN>` to scope generation
- optional `--qa-profile .harnessy/qa-profile.json`
- optional `--profile .flow/delivery-profile.json`

## Workflow

1. Resolve the QA profile. Default to `.harnessy/qa-profile.json`, then `.flow/qa-profile.json`, then `qa/qa-profile.json`.
2. Run a deterministic preflight:

```bash
flow-qa ids --profile <qa-profile> --json
```

3. Load the optional delivery profile when fixture imports, route helpers, or DOM inspection adapters are needed.
4. Resolve the browser regression spec, optional DOM inspection path, and generated suite destination.
5. Parse the regression spec with:

```bash
pnpm exec tsx ${AGENTS_SKILLS_ROOT}/browser-integration-codegen/scripts/parse-regression.ts <browser-regression-spec> [--suite <NN>]
```

6. If DOM inspection artifacts exist, resolve selector inventories with:

```bash
pnpm exec tsx ${AGENTS_SKILLS_ROOT}/browser-integration-codegen/scripts/resolve-selectors.ts <inspection-dir>
```

7. Read the real page or component source for the routes under test.
8. Generate suite content with:

```bash
pnpm exec tsx ${AGENTS_SKILLS_ROOT}/browser-integration-codegen/scripts/generate-suite.ts <scenarios-json> [--suite <NN>] [--profile .flow/delivery-profile.json]
```

9. Write the generated suite into the QA-profile-configured browser suites directory.

## Completion criteria

- generated suite uses QA-profile paths and only delivery-profile-configured imports and fixture mappings
- selector strategy is source-verified or explicitly marked with TODOs
- destructive/read-only gating matches the regression spec semantics
- generated scenarios preserve canonical ID references from the regression spec

## Decision Trace Protocol

This skill participates in the skill evolution system by capturing decision traces at gate resolutions and consulting accumulated feedback.

### Trace Consultation (short loop)

Before executing any step with a quality or human gate, query accumulated decision traces:

```bash
python3 "${AGENTS_SKILLS_ROOT}/_shared/trace_query.py" recent \
    --skill "browser-integration-codegen" --gate "<gate_name>" --limit 5 --min-loops 1
```

If patterns or recent feedback exist, incorporate them as additional constraints. Do not cite traces to the user unless asked.

### Trace Capture (after gate resolution)

After every gate resolves, capture a decision trace:

```bash
python3 "${AGENTS_SKILLS_ROOT}/_shared/trace_capture.py" capture \
    --skill "browser-integration-codegen" \
    --gate "<gate_name>" --gate-type "<human|quality>" \
    --outcome "<approved|rejected|passed|failed>" \
    --refinement-loops <N> \
    [--feedback "<user's feedback text>"] \
    [--category <CATEGORY>]
```

### Post-Run Retrospective

After completion, ask: **"Any feedback on this browser-integration-codegen run? (skip to finish)"**
If provided, capture via trace_capture.py with gate "run_retrospective" and gate-type "retrospective".
