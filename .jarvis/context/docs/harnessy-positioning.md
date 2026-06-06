# Harnessy Positioning

## Canonical Definition

Harnessy is Flow's agent capability harness for software projects and agent runtimes.

It packages context, skills, commands, QA surfaces, dependency contracts, runtime adapters, and project protocols so supported agents can do real work safely and consistently.

Repo installation is the default mode, but not the whole identity. Harnessy also provides the capability, profile, adapter, and verification layer that Jarvis, Garden, Workstream, and compatible agent hosts can reuse.

## What Harnessy Owns

- Capability packs: skills, scripts, command shims, context templates, hooks, cron jobs, QA profiles, permissions, and dependency checks.
- Install profiles: repo, user, agent host, runtime, and CI shapes.
- Runtime adapters: Claude Code, Codex, OpenCode, Jarvis, Garden, MCP, and future hosts.
- Verification harnesses: inventory, dependencies, auth, context, host registration, execution probes, QA contracts, and capability-specific health.
- Repo protocols: `AGENTS.md`, `.jarvis/context/`, shared and project-local skills, and project-specific operating guidance.

## Relationship To Other Flow Layers

- Harnessy prepares and verifies project, host, and runtime capabilities.
- Jarvis governs human-agent work sessions, policy, memory, review, and evidence.
- Garden presents the product workspace, enterprise controls, inboxes, issues, connectors, and UI.
- Workstream supplies tasks, rubrics, reviewers, evaluations, contribution records, and evidence needs.

## What Not To Say

- Do not describe Harnessy as only a repo wrapper.
- Do not describe Harnessy as merely substrate.
- Do not collapse Harnessy into Jarvis; they are both harnesses, but they harness different things.
- Do not make Garden or Workstream responsible for reinventing capability packaging and verification when Harnessy can provide it.

## Short Form

Harnessy answers: what can this agent do here, and is the environment ready for it?
