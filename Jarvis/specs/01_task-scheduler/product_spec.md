# Product Specification: Jarvis

**AnyType Intelligent Task Scheduler**

---

## 1. Executive Summary

### Product Vision

Jarvis is an intelligent task scheduling automation for AnyType that analyzes workload patterns and proposes optimized task rescheduling — reducing the cognitive load of daily planning while keeping the user in full control.

### Value Proposition

For AnyType power users who manage many tasks across projects, Jarvis eliminates the mental overhead of deciding "when should I do this?" by intelligently suggesting schedule optimizations based on workload, priorities, deadlines, and learned preferences.

### Product Name

**Jarvis** — an intelligent assistant that handles the scheduling so you can focus on the work.

---

## 2. Problem Statement

### The Problem

Manual task scheduling is cognitively draining. Users spend significant mental energy:

- Reorganizing tasks when priorities shift
- Balancing workload across days to avoid burnout
- Remembering preferences (deep work in mornings, admin on Fridays)
- Ensuring deadlines aren't missed while managing competing priorities

This mental energy could be spent on actually completing tasks.

### Current State

AnyType users manually drag tasks between dates, mentally calculating workload distribution and priority trade-offs. There's no intelligent assistance for scheduling optimization.

### Impact

- **Cognitive overhead**: Decision fatigue from constant rescheduling
- **Uneven workload**: Some days overloaded, others underutilized
- **Missed context**: Hard to remember personal preferences and patterns
- **Reactive planning**: Always catching up rather than proactively optimized

---

## 3. Target Users

### Primary Persona: The Productivity-Focused Professional

**Demographics:**
- Knowledge worker managing 20-50+ active tasks
- Uses AnyType as primary task/project management tool
- Comfortable with command-line tools
- Values automation but wants control

**Behaviors:**
- Reviews and reorganizes tasks daily or multiple times per week
- Has developed personal productivity patterns (morning focus time, Friday admin, etc.)
- Frustrated by the overhead of manual scheduling
- Appreciates tools that "get" their preferences over time

**Pain Points:**
- "I spend 20 minutes every morning just reorganizing my task list"
- "I know Fridays should be for admin but I keep forgetting to schedule that way"
- "Some days I have 10 tasks, others I have 2 — it's never balanced"

**Goals:**
- Reduce time spent on scheduling logistics
- Have a more evenly distributed workload
- Never miss deadlines due to poor planning
- Feel confident that important tasks are appropriately prioritized

### Secondary Persona: The AnyType Power User

- Uses AnyType extensively with custom types, properties, and tags
- Already has `bar_movement` tag for immovable tasks
- Interested in AnyType automations and integrations
- Willing to configure context files for better results

---

## 4. User Stories & Requirements

### Epic 1: Core Scheduling Engine

**US-1.1: Workload Analysis**
> As a user, I want Jarvis to analyze my current task distribution so that I can see imbalances in my schedule.

Acceptance Criteria:
- Reads all tasks from AnyType via API
- Calculates task count per day for configurable date range
- Identifies overloaded and underutilized days
- Respects `bar_movement` tag (excludes from moveable tasks)

**US-1.2: Intelligent Suggestions**
> As a user, I want Jarvis to suggest schedule optimizations so that my workload is balanced.

Acceptance Criteria:
- Generates rescheduling proposals based on:
  1. Workload balancing (primary)
  2. Task priority
  3. Deadline constraints
  4. Dependencies between tasks
  5. Time-of-day preferences from context
- Never suggests moving `bar_movement` tasks
- Provides reasoning for each suggestion

**US-1.3: Context-Aware Reasoning**
> As a user, I want Jarvis to consider my preferences and patterns so that suggestions align with how I work.

Acceptance Criteria:
- Reads all files in `context/` folder
- Incorporates preferences, patterns, constraints, and priorities
- Weighs context rules appropriately in scheduling decisions

### Epic 2: CLI Interface

**US-2.1: Analyze Command**
> As a user, I want to run `jarvis analyze` to see my current schedule status.

Acceptance Criteria:
- Shows task distribution for next 14 days [ASSUMPTION]
- Highlights overloaded days (>6 tasks) [ASSUMPTION]
- Shows underutilized days (<3 tasks) [ASSUMPTION]
- Lists `bar_movement` tasks separately

