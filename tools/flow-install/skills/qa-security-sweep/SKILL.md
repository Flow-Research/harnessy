---
name: qa-security-sweep
description: "Adversarial QA audit that turns security findings for a feature, module, or diff into canonical Layer:security regression scenarios and archived findings."
disable-model-invocation: false
allowed-tools: Read, Write, Grep, Glob, Bash, ApplyPatch
argument-hint: "[<feature-slug>|--diff <ref>|--pr <number>] [--write] [--severity-floor critical|high|medium|low]"
---

# QA Security Sweep

## Purpose

Treat security testing as a first-class QA layer. The skill reviews a feature,
module, or diff with an adversarial mindset, then emits findings as canonical
`Layer: security` regression scenarios that can be tracked by `qa drift`
and implemented as browser/API/security tests.

Template paths are resolved from `${AGENTS_SKILLS_ROOT}/qa-security-sweep/`.

## Scope

Inspect every relevant layer in the target repo:

- frontend UI, client state, browser storage, forms, URLs, iframes, messages
- backend route handlers, controllers, server actions, jobs, webhooks
- authn/authz, sessions, role checks, tenant isolation, policy enforcement
- database queries, migrations, RLS/policies, secrets, audit logs
- integrations, webhooks, credential handling, replay protection
- infrastructure headers/config, environment handling, CI/CD, dependencies
- business logic, state machines, race conditions, workflow bypasses

## Steps

1. Follow `${AGENTS_SKILLS_ROOT}/qa-security-sweep/commands/qa-security-sweep.md`.
2. Load the QA profile and feature catalog when present.
3. Identify existing scenarios and tests for the target feature/prefix.
4. Build a threat model before writing scenarios.
5. Propose `Layer: security` scenarios using canonical IDs and the shared
   `Security Class:` vocabulary.
6. Archive the full findings report under `qa/security/findings/` when the
   repo uses that convention, or under the QA profile's configured security
   output path when present.
7. With `--write`, append scenarios to the relevant regression spec files and
   run `qa drift`.

## Guardrails

- Do not actively exploit live infrastructure.
- Do not include real secrets, tokens, customer data, or production identifiers.
- Prefer testable regression scenarios over vague prose findings.
- Model exploit chains when individually low-severity issues compose into a
  higher-risk path.
- Use repo-local fixture IDs and helper patterns when proposing tests.
