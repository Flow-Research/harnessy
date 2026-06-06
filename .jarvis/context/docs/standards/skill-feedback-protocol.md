# Skill Feedback Protocol

Harnessy skills improve through decision traces. Agents must capture useful
skill feedback as structured traces instead of leaving it only in chat,
temporary notes, or memory.

## Purpose

The protocol creates a reliable loop:

1. A skill is used in real work.
2. The run exposes a lesson about the skill.
3. The lesson is captured as a decision trace.
4. Future runs query traces for the short loop.
5. `skill-improve` can promote recurring patterns into durable skill changes.

This is the feedback layer that supports the autoresearch ratchet. It is not a
general conversation log.

## Mandatory Capture Triggers

Capture feedback whenever any of these occur during skill-backed work:

- The user explicitly says to treat something as feedback, learning, or a skill
  improvement.
- A skill misses a required step, uses a brittle assumption, or needs a manual
  workaround.
- A deterministic command, wrapper, profile, or artifact contract is missing or
  weaker than the work requires.
- A deployment, QA, browser, CI, provider, dependency, packaging, security, or
  mobile/runtime issue reveals a reusable gap in the skill.
- A skill's instructions are correct but incomplete for an observed real-world
  variant.
- The same correction, clarification, or workaround appears more than once.
- The user rejects, corrects, or materially redirects a skill-produced output.
- A run produces evidence that should change future defaults, checks, or
  escalation rules.

Do not capture feedback for a normal successful skill invocation with no
skill-level lesson. Empty traces reduce signal quality.

## Routing

Attach feedback to the skill that should change.

- If one skill caused the issue, trace that skill.
- If the issue is coordination between two skills, trace the primary orchestrator
  and mention the related skill in the feedback text.
- If the issue is a generic Harnessy install or policy gap, trace the closest
  Harnessy meta-skill or capability owner.
- Do not attach routine feedback to `skill-feedback`; that skill is only the
  recorder unless the recorder itself is what failed.

## Capture Method

For ad-hoc feedback, use the installed `skill-feedback` skill or call the shared
trace recorder directly:

```bash
python3 "${AGENTS_SKILLS_ROOT}/_shared/trace_capture.py" capture \
  --skill "<skill-name>" \
  --gate "ad_hoc" \
  --gate-type "retrospective" \
  --outcome "approved" \
  --feedback "<specific reusable lesson>"
```

When a skill command already defines a gate-specific trace capture flow, use that
flow instead. Include refinement loops, categories, issues found, phase, project,
or issue metadata when available.

## Agent Workflow

Before finalizing a skill-backed task, perform a feedback capture check:

1. List the skill or skills used.
2. Decide whether any mandatory trigger fired.
3. Capture one trace per affected skill when a trigger fired.
4. If trace capture fails, report the failure and the reason in the final
   response.
5. If no trigger fired, do not create a trace.

When the user provides feedback after the final response, capture it on the next
turn before doing unrelated work.

## Quality Bar

Good feedback is specific, reusable, and operational:

- State what happened.
- State why the current skill behavior was insufficient.
- State what future runs should check, avoid, or automate.

Avoid vague praise, broad complaints, or chat transcripts. The trace should be
actionable enough for `skill-improve` to propose an edit.

## Relationship To Autoresearch

Skill feedback traces are the input signal for the short loop and long loop:

- Short loop: skills query recent traces before gates and adapt behavior.
- Long loop: `skill-improve` analyzes recurring traces and proposes durable
  changes.
- Ratchet loop: autoresearch evaluates whether changed skill behavior improves
  the fixed metric without regressions.

Trace capture is therefore a required Harnessy operating protocol, while skill
mutation remains governed by the autoresearch ratchet and human control surface.