**US-2.2: Suggest Command**
> As a user, I want to run `jarvis suggest` to get rescheduling proposals.

Acceptance Criteria:
- Displays proposed changes in clear format
- Shows: task name, current date, proposed date, reasoning
- Groups suggestions by confidence level [ASSUMPTION]
- Does not apply any changes automatically

**US-2.3: Apply Command**
> As a user, I want to review and selectively apply suggestions so that I stay in control.

Acceptance Criteria:
- Interactive approval: accept/reject each suggestion
- Batch operations: accept all, reject all
- Applies approved changes via AnyType API
- Confirms success/failure for each change

**US-2.4: On-Demand Execution**
> As a user, I want to run Jarvis manually whenever I need it.

Acceptance Criteria:
- CLI commands work anytime AnyType desktop is running
- No required schedule; user triggers when needed

### Epic 3: Scheduled Execution

**US-3.1: Daily Automation**
> As a user, I want Jarvis to run automatically each morning so that I start the day with suggestions ready.

Acceptance Criteria:
- Configurable schedule (default: 7:00 AM) [ASSUMPTION]
- Runs analysis and generates suggestions
- Stores suggestions for later review
- Optional notification that suggestions are ready

### Epic 4: Learning System

**US-4.1: Pattern Recording**
> As a user, I want Jarvis to learn from my approval/rejection patterns so that suggestions improve over time.

Acceptance Criteria:
- Records which suggestions are accepted vs. rejected
- Identifies patterns in rejections
- Updates `context/learnings.md` with insights

**US-4.2: Feedback Loop**
> As a user, I want Jarvis to get better at predicting my preferences over time.

Acceptance Criteria:
- Incorporates learnings into future suggestions
- Reduces rejection rate over time
- Adapts to changing preferences

---

## 5. Feature Prioritization

### MVP (Must Have)

| Feature | Rationale |
|---------|-----------|
| AnyType API integration | Foundation for all functionality |
| Task reading & filtering | Must identify moveable vs. immovable tasks |
| Workload analysis | Core value: see your schedule clearly |
| Basic balancing suggestions | Primary use case |
| CLI interface (analyze, suggest, apply) | User interaction model |
| Context file reading | Personalization from day one |
| `bar_movement` respect | Hard requirement from user |
| Approval workflow | No silent changes requirement |

### Post-MVP (Should Have)

| Feature | Rationale |
|---------|-----------|
| Scheduled daily runs | Convenience automation |
| Learning system | Improves over time |
| Confidence scoring | Better suggestion filtering |
| Dependency awareness | More sophisticated scheduling |

### Future (Nice to Have)

| Feature | Rationale |
|---------|-----------|
| Time-of-day optimization | Match tasks to energy patterns |
| Calendar integration | Avoid conflicts with meetings |
| Multi-space support | Users with multiple AnyType spaces |
| Web dashboard alternative | For users who prefer GUI |

---

## 6. User Experience

### Interaction Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     Daily Workflow                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Morning:                                                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   Jarvis    │───▶│   Review    │───▶│   Apply     │     │
│  │   runs      │    │  suggestions│    │  approved   │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│        │                   │                   │            │
│        ▼                   ▼                   ▼            │
│  "5 suggestions      "Move 'Write docs'   Changes made     │
│   ready"              to Thursday?"        to AnyType       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### CLI Interface Design

```bash
# See your schedule analysis
$ jarvis analyze

📊 Schedule Analysis (Next 14 Days)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Mon 27  ████████████  8 tasks  ⚠️  Overloaded
  Tue 28  ██████        4 tasks  ✓
  Wed 29  ████          2 tasks  ○  Light
  Thu 30  ██████████    6 tasks  ✓
  Fri 31  ████          2 tasks  ○  Light

🔒 Immovable (bar_movement): 3 tasks
📦 Moveable: 19 tasks

# Get rescheduling suggestions
$ jarvis suggest

💡 Suggested Changes
━━━━━━━━━━━━━━━━━━━━

1. "Write API docs"
   Mon 27 → Wed 29
   Reason: Balances workload, no deadline pressure

2. "Review PRs"
   Mon 27 → Fri 31
   Reason: Admin task fits Friday pattern (from preferences.md)

3. "Update dependencies"
   Mon 27 → Wed 29
   Reason: Low priority, moveable to lighter day

Accept all? [a] Accept each? [e] Reject all? [r]: e

# Interactive approval
[1/3] Move "Write API docs" Mon→Wed? [y/n]: y
✓ Applied

[2/3] Move "Review PRs" Mon→Fri? [y/n]: y
✓ Applied

[3/3] Move "Update dependencies" Mon→Wed? [y/n]: n
✗ Skipped

━━━━━━━━━━━━━━━━━━━━
Applied: 2 | Skipped: 1
```

