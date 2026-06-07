---
name: tmux-agent-launcher
description: "Launch Claude, OpenCode, or Codex in a named tmux session from the command line or agent workflows."
disable-model-invocation: true
allowed-tools: Read, Bash
argument-hint: "--runner <claude|opencode|codex> [session-name] [options] [--permission-mode bypass|default] [-- <runner-args>...]"
---

# Tmux Agent Launcher

## Purpose

Launch `claude`, `opencode`, or `codex` inside a named tmux session, attach to an existing named tmux session, or list tmux sessions, without re-implementing the logic in the skill.

## Inputs

- runner: `claude`, `opencode`, or `codex`
- optional session name; when omitted, prompt for a name defaulting to the current folder and generate `{name}-{runner}-{index}`
- optional mode: `attach`
- optional mode: `list`
- optional `--cwd <path>`
- optional `--attach`; launch mode attaches by default
- optional `--no-attach` to leave the new session detached
- optional `--dry-run`
- optional `--permission-mode <bypass|default>`; defaults to the per-user Harnessy install config, then `bypass`
- optional `--skip-permissions` / `--no-skip-permissions`
- optional `-- <runner-args>...`: arguments passed directly to the selected agent CLI

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/tmux-agent-launcher/`.

## Steps

1. Read the command contract at `${AGENTS_SKILLS_ROOT}/tmux-agent-launcher/commands/tmux-agent-launcher.md`.
2. Validate that the request includes a supported runner; session name is optional in launch mode.
3. Execute `tmux-agent-launcher` with the requested arguments.
4. Prefer `--json` when the caller needs machine-readable output.
5. Return the script output as-is rather than duplicating launch logic in the skill.

## Deterministic Logic (Scripts)

- Source of truth: `${AGENTS_SKILLS_ROOT}/tmux-agent-launcher/scripts/tmux-agent-launcher`
- Input contract: documented in the command contract
- Output contract: human mode and `--json`

## Output

- The launcher script's stdout/stderr and exit semantics.
