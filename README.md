# Harnessy

Harnessy is a reusable agent harness for software projects.

It installs a shared AI operating layer into a repo so supported coding agents can discover the same skills, context, commands, and verification surfaces.

## Overview

Harnessy gives a repository:

- a minimal root `AGENTS.md` pointer plus a full protocol in `.jarvis/context/AGENTS.md`
- a shared context vault and memory system under `.jarvis/context/`
- shared Harnessy skills installed globally in `~/.agents/skills/`
- optional project-local skills in `.agents/skills/`
- generated lifecycle scripts for registration, validation, sync, and verification
- global command shims in the user-local bin directory such as `jarvis`, `flow-qa`, and `flow-deps`
- registration parity across OpenCode, Claude Code, and Codex
- installation verification harnesses for local and remote-style bootstrap flows
- Meta-Harness capabilities, including skill auto-improvement

## Key Features

- Shared skill distribution from `tools/flow-install/skills/`
- Project-local skill registration from `.agents/skills/`
- Cross-agent registration for OpenCode, Claude Code, and Codex
- Context vault scaffolding in `.jarvis/context/`
- File-based scoped memory under `.jarvis/context/scopes/`
- Optional Autoflow GitHub Actions setup during install
- Pipeline hooks and helper script installation
- Explicit dependency management for skill runtimes via `flow-deps`
- Deterministic QA runtime via `flow-qa`

## Repository Layout

```text
.
├── install.sh                  # bootstrap + in-place installer entrypoint
├── jarvis-cli/                 # Jarvis CLI source
├── scripts/flow/               # generated/project lifecycle scripts
├── tests/harness/              # install and verification harnesses
└── tools/flow-install/
    ├── index.mjs               # core installer
    ├── lib/                    # installer/runtime shared logic
    ├── templates/              # install templates
    └── skills/                 # shared Harnessy skills
```

## What Gets Installed

After in-place installation into a target repo, the baseline structure looks like this:

```text
.
├── AGENTS.md
├── .agents/
│   └── skills/                 # project-local skills (optional)
├── .jarvis/
│   └── context/
│       ├── README.md
│       ├── AGENTS.md
│       ├── technical-debt.md
│       ├── skills/_catalog.md
│       ├── scopes/_scopes.yaml
│       ├── private/<username>/
│       └── ...
└── package.json scripts
    ├── skills:register
    ├── skills:validate
    ├── harness:verify
    └── postinstall
```

Global/shared assets are installed for the local user:

- shared skills: `~/.agents/skills/`
- Claude symlinks: `~/.claude/skills/`
- Codex links: `~/.codex/skills/harnessy/`
- user-local command shims: `$XDG_BIN_HOME` or `~/.local/bin`
- lifecycle helper scripts: `~/.scripts/`

## Requirements

### For installing Harnessy

- Node.js 18+
- pnpm 9+
- Git
- Python 3.11+
- `uv`

### Installed automatically when needed

- `uv` is installed by `install.sh` if missing

### Not installed automatically

- skill runtime dependencies declared in manifests

Harnessy now treats skill dependencies as explicit user-managed installs. Use `flow-deps` to inspect and install them after reviewing the plan.

Harnessy core skills are sourced from `tools/flow-install/skills/` and installed into `~/.agents/skills/`.
Project-specific skills stay in each repo's `.agents/skills/` directory and are copied into `~/.agents/skills/` by the generated scripts, which also refresh supported agent registrations.

If you need a curated active skill set, set `AGENTS_SKILLS_ROOT` to an alternate directory before running the registration scripts. Harnessy will use that directory instead of the default `~/.agents/skills/`.

## Installation

### Option 1: Bootstrap a full Harnessy workspace

```bash
curl -fsSL https://raw.githubusercontent.com/Flow-Research/harnessy/main/install.sh | bash
```

This path:

- installs `uv` if needed
- verifies `node` and `pnpm`
- clones or updates a local Harnessy checkout
- installs `jarvis`
- runs `flow-install`
- installs shared skills and command shims
- optionally installs community skills

Useful environment variables:

| Variable | Purpose | Example |
|---|---|---|
| `FLOW_REPO_URL` | Override the Harnessy git source | custom fork URL |
| `FLOW_INSTALL_DIR` | Workspace clone destination | `/Users/name/harnessy` |
| `FLOW_CACHE_DIR` | Cache used for in-place installs | `$HOME/.cache/harnessy` |
| `FLOW_NONINTERACTIVE` | Skip prompts | `1` |
| `FLOW_SKIP_SUBPROJECTS` | Skip optional bundled sub-project logic | `1` |

Example:

