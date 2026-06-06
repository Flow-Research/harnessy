# CI And Deployment Process

## Purpose

This document defines the Harnessy baseline for CI, packaging, deployment, and
release evidence. Project repos may extend it, but should keep the shared shape
of profiles, gates, and deployment evidence.

## Profile Model

Machine-readable CI and deployment policy lives under the context vault:

```text
.jarvis/context/profiles/ci.json
.jarvis/context/profiles/deploy.json
```

The QA profile lives beside them:

```text
.jarvis/context/profiles/qa.json
```

Legacy `.harnessy/qa-profile.json`, `.flow/qa-profile.json`, and
`qa/qa-profile.json` paths are compatibility inputs only.

## Standard CI Gates

The default CI path is:

1. preflight and dependency checks
2. lint and typecheck
3. `qa drift`
4. `qa coverage`
5. `/test-quality-validator`
6. container-backed integration tests from the QA profile
7. security checks
8. semantic version and changelog validation
9. package
10. deploy canary
11. smoke verify
12. promote production
13. capture evidence

Production deployment should default to `vX.Y.Z` tags. Pull requests verify but
do not deploy production. Manual dispatch can deploy or roll back only when the
profile allows it and the command captures evidence.

## Deployment Strategy

Default strategy is canary then promote. Blue-green is an optional strategy when
the provider or runtime supports two production pools and traffic switching.

Deployment runtime is a profile choice, not a hard-coded Harnessy assumption.
Docker Compose is preferred when a project benefits from a reproducible
container boundary, but services may also deploy as systemd-managed processes,
static build artifacts, managed Node apps, or provider-native process targets.
All runtime modes must share the same gate, package, evidence, smoke, and
rollback contract.

Local deployment override is allowed only when explicitly requested and must run
the same gates as CI. It is not a shortcut around QA, semver, packaging, or smoke
verification.

## Packaging Contract

Packaging should adapt to repo structure:

- static app: package the configured build output
- Node app: package the app root, build output, lockfile, and runtime metadata
- Docker Compose/VPS: package compose files, env examples, and deploy manifests
- systemd/VPS: package app files, service metadata, reverse-proxy metadata, env examples, and deploy manifests
- generic process runtime: package app files plus start/healthcheck metadata

Packages must exclude `.env`, `.git`, `node_modules`, caches, local artifacts,
and secret candidates. Every package should produce a deterministic hash.

## Provider Contract

Harnessy deployment commands use provider adapters behind a normalized contract.
Hostinger is the first adapter, using official MCP/API surfaces where available.
Provider adapters must normalize:

- provider name and adapter type
- deployment id
- target environment and URL
- status and logs summary
- smoke result
- rollback target
- raw provider response path

Billing, purchasing, destructive deletion, destructive backup restore, and DNS
mutation are forbidden in v1 unless a future profile explicitly adds guarded
approval semantics.

## Evidence

Deployment evidence should be written under:

```text
.jarvis/context/deployments/<run-id>/
```

At minimum, evidence should include:

- CI/deploy profile snapshot
- QA gate summary
- semver tag or local override marker
- package hash
- provider deployment id or dry-run marker
- logs summary
- smoke result
- rollback target
- final status

Deployment evidence and package archives should be gitignored by default:

```text
.jarvis/context/deployments/
```

If a repo needs committed release evidence, commit a sanitized summary or
scorecard rather than raw provider responses, logs, or package archives.
