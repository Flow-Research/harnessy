---
description: Security QA sweep workflow that emits Layer:security regression scenarios
argument-hint: "[<feature-slug>|--diff <ref>|--pr <number>] [--write] [--severity-floor critical|high|medium|low]"
---

# QA Security Sweep Command

## Workflow

### 1. Resolve Scope

Scope can come from:

- a feature slug or ID prefix in the QA catalog
- `--diff <ref>` for local changes
- `--pr <number>` when the repo has a PR workflow
- current working tree diff as the default

Load:

- QA profile
- parsed specs: `qa ids --json`
- parsed tests: `qa tests --json`
- feature catalog and run-results if present
- relevant source, route, API, schema, migration, and auth files

### 2. Threat Model

Always produce:

- attacker profiles
- entry points
- trust boundaries
- sensitive assets
- existing controls
- assumptions and unknowns

### 3. Audit Classes

Check at least:

- `authn`
- `authz`
- `injection`
- `xss`
- `csrf`
- `crypto`
- `ratelimit`
- `businesslogic`
- `exposure`
- `supplychain`
- `config`
- `other`

### 4. Emit Regression Scenarios

Use this format:

```markdown
## <PREFIX>-<NNN> <one-line title>

Layer: security
Security Class: <class>
Threat Actor: <actor>
Attack Surface: <route/function/UI control>
Role: <role, if applicable>
Linked Refs: <related scenario IDs>
Status: not-implemented
Test File: <path to proposed test file>

Preconditions:
- ...

Exploitation:
1. ...
2. ...

Expected: <secure behavior to assert>
Impact (if not enforced): <what the attacker gains>
```

Browser-reachable attacks can live in browser specs. API-only, DB, webhook, and
RLS attacks should live in API or security specs according to the repo profile.

### 5. Archive

Write findings to `qa/security/findings/<yyyy-mm-dd>-<target>.md` when that
path exists or is consistent with the repo. Include severity summary and attack
chains.

### 6. Validate

With `--write`, run:

```bash
qa drift --profile <qa-profile>
```

If tests were added or edited, also run `/test-quality-validator`.

## Completion Criteria

- findings are expressed as concrete regression scenarios
- severity and security class are explicit
- exploit chains are separated from component-level findings
- no real secrets or live exploitation steps are present
- drift status is reported
