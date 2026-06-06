---
name: service-deploy
description: "Plan, package, verify, deploy, inspect, and roll back services using Harnessy CI/deploy profiles with Hostinger as the first provider adapter."
disable-model-invocation: false
allowed-tools: Read, Grep, Glob, Bash
argument-hint: "plan|check|configure|targets|ssh-setup|package|deploy|status|logs|rollback [--env <name>] [--json] [--dry-run] [--local-override]"
---

# Service Deploy

## Purpose

Provide a Harnessy-standard deployment capability that is CI/profile/evidence
driven. The skill normalizes deployment planning, packaging, provider policy,
Hostinger adapter selection, smoke evidence, and rollback records behind the
`harness-deploy` command.

## Inputs

- `.jarvis/context/profiles/ci.json`
- `.jarvis/context/profiles/deploy.json`
- optional `.jarvis/context/profiles/qa.json`
- command intent: `plan`, `check`, `configure`, `targets`, `ssh-setup`, `package`, `deploy`, `status`, `logs`, or `rollback`

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/service-deploy/`.

## Steps

1. Read `${AGENTS_SKILLS_ROOT}/service-deploy/commands/service-deploy.md`.
2. Run `${AGENTS_SKILLS_ROOT}/service-deploy/scripts/harness-deploy <command>` for deterministic behavior.
3. For deployment work, prefer CI tag-driven execution. Use `--local-override` only when the user explicitly asks for local deploy.
4. Do not call raw Hostinger tools directly unless the Harnessy wrapper instructs you to do so.
5. Treat billing, purchase, destructive deletion, destructive backup restore, and DNS mutation as out of scope for v1.
6. Treat Docker Compose, systemd, static, managed Node, and generic process deployment as runtime modes selected by `.jarvis/context/profiles/deploy.json`.
7. Use `harness-deploy configure` for gitignored local provider credential setup, `harness-deploy targets` for read-only Hostinger VPS discovery, and `harness-deploy ssh-setup` for SSH key attachment/verification.
8. Preserve evidence under `.jarvis/context/deployments/<run-id>/` when persistence is enabled.

## Deterministic Logic

- `scripts/harness-deploy`
  - Input: CI/deploy profile files plus command flags.
  - Output: human summary or JSON with profile paths, gate results, package hash, provider target, and evidence path.
  - Side effects: `package`, `deploy`, and `rollback` may write deployment evidence under `.jarvis/context/deployments/`.

## Output

- Deployment plan, gate report, package metadata, deployment evidence, provider status/log summary, or rollback evidence.
