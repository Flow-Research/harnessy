# QA Process

## Purpose

This document is the canonical Harnessy-level QA process contract.

It defines the shared rules for:

- regression specs as source of truth
- canonical scenario IDs and fields
- test discovery and header requirements
- drift validation
- code generation expectations
- test-quality validation expectations

Project repos can extend this contract with repo-specific profiles, seed flows,
environment rules, and result sinks, but they should not redefine the shared
baseline semantics documented here.

## Core Model

Harnessy QA has three layers:

1. **Regression specs** describe what should be tested.
2. **Tests** implement those scenarios in code.
3. **Runtime validation** detects drift and coverage gaps.

The canonical deterministic runtime is `flow-qa`.

## Source Of Truth

- Regression specs are the source of truth for scenario intent.
- Tests must map back to canonical scenario IDs.
- Drift between specs and tests is a defect, not a documentation nicety.

Generated or derived artifacts should have one owning command and should not be
hand-edited when the runtime owns them.

## QA Profile Contract

Harnessy resolves QA configuration from a repo-local JSON profile. Default lookup order:

1. `.harnessy/qa-profile.json`
2. `.flow/qa-profile.json`
3. `qa/qa-profile.json`

The profile must define:

- regression spec paths
- app IDs
- browser test roots
- API test roots
- optional output paths such as coverage reports

The QA profile is the canonical runtime input. Adapter metadata in files such as
`.flow/delivery-profile.json` may enrich codegen or validation, but does not
replace the QA profile as the source of truth.

## Canonical Scenario IDs

Scenario IDs must use the canonical form:

```text
<PREFIX>-<NNN>
```

Rules:

- `PREFIX` is 2-5 uppercase alphanumeric characters starting with a letter
- `NNN` is a zero-padded three-digit sequence number

Examples:

- `AUTH-001`
- `MATCH-014`
- `E2E-005`

Non-canonical IDs are drift defects.

## Minimum Spec Fields

Harnessy regression specs should use `##` headings plus a top field block.

Minimum expected fields:

- `Layer:`
- `Status:`
- `Test File:` when implemented or scaffolded

Common optional fields:

- `Linked Refs:`
- `User Flow:`
- `Role:`
- `Route:`
- `DB Assert:`
- `Expected:`
- `Security Class:`
- `Threat Actor:`

## Layers

Shared layer vocabulary:

- `browser`
- `api`
- `security`
- `manual`

Meaning:

- `browser`: user-visible workflows and browser automation
- `api`: backend logic, authorization, workflow transitions, DB invariants
- `security`: adversarial security scenarios
- `manual`: human-only scenarios with no automated implementation

## Test Header Contract

Automated test files must include top-level annotations near the start of the file:

```ts
// @qa-spec: qa/<layer>/scripts/<file>.md
// @qa-suite: <PREFIX> (<slug>)
```

Missing `@qa-spec` or `@qa-suite` headers are quality defects.

## Drift Contract

`flow-qa drift` is the shared deterministic drift gate.

At minimum, it must surface:

- spec parse errors
- implemented scenarios without tests
- tests referencing nonexistent spec scenarios
- files missing `@qa-spec` / `@qa-suite` headers

Teams may add stricter project-local rules, but these are the baseline Harnessy-wide defects.

## Codegen Contract

`/browser-integration-codegen` and `/api-integration-codegen` must:

- treat the QA profile as the canonical regression input
- preserve canonical scenario IDs
- use adapter metadata only for imports, fixtures, helper modules, and project-specific test shims
- leave explicit TODOs instead of guessing selectors, assertions, or auth setup

Codegen should not silently invent non-canonical scenarios or bypass runtime drift expectations.

## Validator Contract

`/test-quality-validator` must treat these as quality defects:

- missing `@qa-spec` / `@qa-suite` headers
- non-canonical scenario IDs
- `Status: implemented` scenarios without matching tests
- tests referencing nonexistent specs

It should combine those runtime defects with:

- coverage completeness
- false-green risk detection
- role and authorization coverage
- project adapter rule violations when configured

## Recommended Workflow

1. Write or update regression specs.
2. Run `flow-qa ids` to confirm the spec parses.
3. Generate or update tests.
4. Run `flow-qa tests` and `flow-qa drift`.
5. Run `/test-quality-validator` for higher-level quality review.
6. Fix drift or validator findings before claiming QA completeness.

## Project Extensions

Project repos can extend the shared contract with:

- seed and login preparation flows
- remote environment policies
- result sinks such as spreadsheets or dashboards
- app-specific role inventories
- local runbooks for release QA

Those extensions should live in the project repo, not in this shared standard.
