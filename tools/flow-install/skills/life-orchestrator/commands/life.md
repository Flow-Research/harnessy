---
description: Life orchestration — monthly reviews, weekly plans, daily focus
argument-hint: "monthly | weekly | daily | status | feedback \"...\""
---

# Command Contract: life

## Purpose

Produce rhythmic life orchestration outputs — monthly reviews, weekly plans, and daily briefs — grounded in the user's priorities and current project state.

## Ownership

- Owner: julian
- Source of truth: `${AGENTS_SKILLS_ROOT}/life-orchestrator/`

## User Input

$ARGUMENTS

## Context

- Current date: !`date +%Y-%m-%d`
- Current day of week: !`date +%A`
- Week number: !`date +%V`
- Month: !`date +%B`
- Year: !`date +%Y`

## Shared Conventions

### File Paths

```
LIFE_DIR=~/.agents/life
YEAR=$(date +%Y)
MONTH=$(date +%b)   # e.g. Apr
DAY=$(date +%d)
WEEK=$(date +%V)
OUTPUT_DIR=$LIFE_DIR/$YEAR/$MONTH
```

### Priority Reading (ALWAYS First)

Before collecting any project state, read the user's priorities:

```bash
cat ~/.agents/life/priorities.md
```

This file is the user's voice. It defines what matters right now, what to deprioritize, and what to ignore. All subsequent state collection and synthesis must be filtered through this lens.

---

## Command Router

### `monthly`

Run a comprehensive monthly review using goal-agent.

**Cost:** Expensive (full goal-agent run)

**Steps:**

1. Read `priorities.md`.
2. Collect full project state using the collect-state script:
   ```bash
   python3 "${AGENTS_SKILLS_ROOT}/life-orchestrator/scripts/collect-state"
   ```
3. Read the monthly review template:
   ```bash
   cat "${AGENTS_SKILLS_ROOT}/life-orchestrator/templates/monthly-review.md"
   ```