```bash
FLOW_INSTALL_DIR="$HOME/work/harnessy" \
FLOW_NONINTERACTIVE=1 \
FLOW_SKIP_SUBPROJECTS=1 \
bash -c "$(curl -fsSL https://raw.githubusercontent.com/Flow-Research/harnessy/main/install.sh)"
```

### Option 2: Install Jarvis only

```bash
uv tool install --force "git+https://github.com/Flow-Research/harnessy.git#subdirectory=jarvis-cli"
jarvis --help
```

### Option 3: Install Harnessy into an existing repository

From the target repo root:

```bash
curl -fsSL https://raw.githubusercontent.com/Flow-Research/harnessy/main/install.sh | bash -s -- --here
```

Or target another repo explicitly:

```bash
curl -fsSL https://raw.githubusercontent.com/Flow-Research/harnessy/main/install.sh | bash -s -- --target "/path/to/project"
```

This mode:

- treats the target repository as the install destination
- installs `jarvis`
- uses a cached Harnessy checkout as installer source
- scaffolds the context vault and memory files
- installs shared skills globally
- generates project lifecycle scripts and package scripts
- skips community skill installation by default for a leaner in-place install path

If the repo already has `harnessy.lock.json` and you want to re-ask path prompts:

```bash
curl -fsSL https://raw.githubusercontent.com/Flow-Research/harnessy/main/install.sh | bash -s -- --here --reconfigure
```

Local equivalent:

```bash
node tools/flow-install/index.mjs --yes --target "/path/to/project"
```

## Core Commands

### Root development commands

| Command | Purpose |
|---|---|
| `pnpm setup` | Run local setup wizard |
| `pnpm skills:validate` | Validate shared skill source and catalog consistency |
| `pnpm skills:register` | Register project-local skills for supported agents |
| `pnpm skills:register:claude` | Refresh Claude skill registration |
| `pnpm skills:register:opencode` | Refresh OpenCode `skills.paths` |
| `pnpm skills:register:codex` | Refresh Codex skill links |
| `pnpm harness:verify` | Verify repo and runtime parity |
| `pnpm harness:eval` | Run local fixture-based install evaluation |
| `pnpm harness:eval:remote` | Run remote-style Docker bootstrap evaluation |
| `pnpm flow:cleanup` | Clean stale plugin artifacts |
| `pnpm flow:sync` | Re-run in-place sync from cached source |
| `pnpm flow:sync:force` | Force in-place sync |
| `pnpm flow:sync:remote` | Refresh cached source, then sync |
| `pnpm flow:sync:remote:force` | Refresh cached source, then force sync |

### Shared CLI tools installed through skills

| Command | Purpose |
|---|---|
| `jarvis` | User-facing CLI for planning, journaling, context operations, reading lists, Android tooling, and more |
| `flow-qa` | Deterministic QA runtime for spec parsing, test scanning, drift detection, and coverage from a repo-local profile |
| `flow-deps` | Plan, check, and explicitly install runtime dependencies declared in skill manifests |

## Command Examples

```bash
# Install or refresh shared skills only
node tools/flow-install/index.mjs --skills --yes

# Preview installer changes
node tools/flow-install/index.mjs --dry-run

# Update only the managed block in .jarvis/context/AGENTS.md
node tools/flow-install/index.mjs --update-context-agents

# Check dependencies for one skill manifest
flow-deps check --manifest "tools/flow-install/skills/goal-agent/manifest.yaml"

# Audit all installed shared skills
flow-deps check --skills-root "$HOME/.agents/skills"

# Parse QA specs from a repo-local profile
flow-qa ids --profile .harnessy/qa-profile.json

# Run a QA drift check
flow-qa drift --profile .harnessy/qa-profile.json
```

## Architecture

### 1. Installer

`tools/flow-install/index.mjs` is the idempotent installer. It handles:

- shared skill install and registration
- project script generation
- package.json patching
- context vault scaffolding
- memory system install
- `AGENTS.md` merge
- optional Autoflow workflow setup
- hook and pipeline helper install
- cron registration from skill manifests
- lockfile writing

### 2. Shared skills

Shared reusable skills live in:

```text
tools/flow-install/skills/
```

They are copied into the active global skills root, usually:

```text
~/.agents/skills/
```

If you need a curated active skill set, set `AGENTS_SKILLS_ROOT` before registration or install.

### 3. Project-local skills

Project-specific skills live in:

```text
.agents/skills/
```

They are not part of shared Harnessy core. The generated `skills:register` script copies them into the active global skills root and refreshes supported agent registrations.

### 4. Context vault

Every installed project gets:

```text
.jarvis/context/
```

Important files:

