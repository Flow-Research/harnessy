---
name: dependency-manager
description: Plan, verify, and explicitly install skill and script runtime dependencies from Harnessy manifests.
disable-model-invocation: true
allowed-tools: Read, Bash
argument-hint: "[check|plan|install] [--manifest <path>|--skills-root <path>] [--json] [--dry-run] [--include-optional]"
---

# Dependency Manager

## Purpose
Provide an explicit dependency-management surface for Harnessy skills and scripts so runtime dependencies are checked, planned, and installed with user approval instead of silently provisioned.

## Inputs
- Optional subcommand: `check`, `plan`, or `install`
- Optional flags: `--manifest <path>`, `--skills-root <path>`, `--json`, `--dry-run`, `--include-optional`

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/dependency-manager/`.

## Steps
1. Follow the command contract in `${AGENTS_SKILLS_ROOT}/dependency-manager/commands/dependency-manager.md`.
2. Use the installed `flow-deps` command for deterministic dependency inspection.
3. Ask the user before invoking `flow-deps install ...` unless they explicitly requested installation.
4. Keep manifests as the source of truth for runtime requirements.
5. Use `--include-optional` when the user explicitly asks to install provider/capability extras.

## Output
- Dependency plans for one manifest or all installed skills.
- Availability and authentication checks for declared tools.
- Explicit installation results for missing packages or tools.
