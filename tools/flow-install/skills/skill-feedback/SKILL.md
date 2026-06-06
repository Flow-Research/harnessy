---
name: skill-feedback
description: Capture ad-hoc feedback about any skill for the decision trace system.
disable-model-invocation: true
allowed-tools: Read, Write, Bash
argument-hint: "<skill-name> \"<feedback text>\""
---

# Skill Feedback — Ad-Hoc Trace Capture

## Purpose

Record feedback about any skill's behavior as a decision trace. This feeds the short loop (skill reads its own traces on future runs) and the long loop (`/skill-improve` analyzes accumulated traces to propose skill mutations).

Use this when you have feedback that doesn't correspond to a specific gate interaction — general impressions, workflow complaints, meta-observations, or suggestions.

Template paths are resolved from `${AGENTS_SKILLS_ROOT}/skill-feedback/`.

Follow the Harnessy policy in `.jarvis/context/docs/standards/skill-feedback-protocol.md` when deciding whether feedback must be captured and which skill should receive the trace. The short rule is: capture reusable skill lessons, not empty retrospectives.

## Inputs

- `skill-name` — the skill to attach feedback to
- `feedback text` — free-text description of the issue, suggestion, or observation

## Steps

1. **Parse arguments**: extract skill name and feedback text from `$ARGUMENTS`.
2. **Validate skill exists**: check that `${AGENTS_SKILLS_ROOT}/<skill-name>/` or `~/.agents/skills/<skill-name>/` exists. If not, report the error and list similar skill names.
   - Attach the trace to the skill that should change. Do not attach routine feedback to `skill-feedback` unless the recorder itself failed.
3. **Capture the trace**:
   ```bash
   python3 "${AGENTS_SKILLS_ROOT}/_shared/trace_capture.py" capture \
       --skill "<skill-name>" \
       --gate "ad_hoc" \
       --gate-type "retrospective" \
       --outcome "approved" \
       --feedback "<feedback text>"
   ```
4. **Confirm**: report that the feedback was recorded and the trace file location.
5. **Suggest**: if the skill has 5+ traces with refinement loops, suggest running `/skill-improve <skill-name>`.

## Output

- Confirmation message with trace ID
- Trace file path
- Optional improvement suggestion
