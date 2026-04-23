# Harnessy Context AGENTS

This file contains Harnessy's installed agent protocol for this repository.

- Harnessy manages only the dedicated managed block below.
- You can add project-specific notes above or below the managed block.
- Future updates should merge only the managed block, never replace this file.

<!-- flow-context:start -->
## Harnessy Protocol

This repo is Harnessy-managed. Use this file as the canonical agent protocol for
the installed project.

### Session Start

1. Read `.jarvis/context/README.md`
2. Check `.jarvis/context/skills/_catalog.md` for installed project catalog entries
3. Read `.jarvis/context/scopes/_scopes.yaml` when you need memory scope structure
4. For implementation work, read `.jarvis/context/docs/standards/development-guidance.md`
5. For contribution and maintenance workflows, read `.jarvis/context/docs/contribution-protocol.md`
6. Prefer deeper sub-project context when working inside a nested app with its own `.jarvis/context/`

### Skills

- Global skills live in `~/.agents/skills/`
- Project-local skills live in `.agents/skills/` when present
- Run `pnpm skills:register` after adding or updating project-local skills
- Run `pnpm harness:verify` to confirm Harnessy, OpenCode, and Claude parity

### Context Vault

- Canonical context root: `.jarvis/context/`
- Memory scope registry: `.jarvis/context/scopes/_scopes.yaml`
- Template token `{{global}}` is Jarvis templating; treat it as a no-op in raw files

### Conventions

- Never commit `.env` files; use `.env.example`
- Personal context belongs in `.jarvis/context/private/<username>/`
- Keep durable project guidance in tracked docs, not only in chat or TODO comments
<!-- flow-context:end -->