- `README.md` - context loading protocol
- `AGENTS.md` - full Harnessy protocol for the installed repo
- `technical-debt.md` - tracked debt register
- `skills/_catalog.md` - skill registry for the repo
- `scopes/_scopes.yaml` - memory scope registry
- `private/<username>/` - gitignored personal space

### 5. Memory system

The memory system is file-based and scoped.

Core hierarchy:

- `org:<git-org>`
- `project:<repo-name>`
- `user:<username>` via `.jarvis/context/private/<username>/`

Memory record types:

- `fact`
- `decision`
- `preference`
- `event`

### 6. Dependency model

Skill manifests can declare runtime dependencies such as:

- shell tools via `dependencies:`
- Python packages via `python_packages:`
- Node packages via `node_packages:`

Harnessy does not silently provision these anymore. Use `flow-deps` to inspect and explicitly install what a skill needs.

## Verification

### Standard verification

```bash
pnpm skills:register
pnpm harness:verify
```

`pnpm harness:verify` checks:

- `AGENTS.md` and `.jarvis/context/AGENTS.md` presence and protocol wiring
- context and memory files under `.jarvis/context/`
- lifecycle scripts and package wiring
- `jarvis` on `PATH`
- global skills directory presence
- OpenCode, Claude, and Codex registration parity
- every declared core skill is installed and discoverable
- project-local skills, when present, are visible to supported agents
- community skill inventory behavior from `harnessy.lock.json`

### Acceptance harnesses

For heavier install validation:

```bash
pnpm harness:eval
pnpm harness:eval:remote
```

These cover local fixture installs, reruns, isolated home directories, remote-style Docker bootstrap, and agent-surface parity. More details live in `tests/harness/README.md`.

## Local Development

### Repository setup

```bash
pnpm skills:validate
pnpm skills:register
pnpm harness:verify
uv tool install --force ./jarvis-cli
jarvis --help
```

<<<<<<< HEAD
### Useful iteration loops
=======
### Core commands

| Command | Purpose |
|---|---|
| `pnpm skills:validate` | Validate shared skill source and catalog consistency |
| `pnpm skills:register` | Copy project-local skills into `~/.agents/skills/` and refresh supported agent registrations |
| `pnpm skills:register:claude` | Rebuild Claude marketplace metadata from `~/.agents/skills/` |
| `pnpm skills:register:opencode` | Rebuild OpenCode `skills.paths` from `~/.agents/skills/` |
| `pnpm skills:register:codex` | Rebuild Codex skill links from `~/.agents/skills/` |
| `pnpm flow:sync` | Re-run the Harnessy installer from the cached local Harnessy checkout |
| `pnpm flow:sync:remote` | Pull the latest Harnessy changes into the cache, then reinstall in-place |
| `pnpm flow:sync:force` | Force a stronger in-place reinstall from the cached local Harnessy checkout |
| `pnpm flow:sync:remote:force` | Pull latest Harnessy changes into the cache, then force a stronger in-place reinstall |
| `pnpm flow:cleanup` | Clean stale plugin artifacts from old registrations |
| `pnpm harness:verify` | Verify repo and supported agent harness parity |
| `pnpm harness:eval` | Run isolated fixture-based Harnessy installation acceptance checks |
| `pnpm harness:eval:remote` | Run remote-style Docker bootstrap validation using `install.sh` |
| `uv tool install --force ./jarvis-cli` | Install the local Jarvis CLI build |
| `node tools/flow-install/index.mjs --yes` | Install Harnessy into the current repo |
| `node tools/flow-install/index.mjs --dry-run` | Preview install changes |

## Architecture

### 1. Jarvis CLI

`jarvis-cli/` is the user-facing agent CLI.

Install paths:

- local workspace: `uv tool install --force ./jarvis-cli`
- GitHub: `uv tool install --force "git+https://github.com/Flow-Research/harnessy.git#subdirectory=jarvis-cli"`

Jarvis currently provides task planning, journaling, reading-list workflows, context operations, and Android APK tooling.

### 2. Shared skills

Shared core skills live in:

```text
tools/flow-install/skills/
```

These are the source of truth for reusable skills shipped by the framework.

### 3. Project-local skills

Repo-specific skills live in:

```text
.agents/skills/
```

These are not part of the shared framework. They are owned by the target project and registered globally with the generated `skills:register` script.

### 4. Generated lifecycle scripts

`flow-install` installs helper scripts into the project in a configurable folder.

Default:

```text
scripts/flow/
```

These power:

- `skills:register`
- `skills:validate`
- `skills:register:claude`
- `skills:register:opencode`
- `skills:register:codex`
- `harness:verify`
- `postinstall`

Global convenience scripts are still installed into `$HOME/.scripts/`, but committed project wiring uses repo-local script paths so CI stays portable.

