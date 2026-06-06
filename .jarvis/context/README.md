# .jarvis/context/ — Knowledge Base Protocol

## Purpose

This directory is the canonical knowledge base for the Harnessy workspace. AI
agents, Jarvis CLI, and human contributors read these files for project context.

## Loading Order

For general context, read in this order:

1. `README.md` — protocol overview and file map
2. `AGENTS.md` — context-vault operating rules
3. `skills/_catalog.md` — installed project skill inventory
4. `scopes/_scopes.yaml` — scope registry for memory files

For development work, also read:

5. `docs/standards/development-guidance.md` — engineering workflow guidance
6. `docs/standards/worktree-protocol.md` — canonical `projects/<project>/dev` plus `projects/<project>/worktrees/` layout and branch model
7. `docs/standards/qa-process.md` — shared QA contract for specs, tests, drift, and codegen
8. `docs/standards/testing-strategy.md` — integration-first testing, Testcontainers preference, and mock exception policy
9. `docs/standards/ci-process.md` — CI, packaging, deployment, rollback, and evidence contract
10. `docs/standards/skill-feedback-protocol.md` — mandatory capture triggers for reusable skill lessons
11. `docs/contribution-protocol.md` — contribution and maintenance workflow

For specialized maintenance tasks, read as needed:

12. `docs/harnessy-positioning.md`
13. `docs/personal-context-protocol.md`
14. `docs/reusable-script-standard.md`
15. `docs/skill-promotion-maintainer-playbook.md`
16. `docs/autoflow-autoresearch-system.md`

## Canonical Root Files

| File | Role |
|------|------|
| `README.md` | Knowledge-base protocol and loading guidance |
| `AGENTS.md` | Context-vault agent instructions |
| `skills/_catalog.md` | Installed project skill inventory |
| `scopes/_scopes.yaml` | Scope registry for memory files |

## Standards And Reference Docs

| File | Role |
|------|------|
| `docs/harnessy-positioning.md` | Canonical Harnessy capability-harness positioning |
| `docs/standards/development-guidance.md` | Workspace engineering workflow guidance |
| `docs/standards/worktree-protocol.md` | Canonical gitignored project-container layout and `dev` branch standard |
| `docs/standards/qa-process.md` | Shared QA contract for profiles, specs, tests, drift, and validator expectations |
| `docs/standards/testing-strategy.md` | Shared testing strategy: integration-first, Testcontainers preferred, mocks by exception |
| `docs/standards/ci-process.md` | Shared CI, packaging, deployment, rollback, and evidence contract |
| `docs/standards/skill-feedback-protocol.md` | Mandatory trace capture triggers for reusable skill lessons |
| `docs/standards/technical-debt-tracking-standard.md` | Debt tracking structure reference |
| `docs/contribution-protocol.md` | Contribution workflow for skills, context, and tooling |
| `docs/reusable-script-standard.md` | Reusable-script authoring standard |
| `docs/skill-promotion-maintainer-playbook.md` | Maintainer workflow for skill promotion |
| `docs/personal-context-protocol.md` | Personal-context layout and ownership rules |
| `docs/autoflow-autoresearch-system.md` | Autoflow and autoresearch reference |
| `docs/operations/fathom-local-automation.md` | Local Fathom webhook + tunnel + auto-ingest runbook |

## Template Syntax

Files may start with `{{global}}`. This is a Jarvis CLI feature that includes
global context from `~/.jarvis/context/`. Other agents should treat `{{global}}`
as a no-op marker and read the rest of the file normally.

## Tiers

- Workspace-level (this directory): shared Harnessy truth
- Project-level (for example `some-app/.jarvis/context/`): project-specific
  overrides and implementation details
- Project-level files take precedence when working inside a specific sub-project

## Runtime Profiles

Machine-readable Harnessy runtime contracts live under `profiles/`:

| File | Role |
|------|------|
| `profiles/qa.json` | QA source paths, test roots, result outputs, and test environment policy |
| `profiles/ci.json` | CI gates, release trigger, and local override policy |
| `profiles/deploy.json` | Deployment apps, environments, provider adapters, and evidence policy |

Legacy `.harnessy/qa-profile.json`, `.flow/qa-profile.json`, and
`qa/qa-profile.json` are compatibility inputs only.

## Freshness Convention

Review files before relying on them for current decisions if they appear stale
relative to the code or install scripts they describe.
