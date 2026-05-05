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
7. `docs/contribution-protocol.md` — contribution and maintenance workflow

For specialized maintenance tasks, read as needed:

8. `docs/personal-context-protocol.md`
9. `docs/reusable-script-standard.md`
10. `docs/skill-promotion-maintainer-playbook.md`
11. `docs/autoflow-autoresearch-system.md`

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
| `docs/standards/development-guidance.md` | Workspace engineering workflow guidance |
| `docs/standards/worktree-protocol.md` | Canonical gitignored project-container layout and `dev` branch standard |
| `docs/standards/technical-debt-tracking-standard.md` | Debt tracking structure reference |
| `docs/contribution-protocol.md` | Contribution workflow for skills, context, and tooling |
| `docs/reusable-script-standard.md` | Reusable-script authoring standard |
| `docs/skill-promotion-maintainer-playbook.md` | Maintainer workflow for skill promotion |
| `docs/personal-context-protocol.md` | Personal-context layout and ownership rules |
| `docs/autoflow-autoresearch-system.md` | Autoflow and autoresearch reference |

## Template Syntax

Files may start with `{{global}}`. This is a Jarvis CLI feature that includes
global context from `~/.jarvis/context/`. Other agents should treat `{{global}}`
as a no-op marker and read the rest of the file normally.

## Tiers

- Workspace-level (this directory): shared Harnessy truth
- Project-level (for example `some-app/.jarvis/context/`): project-specific
  overrides and implementation details
- Project-level files take precedence when working inside a specific sub-project

## Freshness Convention

Review files before relying on them for current decisions if they appear stale
relative to the code or install scripts they describe.