## Harness Verification

The install is only considered complete when both agent surfaces resolve the same harness.

Run:
>>>>>>> 755328e (feat: Codex runtime, jarvis-cli Anytype sync, worktree protocol (#34))

```bash
# Reinstall or refresh shared skills into your active skills root
node tools/flow-install/index.mjs --skills --yes

# Re-run full in-place installer against this repo
node tools/flow-install/index.mjs --yes

# Refresh the local Jarvis CLI build
uv tool install --force ./jarvis-cli
```

## Team Rollout

Recommended team workflow for an existing repository:

<<<<<<< HEAD
1. Install Harnessy in place:
=======
`pnpm harness:verify` checks:

- Harnessy section present in `AGENTS.md`
- full Harnessy protocol present in `.jarvis/context/AGENTS.md`
- core context and memory files under `.jarvis/context/`
- generated lifecycle scripts exist
- `package.json` wiring is present
- `jarvis` is available in `PATH`
- `~/.agents/skills/` exists
- lockfile components are recorded
- every shipped Harnessy core skill is installed globally and accessible to supported agent runtimes
- OpenCode `skills.paths` includes the required global skills path
- Claude marketplace and enabled plugin state exist
- Codex skill links exist under `~/.codex/skills/harnessy/`
- project-local skills, if present, are visible to supported agent runtimes
- community skills are checked from `harnessy.lock.json` using warn-or-strict behavior based on `communitySkills.strict`
- `community-skills-install --full` is validated from persisted inventory metadata in `~/.agents/community-install.json` and, when available, `harnessy.lock.json`

### 5. Context vault

Every installed project gets:

```text
.jarvis/context/
```

Important files:

- `README.md` - knowledge base protocol
- `AGENTS.md` - full Harnessy agent protocol for the installed repo
- `technical-debt.md` - tracked debt register
- `skills/_catalog.md` - local discovery layer
- `scopes/_scopes.yaml` - memory scope registry
- `private/<username>/` - gitignored personal space
- `local.md.example` - machine-specific template

### 6. Memory system

The memory system is file-based and scoped.

Current core hierarchy:

- `org:<git-org>`
- `project:<repo-name>`
- `user:<username>` via `.jarvis/context/private/<username>/`

Memory file types:

- `fact`
- `decision`
- `preference`
- `event`

## Installing Harnessy in a Team Project

Recommended team workflow:

1. From the target repo root, install Harnessy in place:
>>>>>>> 755328e (feat: Codex runtime, jarvis-cli Anytype sync, worktree protocol (#34))

```bash
curl -fsSL https://raw.githubusercontent.com/Flow-Research/harnessy/main/install.sh | bash -s -- --here
```

2. Commit generated files:

- `AGENTS.md`
- `.jarvis/context/`
- `harnessy.lock.json`
- any repo-local `.agents/skills/`

3. Have each engineer run the repo-local registration command:

```bash
pnpm skills:register
```

or the equivalent package-manager script in that repo.

4. If needed, apply newer managed context protocol explicitly later:

```bash
node tools/flow-install/index.mjs --update-context-agents
```

## Troubleshooting

### `jarvis` not found

```bash
uv tool install --force "git+https://github.com/Flow-Research/harnessy.git#subdirectory=jarvis-cli"
```

### `flow-qa` or `flow-deps` not found

Reinstall shared skills and ensure your user-local bin directory is on `PATH`:

```bash
node tools/flow-install/index.mjs --skills --yes
```

Harnessy uses `$XDG_BIN_HOME` when set, otherwise `~/.local/bin`.

### `pnpm skills:register` appears to do nothing

That usually means the current repo has no project-local skills in `.agents/skills/`. Shared skills are already installed globally by `flow-install`.

### Missing skill runtime dependencies

Inspect the dependency plan first:

```bash
flow-deps check --skills-root "$HOME/.agents/skills"
```

Then explicitly install what you approve:

```bash
flow-deps install --skills-root "$HOME/.agents/skills"
```

### Re-run installation into a repo

```bash
node /path/to/harnessy/tools/flow-install/index.mjs --yes
```

The installer is designed to be re-runnable and skip already-current parts.

## Contributing

Start here:

- `CONTRIBUTING.md`
- `.jarvis/context/docs/contribution-protocol.md`
- `.jarvis/context/templates/contribution/shared-skill-candidate-packet.md`

When changing shared functionality, update the shared source in this repository first, then verify it through the install harnesses.

## Source of Truth

This repository is the source repo for Harnessy.

- bootstrap entry point: `install.sh`
- installer source: `tools/flow-install/`
- shared skill source: `tools/flow-install/skills/`
- Jarvis package source: `jarvis-cli/`
