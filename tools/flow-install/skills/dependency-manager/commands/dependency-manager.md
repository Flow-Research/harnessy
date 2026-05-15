---
description: Plan, verify, and explicitly install runtime dependencies from Harnessy manifests
argument-hint: "[check|plan|install] [--manifest <path>|--skills-root <path>] [--json] [--dry-run]"
---

# Dependency Manager Command

Use the installed `flow-deps` command as the canonical execution surface.

## Supported Manifest Fields

- `dependencies:` for external tools and auth checks
- `python_packages:` for Python runtime packages, as `package[:module],...`
- `node_packages:` for global Node packages, as `package,...`

## Commands

### `flow-deps check`

Check availability for one manifest or all manifests under a skills root.

### `flow-deps plan`

Emit the normalized dependency inventory without requiring everything to be installed.

### `flow-deps install`

Explicitly install missing dependencies. This command is opt-in and should only be run after user approval.

## Notes

- Prefer `--skills-root ~/.agents/skills` when auditing the full installed skill set.
- Prefer `--manifest <path>` when fixing one specific skill.
- For shell tools, the manifest's platform-specific `install:` command is treated as the source of truth.
