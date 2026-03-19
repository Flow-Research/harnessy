# Flow Network — Agent Instructions

## Workspace Structure

| Project | Path | Stack | Status |
|---------|------|-------|--------|
| Example Platform (POC) | `Focus/Flow/` | Python/FastAPI, React, Solidity, Base Chain | Active primary |
| Example Core (P2P Engine) | `Flow/` | Rust, libp2p, RocksDB, Axum, Qdrant | Phase 3 complete, paused |
| Jarvis CLI | `Jarvis/` | Python 3.11+, Click, AnyType/Notion | Active tooling |
| Knowledge Base | `knowledge-base/` | Python + Astro, GitHub Actions | Brainstorming |

## Installation

```bash
# Full Harnessy workspace bootstrap (after publishing flow-network)
./install.sh

# Install Jarvis CLI from this workspace
uv tool install --force ./Jarvis

# Install Flow framework into another project
node tools/flow-install/index.mjs --yes
```

## Context Loading

Read `.jarvis/context/README.md` for the knowledge base protocol. Start with `projects.md`, `focus.md`, `priorities.md` for orientation.

## Key Commands

| Project | Dev | Test | Lint |
|---------|-----|------|------|
| Focus/Flow backend | `cd Focus/Flow/backend && uvicorn app.main:app --reload` | `pytest` | `ruff check` |
| Focus/Flow frontend | `cd Focus/Flow/frontend && pnpm dev` | — | `pnpm lint` |
| Flow (Rust) | `cargo run -p flow-node` | `cargo test -p flow-node` | `cargo clippy -p flow-node -- -D warnings` |
| Jarvis CLI | `uv run jarvis <command>` | `uv run pytest` | `uv run ruff check` |

## Conventions

- **No `.env` commits** — each project has `.env.example`
- **Jarvis CLI** — always run via `uv run jarvis` or `uv run python -m jarvis`
- **`{{global}}`** in `.jarvis/context/` files is Jarvis CLI templating; treat as no-op
- **Sub-project agent files** — `Flow/AGENTS.md` and `Jarvis/AGENTS.md` have project-specific instructions; defer to them when working in those directories

## Skill Usage Protocol

- **For every user request**, check available skills (installed and installable) before proceeding.
- Sources of truth:
  - Global discovery: `${AGENTS_SKILLS_ROOT}` (synced via `pnpm skills:register`; default resolved from `scripts/skills-root.config.json`)
  - Catalog: `.jarvis/context/skills/_catalog.md`
- If a relevant skill exists, **use it** even when the user doesn't explicitly invoke a slash command.
- After adding or updating skills, run `pnpm skills:validate && pnpm skills:register`.
- For skills that call command docs, reference installed paths in `SKILL.md` as `${AGENTS_SKILLS_ROOT}/<skill-name>/commands/<file-name>.md`.
- Every `SKILL.md` must declare template resolution: `Template paths are resolved from ${AGENTS_SKILLS_ROOT}/<skill-name>/.`

## Technical Debt Tracking Law

- Treat intentional shortcuts, deferred migrations, and knowingly postponed cleanup as **tracked technical debt**, not informal notes.
- Maintain debt in `.jarvis/context/technical-debt.md` and per-epic in `.jarvis/context/specs/<epic>/tech_debt.md`.
- Every debt item must include: ID, status, type, scope, context, impact, proposed resolution, target phase, and links.
- Do not hide debt in chat responses or TODO comments alone. Persist it in the debt registers.
- When debt is resolved or accepted, update the status in the register.

## Personal Context

- Machine-specific config lives in `.jarvis/context/local.md` (gitignored). See `local.md.example` for the template.
- Per-contributor private space: `.jarvis/context/private/<username>/` (gitignored).
- Personal Jarvis files (`preferences.md`, `patterns.md`, `calendar.md`, `recurring.md`, `focus.md`) are gitignored.
- Full protocol: `.jarvis/context/docs/personal-context-protocol.md`.
- **Rule:** AGENTS.md must contain zero absolute filesystem paths. Reference `local.md` for per-machine values.

<!-- flow:start -->
## Harnessy Framework

> `FLOW_SKIP_SUBPROJECTS=true`

### Skill Usage Protocol

- Check available skills before proceeding on every request.
- Global skills: `~/.agents/skills/`
- Project skills: `.agents/skills/` (if present)
- Catalog: `.jarvis/context/skills/_catalog.md`
- Register: use the project skill scripts (for example `pnpm skills:register` or `npm run skills:register`) | Validate: the matching `skills:validate` script

### Context Vault

- Project context: `.jarvis/context/`
- Loading order: projects.md -> focus.md -> priorities.md -> goals.md -> decisions.md
- `{{global}}` in context files is Jarvis CLI templating; treat as no-op

### Memory System

- Scope registry: `.jarvis/context/scopes/_scopes.yaml`
- Scope resolution: most-specific match wins; user scope always highest priority
- Memory types: fact, decision, preference, event
- One file per scope per type

### Technical Debt Tracking

- Register: `.jarvis/context/technical-debt.md`
- Per-epic: `.jarvis/context/specs/<epic>/tech_debt.md`
- Required fields: ID, status, type, scope, context, impact, resolution, target, links

### Conventions

- No `.env` commits — use `.env.example`
- Personal context in `.jarvis/context/private/<username>/` (gitignored)
<!-- flow:end -->
