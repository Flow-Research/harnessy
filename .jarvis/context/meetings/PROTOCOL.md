# Meeting Notes Protocol

## Directory Structure

```
meetings/
├── PROTOCOL.md          # This file
└── YYYY/
    └── Mon/             # 3-letter month: Jan, Feb, Mar, ...
        └── DD-<title>.md
```

**Path pattern:** `meetings/YYYY/Mon/DD-<meeting-title>.md`

**Examples:**
- `meetings/2026/Mar/14-flow-poc-kickoff.md`
- `meetings/2026/Mar/28-sprint-1-review.md`
- `meetings/2026/Apr/11-bittensor-subnet-deep-dive.md`

**Naming rules:**
- `DD` = zero-padded day (01, 14, 28)
- `<title>` = kebab-case, short, descriptive (max 5 words)
- No spaces or special characters in filename

## Required Template

Every meeting note must follow this structure. Sections marked `(required)` must always be present. Sections marked `(if applicable)` can be omitted when empty.

```markdown
# <Meeting Title>

**Date:** YYYY-MM-DD (<day of week>)
**Duration:** <X> minutes
**Recording:** <URL or "None">
**Facilitator:** <name>

## Attendees

| Name | Role | Present |
|------|------|---------|
| ... | ... | Full / Partial / Absent |

## Summary                                    (required)
2-3 sentences. What was this meeting about and what was the outcome.

## Key Decisions                               (required)
Numbered list. Each item = one decision that was made.
If no decisions were made, write "No decisions made."

## Discussion Notes                            (if applicable)
Structured subsections covering the main topics discussed.
Use ### headings for each topic.

## Action Items                                (required)

| Action | Owner | Deadline |
|--------|-------|----------|
| ... | ... | ... |

## Open Questions                              (if applicable)
Bulleted list of unresolved questions parked for later.
```

## Writing Guidelines

- **Synthesize, don't transcribe.** Meeting notes are structured summaries, not verbatim logs. Extract decisions, actions, and context — discard filler, crosstalk, and network issues.
- **Attribute decisions and actions.** Always name who decided, who owns, who raised the question.
- **Preserve exact numbers and specifics.** Token values, contract addresses, deadlines, metrics — capture precisely.
- **Link to artifacts.** If a doc, design, or recording was referenced, include the URL.
- **Keep it scannable.** Tables for attendees and actions. Numbered lists for decisions. Bullets for open questions.

## Automation Notes

This protocol is designed for future automation via Jarvis CLI:

1. **Input:** Raw transcript from Fathom (or similar) is passed to an LLM.
2. **Processing:** LLM extracts structured content following the template above.
3. **Output:** Markdown file written to the correct `meetings/YYYY/Mon/` path.
4. **Post-processing:** Optionally update `goals.md`, `decisions.md`, or `focus.md` if meeting produced changes to those.

**Planned Jarvis command:**
```bash
jarvis meeting process <transcript-file-or-url> --title "sprint-1-review"
```

**LLM extraction prompt should:**
- Follow the template structure exactly
- Deduplicate repeated points (common in transcripts with network issues)
- Distinguish between decisions (agreed by group) vs suggestions (raised but not decided)
- Flag action items with clear owners — if owner is ambiguous, note "TBD"
- Omit attendee chatter about audio/video issues, greetings, and goodbyes
