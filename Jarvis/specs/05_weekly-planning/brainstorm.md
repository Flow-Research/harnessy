# Brainstorm: Weekly Planning Command

## Core Idea

**One sentence:** A `jarvis plan` command that synthesizes all context files and current tasks to generate an actionable weekly plan with gap analysis.

**Problem it solves:** Jarvis's current commands (`analyze`, `suggest`, `rebalance`) are reactive — they work with existing tasks. Users need proactive planning that bridges the gap between their goals/priorities (context files) and their actual scheduled work (Knowledge Base tasks).

## Target Audience

- Jarvis users who maintain context files (goals.md, priorities.md, focus.md, etc.)
- Users who want AI-assisted weekly planning that's personalized to their situation
- Anyone who struggles with "what should I actually work on this week?"

## Key Differentiator

**Gap Analysis** — the killer feature. Not just "here's what you have scheduled" but "here's what's MISSING based on what you say matters."

Examples:
- "Goal: ICML submission by Jan 28. You have 4 related tasks, but none for 'write abstract' — consider adding."
- "Focus mode: Shipping. But 40% of your scheduled tasks are exploratory research — consider deferring."
- "Priority #1 is GND paper, but Monday is overloaded with unrelated tasks."

## Command Design

### Primary Command

```bash
jarvis plan [--days N] [--interactive] [--save]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--days` | 7 | Planning horizon (days) |
| `--interactive` | false | Interactive planning session with follow-up questions |
| `--save` | false | Save plan to `~/.jarvis/plans/YYYY-MM-DD.md` |

### Alias

```bash
jarvis p  # Quick alias for jarvis plan
```

## Output Structure

### 1. Focus Summary (Strategic Layer)

Synthesized from context files:
- `focus.md` — Current mode (shipping, learning, exploring, recovery)
- `goals.md` — This week's goals, this month's goals
- `priorities.md` — Priority hierarchy, decision rules
- `constraints.md` — Hard constraints (no meetings before X, etc.)

Output:
```
╭──────────────────────────────────────────────╮
│ 🎯 Weekly Focus: ICML Deadline Crunch        │
╰──────────────────────────────────────────────╯

Mode: 🚀 Shipping (until Jan 28)
Primary Goal: Submit GND paper to ICML 2026
Decision Rule: If it doesn't contribute to submission, defer it.
```

### 2. Current Reality (Tactical Layer)

From Knowledge Base:
- Tasks scheduled for the planning period
- Grouped by day or category
- Alignment score with stated focus

Output:
```
╭──────────────────────────────────────────────╮
│ 📋 Scheduled Tasks (Jan 25 - Feb 1)          │
╰──────────────────────────────────────────────╯

24 tasks scheduled across 7 days

By Category:
  🔬 Research/GND:     8 tasks (33%) ← Aligned with focus
  💼 Business:         9 tasks (38%) ← Potential conflict
  🔧 Maintenance:      4 tasks (17%)
  📝 Admin:            3 tasks (12%)

Alignment Score: 45% (tasks aligned with stated focus)
```

### 3. Gap Analysis (The Insight Layer)

AI-powered analysis comparing context vs reality:

Output:
```
╭──────────────────────────────────────────────╮
│ 🔍 Gap Analysis                              │
╰──────────────────────────────────────────────╯

⚠️  MISALIGNMENT DETECTED

Goals without tasks:
  • "Write paper abstract" — No task found
  • "Generate figures from B1 results" — No task found
  • "Format for ICML LaTeX template" — No task found

Focus conflicts:
  • Focus mode is "Shipping" but 9 business research tasks scheduled
  • Monday is overloaded (9 tasks) — violates "protect deep work" pattern

Missing from your week:
  • No buffer time for unexpected issues (recommended: 20%)
  • No review/reflection time scheduled
```

### 4. Recommended Plan (Action Layer)

Concrete suggestions:

Output:
```
╭──────────────────────────────────────────────╮
│ 📅 Recommended Weekly Plan                   │
╰──────────────────────────────────────────────╯

SUNDAY (Jan 25) — Light day, prep for week
  ✓ 1 task scheduled
  + Suggested: Set up experiment B2 to run overnight

MONDAY (Jan 26) — Deep work day
  ⚠️ 9 tasks (overloaded)
  → Defer 5 business research tasks to next week
  → Protect 4-hour block for paper writing

TUESDAY (Jan 27) — Execution
  ✓ 3 tasks scheduled
  + Suggested: Write abstract (from goals)
  + Suggested: Generate B1 figures

... (continues for each day)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Quick Actions:
  [1] jarvis t "Write paper abstract" -d tuesday -p high -t gnd
  [2] jarvis t "Generate B1 figures" -d tuesday -t gnd
  [3] jarvis suggest --days 7  (to rebalance Monday)
```