### Error States

| Scenario | Handling |
|----------|----------|
| AnyType not running | Clear message: "AnyType desktop must be running. Please start it and try again." |
| API authentication fails | Guide user through re-authentication |
| No tasks found | "No moveable tasks found. All tasks may be tagged bar_movement or have no scheduled date." |
| Context files missing | Warn but continue: "No context/preferences.md found. Suggestions will use defaults." |

---

## 7. Technical Requirements

### Platform & Runtime

- **Language**: Python 3.10+ [ASSUMPTION]
- **Package Manager**: uv (for fast dependency management) [ASSUMPTION]
- **Local Execution**: Runs on user's machine alongside AnyType desktop

### Dependencies

| Dependency | Purpose |
|------------|---------|
| `anytype-client` | Official Python client for AnyType API |
| `anthropic` | Claude API for AI reasoning |
| `click` | CLI framework |
| `rich` | Terminal formatting and UI |
| `schedule` | Cron-like scheduling for daily runs [ASSUMPTION]
| `pydantic` | Data validation and settings |

### AnyType Integration

- **API Version**: Latest stable from developers.anytype.io
- **Authentication**: Local challenge-response flow
- **Requirement**: AnyType desktop app must be running
- **Rate Limiting**: Respect API rate limits (batch operations where possible)

### AI Integration

- **Model**: Claude (via Anthropic API) for scheduling reasoning
- **Context Window**: Pass user context + task data for intelligent suggestions
- **Fallback**: Basic algorithmic balancing if AI unavailable [ASSUMPTION]

### Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   AnyType   │────▶│   Jarvis    │────▶│   Claude    │
│   (tasks)   │     │  (engine)   │     │ (reasoning) │
└─────────────┘     └─────────────┘     └─────────────┘
       ▲                   │                   │
       │                   ▼                   │
       │            ┌─────────────┐            │
       │            │  context/   │◀───────────┘
       │            │  (prefs)    │
       │            └─────────────┘
       │                   │
       │                   ▼
       │            ┌─────────────┐
       └────────────│    CLI      │
    (apply changes) │  (user)     │
                    └─────────────┘
```

---

## 8. Context System Specification

### Directory Structure

```
context/
├── preferences.md      # Personal scheduling rules
├── patterns.md         # Work patterns and energy cycles
├── constraints.md      # Hard boundaries (times, capacity)
├── priorities.md       # Project/task priority hierarchy
└── learnings.md        # System-generated insights (append-only)
```

### File Format

All context files use Markdown with the following conventions:

- **Headers** (`##`) denote categories
- **Lists** (`-`) denote individual rules
- **Comments** (`<!-- -->`) are ignored but preserved
- Natural language is interpreted by AI reasoning

### Example: preferences.md

```markdown
## Time of Day Preferences

- Deep work (coding, writing) → Morning (9am-12pm)
- Meetings and calls → Afternoon (2pm-5pm)
- Admin tasks → End of day (4pm-5pm)

## Day of Week Preferences

- Monday: Planning and priority setting
- Friday: Admin, reviews, and wrap-up
- Weekends: No work tasks
```

### Learnings File

The `learnings.md` file is append-only and system-managed:

```markdown
## 2025-01-23

- User rejected moving "Client call" to afternoon (3 times)
  → Inference: Client calls preferred in morning
- User consistently accepts Friday admin suggestions
  → Confidence: High for Friday admin pattern
```

---

## 9. Non-Functional Requirements

### Performance

| Metric | Target |
|--------|--------|
| Analysis time | <5 seconds for 100 tasks |
| Suggestion generation | <10 seconds including AI reasoning |
| Apply single change | <2 seconds |

### Reliability

- Graceful degradation if AI unavailable
- No data loss on interrupted operations
- Atomic task updates (all-or-nothing per task)

### Security

- API keys stored securely (environment variables or system keychain)
- No task data sent to external services except Claude API (for reasoning)
- Local execution only; no cloud backend

