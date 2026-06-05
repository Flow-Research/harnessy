# Harnessy Context AGENTS

This file contains Harnessy's installed agent protocol for this repository.

- Harnessy manages only the dedicated managed block below.
- You can add project-specific notes above or below the managed block.
- Future updates should merge only the managed block, never replace this file.

<!-- flow-context:start -->
## Harnessy Protocol

This repo is Harnessy-managed. Use this file as the canonical Harnessy agent protocol for the installed project.

### Session Start

1. Read `.jarvis/context/README.md`
2. Load context in order: `status.md` -> `roadmap.md` -> `team.md` -> `technical-debt.md`
3. For ideation, issue intake, PRD, roadmap, and architecture tradeoff work, read `.jarvis/context/docs/strategy/README.md` when it exists, then load the relevant strategy docs it points to
4. Treat `projects.md` and `decisions.md` as optional supporting docs when present
5. Check `.jarvis/context/skills/_catalog.md` for project catalog entries
6. For QA, testing, CI, deployment, or release work, read `.jarvis/context/docs/standards/qa-process.md`, `.jarvis/context/docs/standards/testing-strategy.md`, and `.jarvis/context/docs/standards/ci-process.md` when present
7. For substantial skill-backed work, read `.jarvis/context/docs/standards/skill-feedback-protocol.md`
8. Prefer deeper sub-project context when working inside a nested app with its own `.jarvis/context/`

### Skills

- Global skills live in `~/.agents/skills/`
- Project-local skills live in `.agents/skills/` when present
- Run `pnpm skills:register` after adding or updating project-local skills
- Run `pnpm harness:verify` to confirm Harnessy, community, and supported agent parity
- Before finalizing skill-backed work, capture reusable skill lessons with `skill-feedback` or the shared trace recorder. Do not create empty traces for uneventful successful runs.

### Context Vault

- Canonical context root: `.jarvis/context/`
- Standard strategy folder: `.jarvis/context/docs/strategy/`
- Memory scope registry: `.jarvis/context/scopes/_scopes.yaml`
- Technical debt register: `.jarvis/context/technical-debt.md`
- Runtime profiles: `.jarvis/context/profiles/qa.json`, `.jarvis/context/profiles/ci.json`, `.jarvis/context/profiles/deploy.json`
- Template token `{{global}}` is Jarvis templating; treat it as a no-op in raw files

### Testing And Deployment

- Prefer full integration and container-backed tests over mocks. Use Testcontainers first, Docker Compose when a full multi-service stack is needed, and document any mock exception.
- Treat QA drift, test-quality validation, semantic versioning, packaging, deployment, smoke checks, rollback, and evidence capture as CI/profile-driven gates.
- Local deployment overrides must run the same gates as CI unless the profile explicitly documents a stronger break-glass policy.
- Treat missed skill steps, brittle assumptions, manual workarounds, deterministic-command gaps, provider/runtime gaps, security/package issues, and repeated user corrections as mandatory skill feedback capture triggers.

### Conventions

- Never commit `.env` files; use `.env.example`
- Personal context belongs in `.jarvis/context/private/<username>/`
- Keep debt tracked in the debt registers, not only in chat or TODO comments
<!-- flow-context:end -->
