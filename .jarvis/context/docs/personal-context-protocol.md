# Personal Context Protocol

How personal (per-contributor) context is managed alongside shared (git-tracked)
project context in the Flow Network workspace.

## Principle

`AGENTS.md` and all git-tracked files must contain **zero machine-specific paths**
or user-specific configuration. Personal context lives in gitignored locations
and is never committed.

## Shared vs Personal Boundary

| Layer | Location | Git Status | Contains |
|---|---|---|---|
| Shared project context | `.jarvis/context/**` (tracked files) | Tracked | Architecture, specs, plans, decisions, goals, priorities, constraints, blockers, partners, delegation, projects |
| Personal Jarvis root files | `.jarvis/context/{preferences,patterns,calendar,recurring,focus}.md` | Gitignored | Individual work style, schedule, personal task tracking |
| Machine-specific overrides | `.jarvis/context/local.md` | Gitignored | External project paths, local tool locations, machine-specific config |
| Private contributor space | `.jarvis/context/private/<username>/` | Gitignored | Free-form personal notes, drafts, scratch space |

## Setup

Run `pnpm setup` to configure personal context interactively. The setup script will:

1. Create `local.md` from the template, prompting for external project paths
2. Create your `private/<username>/` namespace
3. Optionally create personal Jarvis root files

You can also set up manually:

    cp .jarvis/context/local.md.example .jarvis/context/local.md
    mkdir -p .jarvis/context/private/$(whoami)

## `local.md` Format

`local.md` uses a simple markdown table format that agents can parse:

    # Local Context (Machine-Specific)

    ## External Projects

    | Project | Local Path | Notes |
    |---|---|---|
    | Jarvis CLI | /your/path/to/jarvis | Python 3.11+, use `uv run jarvis <command>` |

    ## Environment Notes

    - Node version manager: nvm / fnm / volta
    - Python environment: uv

## Rules for AGENTS.md

1. Never add absolute filesystem paths (e.g., `/Users/someone/...`).
2. Never add machine-specific tool versions or locations.
3. Reference `local.md` when context is inherently per-machine.
4. External project descriptions belong in AGENTS.md; their paths belong in `local.md`.