### Usability

- Clear, actionable error messages
- Progress indicators for long operations
- Consistent CLI conventions (--help, --version, etc.)

---

## 10. Success Metrics

### Primary Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Suggestion acceptance rate** | >70% | Accepted ÷ Total suggestions |
| **Workload variance reduction** | >50% | Std dev of daily task count before/after |
| **Time to decision** | <2 min | From seeing suggestions to completing approval |

### Secondary Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| User engagement | Daily use | Days with at least one command run |
| Learning effectiveness | Improving acceptance rate over time | Week-over-week acceptance trend |
| Zero missed deadlines | 100% | Tasks with deadlines completed on time |

### Qualitative Success

- User reports feeling "less stressed about scheduling"
- User describes Jarvis as "understanding how I work"
- User trusts suggestions enough to batch-accept regularly

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| AnyType API changes | Medium | High | Pin API version, monitor changelog, abstract API layer |
| Poor AI suggestions | Medium | Medium | Fallback to algorithmic balancing, easy rejection flow |
| User doesn't fill context files | High | Medium | Sensible defaults, prompt to add context over time |
| AnyType desktop not running | Medium | Low | Clear error message with instructions |
| Claude API rate limits/costs | Low | Medium | Cache reasoning, batch requests, local fallback |
| Overwriting user's careful scheduling | Low | High | Never auto-apply, always require approval |

---

## 12. Release Strategy

### Phase 1: Alpha (Internal)

- Core CLI commands (analyze, suggest, apply)
- Basic workload balancing algorithm
- Context file reading
- Single user testing

### Phase 2: Beta (Limited)

- AI-powered reasoning integration
- Learning system basics
- Scheduled execution option
- Feedback collection from 5-10 users [ASSUMPTION]

### Phase 3: Public Release

- Refined suggestion quality based on beta feedback
- Documentation and onboarding guide
- Published to PyPI for easy installation
- Community feedback channel

---

## 13. Open Questions

### Resolved in This Spec

| Question | Resolution |
|----------|------------|
| Product name | Jarvis |
| Approval UI | CLI with interactive prompts |
| Tasks without due dates | Lower priority, schedule in underutilized days |
| Bootstrap learning | Start with context files, learn from approvals |

### Remaining Questions

| Question | Owner | Due |
|----------|-------|-----|
| Optimal look-ahead window (7 days? 14 days? 30 days?) | Tech Spec | Before implementation |
| Should suggestions include estimated task duration? | Tech Spec | Before implementation |
| Multi-space support architecture | Future | Post-MVP |

---

## 14. Dependencies & Integrations

### Required

| Dependency | Purpose | Status |
|------------|---------|--------|
| AnyType Desktop | API host, authentication | Available |
| AnyType API | Task CRUD operations | Available (developers.anytype.io) |
| Claude API | AI reasoning for suggestions | Available |

### Optional

| Integration | Purpose | Priority |
|-------------|---------|----------|
| System cron/launchd | Scheduled daily runs | Post-MVP |
| Desktop notifications | Alert when suggestions ready | Post-MVP |
| Calendar APIs | Avoid meeting conflicts | Future |

---

## 15. Appendix

### A. Glossary

| Term | Definition |
|------|------------|
| **bar_movement** | AnyType tag indicating a task should never be rescheduled |
| **Moveable task** | Task without `bar_movement` tag that can be rescheduled |
| **Workload** | Number of tasks scheduled for a given day |
| **Suggestion** | A proposed rescheduling action (task + new date + reasoning) |
| **Context** | User-provided preferences and patterns in `context/` folder |
| **Learning** | System-inferred preferences from user approval patterns |

### B. CLI Command Reference

```
jarvis analyze [--days N]     Analyze schedule for next N days (default: 14)
jarvis suggest [--days N]     Generate rescheduling suggestions
jarvis apply                  Apply previously generated suggestions
jarvis status                 Show Jarvis configuration and status
jarvis context                Show loaded context summary
```

### C. Context File Templates

See `context/` folder in project root for starter templates.

### D. Related Documents

- `brainstorm.md` — Original ideation document
- `technical_spec.md` — Detailed technical architecture (next phase)

---

*Product Specification v1.0*
*Created: 2025-01-23*
*Status: Ready for technical specification*
