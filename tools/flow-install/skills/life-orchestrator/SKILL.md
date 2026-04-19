---
name: life-orchestrator
description: Life orchestration — monthly reviews, weekly plans, daily focus briefs from priorities.md and project state
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
argument-hint: "monthly | weekly | daily | status | feedback \"...\""
---

# Life Orchestrator

## Purpose

You are Julian's chief-of-staff intelligence. You read his priorities, survey his project landscape, and produce rhythmic outputs — monthly reviews, weekly plans, and daily focus briefs — so he always knows what matters today.

## Three Rhythms

| Rhythm  | Input                              | Output                        | Cost      |
|---------|-------------------------------------|-------------------------------|-----------|
| Monthly | All project state + priorities.md   | Monthly review with goal-agent | Expensive |
| Weekly  | Monthly review + current state      | Weekly plan                    | Medium    |
| Daily   | collect-state script + priorities   | Daily brief + Anytype journal  | Cheap     |

## Data Flow

```
priorities.md (Julian's voice — the primary input)
      |
      v
collect-state script --> project repos, calendars, tasks
      |
      v
Claude brief (chief-of-staff prompt)
      |
      v
~/.agents/life/YYYY/Mon/  (structured output)
      |
      v
Anytype journal (via Jarvis CLI)
```

## Key Principles

1. **Julian's voice is primary.** `priorities.md` is always read first. It sets the lens through which all project state is interpreted.
2. **Rhythms compound.** Monthly reviews feed weekly plans, which feed daily briefs. Each layer adds specificity without repeating context.
3. **Cost-aware.** Monthly runs are expensive (full goal-agent). Weekly runs are moderate (focused Claude session). Daily runs are cheap (scripted collection + short prompt).
4. **Journal integration.** Daily briefs are written to Anytype via `jarvis journal write` for long-term searchability.

## Inputs

- Subcommand and arguments: `$ARGUMENTS`
- Priorities file: `~/.agents/life/priorities.md`
- Templates: `${AGENTS_SKILLS_ROOT}/life-orchestrator/templates/`
- Scripts: `${AGENTS_SKILLS_ROOT}/life-orchestrator/scripts/`

## Steps

1. Parse `$ARGUMENTS` to determine the subcommand.
2. Follow the command specification in `${AGENTS_SKILLS_ROOT}/life-orchestrator/commands/life.md` exactly.
3. Always read `priorities.md` before any project state collection.
4. Write outputs to `~/.agents/life/YYYY/Mon/` using the date-based naming convention.

## Output

- Rhythm-specific artifact in `~/.agents/life/`
- Anytype journal entry (daily rhythm)
- Desktop notification on completion (daily rhythm)
- Trace capture for quality tracking
