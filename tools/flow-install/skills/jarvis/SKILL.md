---
name: jarvis
description: "Bridge to Jarvis CLI for scheduling, journaling, reading list orchestration, and context management."
disable-model-invocation: true
allowed-tools: Read, Write, ApplyPatch, Grep, Glob, Bash, WebFetch
argument-hint: "[command] [options]"
---

# Jarvis

## Purpose
Execute Jarvis CLI commands, orchestrate reading list reorganization, and manage Jarvis context initialization.

For reading list tasks, this skill acts as an **orchestrator** — the agent performs research and scoring using its own context and reasoning, with the CLI providing data extraction and write-back.

## Inputs
- Jarvis command and options

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/jarvis/`.

## Steps
1. Follow the command specification in `${AGENTS_SKILLS_ROOT}/jarvis/commands/jarvis.md` exactly.
2. For reading list reorganization, follow Path A (Agent-Orchestrated) in the command spec.
3. Create or update `jarvis.local.md` as required.

## Output
- Jarvis CLI output, prioritized reading lists, and any generated context files.
