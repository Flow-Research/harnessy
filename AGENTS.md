# Harnessy — Agent Instructions

## Workspace Structure

| Component | Path | Stack | Status |
|---------|------|-------|--------|
| Installer framework | `tools/flow-install/` | Node.js, generated scripts, skill distribution | Active |
| Jarvis CLI | `jarvis-cli/` | Python 3.11+, Click, AnyType/Notion | Active |
| Shared context vault | `.jarvis/context/` | Markdown, YAML, protocol docs | Active |
| Shared skills | `tools/flow-install/skills/` | Skill manifests, templates, scripts | Active |

## Installation

```bash
# Full Harnessy workspace bootstrap
./install.sh

# Install Jarvis CLI from this workspace
uv tool install --force ./jarvis-cli

# Install Harnessy into another project
node tools/flow-install/index.mjs --yes
```

## Context Loading

Read `.jarvis/context/README.md` for the knowledge base protocol. Start with the
root context files and standards docs there. Prefer deeper project-local context
when working inside a nested app.

## Key Commands

| Component | Dev | Test | Lint / Verify |
|---------|-----|------|------|
| Installer framework | `node tools/flow-install/index.mjs --dry-run` | `pnpm harness:eval` | `pnpm harness:verify` |
| Jarvis CLI | `uv run jarvis <command>` | `cd jarvis-cli && uv run pytest` | `cd jarvis-cli && uv run ruff check` |
| Root skills/context | — | `pnpm skills:validate` | `pnpm skills:register` |

## Conventions

- **No `.env` commits** — each component uses `.env.example`
- **Jarvis CLI** — always run via `uv run jarvis` or `uv run python -m jarvis`
- **`{{global}}`** in `.jarvis/context/` files is Jarvis CLI templating; treat as no-op
- **Sub-project agent files** — `jarvis-cli/AGENTS.md` and any nested project `AGENTS.md` files override root guidance in their directories

## Skill Usage Protocol

- **For every user request**, check available skills (installed and installable) before proceeding.
- Sources of truth:
  - Global discovery: `${AGENTS_SKILLS_ROOT}` (synced via `pnpm skills:register`; default resolved from `scripts/skills-root.config.json`)
  - Catalog: `.jarvis/context/skills/_catalog.md`
- If a relevant skill exists, **use it** even when the user doesn't explicitly invoke a slash command.
- After adding or updating skills, run `pnpm skills:validate && pnpm skills:register`.
- For skills that call command docs, reference installed paths in `SKILL.md` as `${AGENTS_SKILLS_ROOT}/<skill-name>/commands/<file-name>.md`.
- Every `SKILL.md` must declare template resolution: `Template paths are resolved from ${AGENTS_SKILLS_ROOT}/<skill-name>/.`

## Autoresearch Convention

Core skills include `autoresearch: enabled: true` in their `manifest.yaml` by
default. This enables the autonomous self-improvement ratchet loop via
`/autoflow`.

- **Protocol**: `${AGENTS_SKILLS_ROOT}/_shared/autoresearch.md` defines the three-file contract (editable skills / fixed evaluation / human control)
- **Metric**: Multiplicative composite score (`ratchet.py`) — weakness in any dimension drags the entire score
- **Hard gates**: Catastrophic failures and regressions are vetoes, not soft penalties
- **When creating skills**: `/skill-create` includes autoresearch by default. Set `time_budget_seconds` by blast_radius: high=1800, medium=1200, low=600
- **Human control**: `program.md` at the repo root steers the loop. Agents read it every iteration but never modify it.

## Personal Context

- Machine-specific config lives in `.jarvis/context/local.md` (gitignored). See `local.md.example` for the template.
- Per-contributor private space: `.jarvis/context/private/<username>/` (gitignored).
- Personal contributor notes should live under `.jarvis/context/private/<username>/` rather than shared root files.
- Full protocol: `.jarvis/context/docs/personal-context-protocol.md`.
- **Rule:** AGENTS.md must contain zero absolute filesystem paths. Reference `local.md` for per-machine values.

<!-- flow:start -->
## Harnessy Framework

> `FLOW_SKIP_SUBPROJECTS=true`

This repo is Harnessy-managed.

- Read `.jarvis/context/README.md`
- Read `.jarvis/context/AGENTS.md`
- Global skills: `~/.agents/skills/`
- Project skills: `.agents/skills/` (if present)
- If inside a sub-project, prefer its local `.jarvis/context/`
<!-- flow:end -->