4. Read all daily notes from the month (the user's own thoughts and action items):
   ```bash
   NOTES_DIR=".jarvis/context/private/${FLOW_USER:-${USER}}/notes/$YEAR/$MONTH"
   for f in $(ls "$NOTES_DIR"/*.md 2>/dev/null); do echo "=== $(basename $f) ==="; cat "$f"; done
   ```
5. Compose a goal file for goal-agent that asks it to produce a monthly review. The goal should:
   - Reference `priorities.md` as the authority on what matters
   - Include the collected state as context
   - Include the daily notes as the user's own voice on what mattered throughout the month
   - Follow the monthly review template structure
   - Write output to `$OUTPUT_DIR/monthly-review.md`
5. Run goal-agent:
   ```bash
   /goal-agent run "$GOAL_FILE"
   ```
6. After goal-agent completes, verify the review was written:
   ```bash
   test -f "$OUTPUT_DIR/monthly-review.md" && echo "Monthly review written" || echo "FAILED"
   ```
7. Capture trace:
   ```bash
   python3 "${AGENTS_SKILLS_ROOT}/_shared/trace_capture.py" capture \
       --skill "life-orchestrator" --gate "monthly_review" --gate-type "quality" \
       --outcome "approved" --feedback "Monthly review for $(date +%B\ %Y)"
   ```

**Output:** `~/.agents/life/YYYY/Mon/monthly-review.md`

---

### `weekly`

Produce a weekly plan based on the monthly review and current state.

**Cost:** Medium (focused Claude session)

**Steps:**

1. Read `priorities.md`.
2. Read the most recent monthly review:
   ```bash
   cat "$OUTPUT_DIR/monthly-review.md" 2>/dev/null || echo "No monthly review found — running with priorities only"
   ```
3. Collect current project state:
   ```bash
   python3 "${AGENTS_SKILLS_ROOT}/life-orchestrator/scripts/collect-state"
   ```
4. Read the weekly plan template:
   ```bash
   cat "${AGENTS_SKILLS_ROOT}/life-orchestrator/templates/weekly-plan.md"
   ```
5. Read any feedback from the past week:
   ```bash
   find ~/.agents/life/feedback/ -name "*.md" -newer "$OUTPUT_DIR/week-*-plan.md" 2>/dev/null | head -5 | xargs cat 2>/dev/null
   ```
6. Read daily notes from this week (the user's own thoughts, action items, reminders):
   ```bash
   NOTES_DIR=".jarvis/context/private/${FLOW_USER:-${USER}}/notes/$YEAR/$MONTH"
   for f in $(ls "$NOTES_DIR"/*.md 2>/dev/null | tail -7); do echo "=== $(basename $f) ==="; cat "$f"; done
   ```
   These notes are the user's voice — they reveal what's actually on their mind vs. what the system tracks.
7. Synthesize a weekly plan that:
   - Aligns with monthly review priorities (or priorities.md if no review exists)
   - Accounts for current project state and momentum
   - Incorporates any feedback captured since last plan
   - Reflects the user's daily notes — what they've been thinking about, action items they captured
   - Assigns focus areas to specific days where appropriate
   - Identifies the week's "must-win" deliverable
8. Write the plan:
   - File: `$OUTPUT_DIR/week-$WEEK-plan.md`
   - Follow the weekly plan template structure
9. Create Jarvis tasks for the week's key deliverables:
   ```bash
   jarvis task create "<task title>" --priority <high|medium|low>
   ```
10. Capture trace:
    ```bash
    python3 "${AGENTS_SKILLS_ROOT}/_shared/trace_capture.py" capture \
        --skill "life-orchestrator" --gate "weekly_plan" --gate-type "quality" \
        --outcome "approved" --feedback "Week $WEEK plan"
    ```

**Output:** `~/.agents/life/YYYY/Mon/week-NN-plan.md`

---

### `daily`

Two-step daily brief: collect state, then synthesize focus.

**Cost:** Cheap (scripted collection + short Claude prompt)

**Steps:**

1. Read `priorities.md`.
2. Run the collect-state script:
   ```bash
   python3 "${AGENTS_SKILLS_ROOT}/life-orchestrator/scripts/collect-state"
   ```
   This script outputs a JSON summary of: git activity across repos, open PRs, calendar events, recent Jarvis tasks, and any changes since yesterday.
3. Check if there are meaningful changes. If the script reports `"changes_detected": false`, write a minimal brief ("No significant changes — carry forward yesterday's focus") and skip to step 7.
4. Read the current weekly plan:
   ```bash
   cat "$OUTPUT_DIR/week-$WEEK-plan.md" 2>/dev/null || echo "No weekly plan — synthesizing from priorities"
   ```
5. Read the daily brief template and chief-of-staff prompt:
   ```bash
   cat "${AGENTS_SKILLS_ROOT}/life-orchestrator/templates/daily-brief.md"
   cat "${AGENTS_SKILLS_ROOT}/life-orchestrator/templates/chief-of-staff-prompt.md"
   ```
6. Run the daily-brief script with the chief-of-staff prompt:
   ```bash
   python3 "${AGENTS_SKILLS_ROOT}/life-orchestrator/scripts/daily-brief" \
       --state-file "/tmp/life-collect-state-$(date +%Y%m%d).json" \
       --priorities ~/.agents/life/priorities.md \
       --weekly-plan "$OUTPUT_DIR/week-$WEEK-plan.md" \
       --template "${AGENTS_SKILLS_ROOT}/life-orchestrator/templates/daily-brief.md" \
       --prompt "${AGENTS_SKILLS_ROOT}/life-orchestrator/templates/chief-of-staff-prompt.md" \
       --output "$OUTPUT_DIR/$DAY-daily-brief.md"
   ```
   This script internally calls `claude -p` with the chief-of-staff prompt, feeding it the collected state, priorities, and weekly plan.
7. Write the brief to `$OUTPUT_DIR/$DAY-daily-brief.md`.
8. Journal to Anytype:
   ```bash
   jarvis journal write --file "$OUTPUT_DIR/$DAY-daily-brief.md"
   ```
9. Send desktop notification:
   ```bash
   osascript -e 'display notification "Daily brief ready" with title "Life Orchestrator"'
   ```
10. Capture trace:
    ```bash
    python3 "${AGENTS_SKILLS_ROOT}/_shared/trace_capture.py" capture \
        --skill "life-orchestrator" --gate "daily_brief" --gate-type "quality" \
        --outcome "approved" --feedback "Daily brief for $(date +%Y-%m-%d)"
    ```

**Output:** `~/.agents/life/YYYY/Mon/dd-daily-brief.md` + Anytype journal entry + desktop notification

---

### `status`

Quick view of current life orchestration state.

**Steps:**

1. Read the most recent monthly review (first 20 lines for current priority):
   ```bash
   head -20 "$OUTPUT_DIR/monthly-review.md" 2>/dev/null || echo "No monthly review"
   ```
2. Read the current weekly plan:
   ```bash
   cat "$OUTPUT_DIR/week-$WEEK-plan.md" 2>/dev/null || echo "No weekly plan"
   ```
3. Read today's brief:
   ```bash
   cat "$OUTPUT_DIR/$DAY-daily-brief.md" 2>/dev/null || echo "No daily brief yet"
   ```
4. Check for running agents:
   ```bash
   ps aux | grep -E "claude.*life-orchestrator|goal-agent" | grep -v grep
   ```
5. Display a summary:
   ```
   ## Life Orchestrator Status

   **Monthly priority:** <extracted from monthly review>
   **This week's plan:** <key items from weekly plan>
   **Today's focus:** <extracted from daily brief>
   **Running agents:** <any active processes>
   **Last updated:** <most recent file timestamp>
   ```

**Output:** Status summary displayed to user

---

### `feedback "..."`

Capture a feedback annotation for future planning cycles.

**Steps:**

1. Parse the feedback text from `$ARGUMENTS` (everything after `feedback`).
2. Create the feedback directory if needed:
   ```bash
   mkdir -p ~/.agents/life/feedback
   ```
3. Write the feedback file:
   - File: `~/.agents/life/feedback/$(date +%Y-%m-%d)-feedback.md`
   - Format:
     ```markdown
     ---
     date: YYYY-MM-DD
     time: HH:MM
     type: feedback
     ---

     <feedback text>
     ```
   - If a feedback file for today already exists, append to it rather than overwriting.
4. Capture trace:
   ```bash
   python3 "${AGENTS_SKILLS_ROOT}/_shared/trace_capture.py" capture \
       --skill "life-orchestrator" --gate "feedback_capture" --gate-type "human" \
       --outcome "approved" --feedback "<feedback text>"
   ```
5. Confirm to user: "Feedback captured. Will be incorporated in next weekly plan."

**Output:** `~/.agents/life/feedback/YYYY-MM-DD-feedback.md` + trace

---

## Safety Rules

1. **Privacy:** Life orchestration data is personal. Never commit `~/.agents/life/` contents to any repository.
2. **Cost awareness:** Monthly is expensive (goal-agent). Don't run monthly more than once per month unless explicitly asked. Weekly should run once per week. Daily is cheap and can run multiple times.
3. **Priorities are sovereign:** Never override or reinterpret `priorities.md`. If project state conflicts with stated priorities, flag the conflict but follow the priorities.
4. **Graceful degradation:** If a monthly review is missing, weekly still works (uses priorities directly). If weekly is missing, daily still works (uses priorities + state). Never block on a missing upstream artifact.
5. **Jarvis integration:** Always use the Jarvis CLI for task creation and journaling. Do not write directly to Anytype.
6. **Idempotent outputs:** Running the same rhythm twice on the same day should overwrite the previous output, not create duplicates.