## Interactive Mode (`--interactive`)

When `--interactive` flag is used:

1. Show the standard plan output
2. Then enter a Q&A session:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Planning Session
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

I noticed some gaps in your week. Let me ask a few questions:

1. The business research tasks (Tinubu initiative, electricity accounting, etc.)
   — are these urgent this week, or can they wait until after Jan 28?

> [user input]

2. You have no tasks for "write abstract" but that's critical for the paper.
   When would you like to tackle this?

> [user input]

Based on your answers, here's my updated recommendation...
```

## Context Files Used

| File | How It's Used |
|------|---------------|
| `goals.md` | Extract this week's goals, check if tasks exist for them |
| `priorities.md` | Understand priority hierarchy, apply decision rules |
| `focus.md` | Determine current mode, what to protect/defer |
| `patterns.md` | Know best times for deep work, meeting days, etc. |
| `constraints.md` | Hard rules that can't be violated |
| `projects.md` | Understand active projects and their status |
| `blockers.md` | Factor in any active blockers |
| `calendar.md` | Account for known events/commitments |
| `recurring.md` | Include recurring responsibilities |

## Technical Approach

### Data Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Context Files  │     │  Knowledge Base │     │   AI (Claude)   │
│  (Global+Local) │     │  (AnyType/      │     │                 │
│                 │     │   Notion)       │     │                 │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         ▼                       ▼                       │
    ┌─────────────────────────────────────┐              │
    │         Context + Tasks             │              │
    │         Merged Payload              │              │
    └─────────────────┬───────────────────┘              │
                      │                                  │
                      ▼                                  │
              ┌───────────────┐                          │
              │  Plan Prompt  │──────────────────────────┘
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────┐
              │  Weekly Plan  │
              │   (Output)    │
              └───────────────┘
```

### Implementation Components

1. **CLI Command** (`src/jarvis/plan/cli.py`)
   - Handle arguments: `--days`, `--interactive`, `--save`
   - Orchestrate the planning flow

2. **Context Aggregator** (`src/jarvis/plan/context.py`)
   - Load all context files (reuse `context_reader.py`)
   - Extract structured data: goals list, priority rules, focus mode, etc.

3. **Task Analyzer** (`src/jarvis/plan/analyzer.py`)
   - Query KB for tasks in planning window
   - Categorize tasks (by project, type, alignment)
   - Calculate alignment score

4. **Gap Detector** (`src/jarvis/plan/gaps.py`)
   - Compare goals vs scheduled tasks
   - Identify focus mode conflicts
   - Find missing task categories

5. **Plan Generator** (`src/jarvis/plan/generator.py`)
   - Send context + tasks + gaps to AI
   - Generate daily recommendations
   - Format output with rich formatting

6. **Interactive Session** (`src/jarvis/plan/interactive.py`)
   - If `--interactive`, enter Q&A mode
   - Refine plan based on user answers

### Reusable Components

- `context_reader.py` — Already loads/merges context files
- `ai_client.py` — Already handles Anthropic API calls
- `analyzer.py` — Has workload analysis logic (adapt for alignment scoring)
- Adapter layer — Already abstracts KB queries

## Success Criteria

1. **Reduces planning friction** — User can get a clear weekly plan in < 30 seconds
2. **Surfaces blind spots** — Gap analysis reveals misalignment user didn't notice
3. **Actionable output** — Every insight has a suggested action
4. **Respects user autonomy** — Recommends, doesn't auto-create tasks
5. **Integrates seamlessly** — Uses existing context system and KB adapters

## What This Should NOT Be

- ❌ Auto-pilot that creates tasks without user consent
- ❌ A replacement for user judgment — it's a decision support tool
- ❌ Overly complex with too many options
- ❌ Slow — should feel snappy like `jarvis analyze`

## Open Questions

1. **Plan persistence** — Should `--save` create a file, or store in KB as a note?
2. **Plan history** — Should we track previous plans to show progress over time?
3. **Integration with `suggest`** — Should `plan` automatically offer to run `suggest` if overload detected?
4. **Weekly review ritual** — Should there be a companion `jarvis review` command for end-of-week reflection?

## Inspiration & References

- **Time blocking** (Cal Newport) — Assigning specific work to specific times
- **Weekly Review** (GTD) — Regular review of goals, projects, next actions
- **OKR check-ins** — Comparing planned vs actual progress
- **Eisenhower Matrix** — Urgent vs Important prioritization

## Summary

`jarvis plan` bridges the gap between intention (context files) and action (scheduled tasks). Its unique value is the **gap analysis** that surfaces misalignment between what users say matters and what they're actually doing. The command is fast by default, with an optional interactive mode for deeper planning sessions.
