# Product Specification: Weekly Planning Command

## 1. Executive Summary

### Product Name
**Jarvis Plan** — Proactive weekly planning with gap analysis

### Vision Statement
Transform Jarvis from a reactive task management tool into a proactive planning assistant that bridges the gap between what users intend to accomplish (context files) and what they're actually doing (scheduled tasks).

### Problem Statement
Jarvis users maintain rich context files documenting their goals, priorities, and focus areas. They also have tasks scheduled in their knowledge base. However, there's no tool that synthesizes these two sources to answer the fundamental question: **"Am I spending my time on what actually matters?"**

Current commands (`analyze`, `suggest`, `rebalance`) are reactive — they optimize existing task schedules. Users need proactive planning that:
1. Surfaces misalignment between stated priorities and actual work
2. Identifies goals with no supporting tasks
3. Generates actionable weekly plans grounded in their own context

### Target Users
- Existing Jarvis users who maintain context files (goals.md, priorities.md, focus.md)
- Knowledge workers who struggle with "what should I work on this week?"
- Anyone who wants AI-assisted planning personalized to their documented priorities

### Key Differentiator
**Gap Analysis** — Not just "here's your schedule" but "here's what's MISSING based on what you say matters." This transforms planning from calendar review into strategic alignment checking.

---

## 2. User Personas

### Primary Persona: The Intentional Planner

**Name:** Alex
**Role:** Researcher / Knowledge Worker
**Context:** Uses Jarvis daily, maintains detailed context files, has 15-30 tasks per week

**Goals:**
- Start each week knowing exactly what to focus on
- Ensure daily work aligns with longer-term goals
- Avoid the trap of being "busy but not productive"

**Pain Points:**
- Spends Sunday evenings manually reviewing goals and tasks
- Often realizes mid-week that important goals have no scheduled work
- Difficult to see the big picture when looking at individual tasks

**Quote:** "I write down my goals, but I don't always check if my actual tasks support them."

### Secondary Persona: The Deadline-Driven Professional

**Name:** Jordan
**Role:** Professional with multiple projects and hard deadlines
**Context:** Uses focus mode during crunch periods, needs to defer non-essential work

**Goals:**
- Protect focus time during critical periods
- Quickly identify what can be deferred
- Get confirmation that the week is set up for success

**Pain Points:**
- Hard to know if scheduled tasks conflict with current focus mode
- Manually scanning calendar for misaligned work is tedious
- Needs quick "am I on track?" validation

**Quote:** "When I'm in shipping mode, I need to know instantly if anything on my plate is a distraction."

---

## 3. User Stories & Requirements

### Epic: Weekly Planning Command

#### US-01: Generate Weekly Plan
**As a** Jarvis user
**I want to** run a single command that generates my weekly plan
**So that** I can quickly see what to focus on without manual analysis

**Acceptance Criteria:**
- [ ] `jarvis plan` generates a plan for the next 7 days by default
- [ ] Plan output appears in < 5 seconds for typical workloads
- [ ] Output uses rich terminal formatting (boxes, colors, icons)
- [ ] Command has alias `jarvis p` for quick access

#### US-02: View Focus Summary
**As a** user with context files
**I want to** see a summary of my current focus mode and goals
**So that** I'm reminded of what matters before reviewing tasks

**Acceptance Criteria:**
- [ ] Focus summary extracts data from focus.md, goals.md, priorities.md
- [ ] Shows current focus mode with duration (e.g., "Shipping until Jan 28")
- [ ] Displays primary goal and key decision rules
- [ ] Handles missing context files gracefully

#### US-03: View Current Task Reality
**As a** user with scheduled tasks
**I want to** see my tasks grouped by category with alignment scoring
**So that** I understand how my actual schedule relates to my focus

**Acceptance Criteria:**
- [ ] Queries knowledge base for tasks in the planning window
- [ ] Categorizes tasks by project, type, or tag
- [ ] Calculates and displays "alignment score" (% of tasks aligned with focus)
- [ ] Shows task count per day with overload warnings

#### US-04: Gap Analysis
**As a** user
**I want to** see gaps between my goals and scheduled tasks
**So that** I can identify blind spots in my planning

**Acceptance Criteria:**
- [ ] Identifies goals from goals.md that have no corresponding tasks
- [ ] Flags focus mode conflicts (e.g., "shipping mode but 40% exploratory tasks")
- [ ] Detects schedule issues (overloaded days, no buffer time)
- [ ] Presents gaps as actionable insights, not just data

#### US-05: Recommended Actions
**As a** user
**I want to** receive specific, actionable recommendations
**So that** I can act on the plan immediately

**Acceptance Criteria:**
- [ ] Each day shows existing tasks + suggested additions
- [ ] Provides ready-to-run `jarvis t` commands for suggested tasks
- [ ] Offers to run `jarvis suggest` when overload detected
- [ ] Recommendations respect user autonomy (suggest, don't auto-create)

#### US-06: Custom Planning Horizon
**As a** user
**I want to** specify how many days to plan
**So that** I can do shorter or longer planning sessions

**Acceptance Criteria:**
- [ ] `--days N` flag accepts integer 1-30
- [ ] Default is 7 days
- [ ] Output adapts to show appropriate level of detail

#### US-07: Interactive Planning Mode
**As a** user who wants deeper planning
**I want to** have a Q&A session with the AI
**So that** I can refine the plan based on my answers

**Acceptance Criteria:**
- [ ] `--interactive` flag enables Q&A mode after initial plan
- [ ] AI asks 2-5 clarifying questions based on detected gaps
- [ ] Generates updated recommendations based on answers
- [ ] Can exit interactive mode at any time

#### US-08: Save Plan to File
**As a** user
**I want to** save my plan to a file
**So that** I can reference it throughout the week

**Acceptance Criteria:**
- [ ] `--save` flag writes plan to `~/.jarvis/plans/YYYY-MM-DD.md`
- [ ] Creates plans directory if it doesn't exist
- [ ] File includes timestamp and all plan sections
- [ ] Confirms save location in output

---

## 4. Functional Requirements

### FR-01: Context File Processing

| Requirement | Description |
|-------------|-------------|
| FR-01.1 | Load context from global (`~/.jarvis/context/`) and local (`./.jarvis/context/`) paths |
| FR-01.2 | Merge context using existing `context_reader.py` logic (local overrides global) |
| FR-01.3 | Parse structured data from: goals.md, priorities.md, focus.md, patterns.md, constraints.md, projects.md, blockers.md, calendar.md, recurring.md |
| FR-01.4 | Handle missing files gracefully with sensible defaults (see FR-01.A) |
| FR-01.5 | Extract: current goals list, focus mode + duration, priority rules, time constraints |

#### FR-01.A: Graceful Degradation Behavior

| Context State | Behavior |
|---------------|----------|
| **Full context** (all files populated) | Full analysis with alignment scoring, gap detection, and personalized recommendations |
| **Partial context** (some files missing) | Skip missing sections; show "Context: Partial" indicator; still provide task analysis and basic recommendations |
| **Minimal context** (only 1-2 files) | Focus on task distribution analysis; recommend creating context files for better planning |
| **No context files** | Show task-only analysis (similar to `jarvis analyze`); prompt user to run `jarvis init` for full planning features |
| **Empty context files** | Treat as missing; show warning "goals.md exists but contains no extractable goals" |

The command should always provide value, even without context files — defaulting to task distribution and workload analysis.

### FR-02: Task Retrieval

| Requirement | Description |
|-------------|-------------|
| FR-02.1 | Query knowledge base via adapter layer (AnyType or Notion) |
| FR-02.2 | Retrieve tasks with due dates within planning horizon |
| FR-02.3 | Include task metadata: title, due date, priority, tags, project |
| FR-02.4 | Support both backends transparently |

### FR-03: Analysis Engine

| Requirement | Description |
|-------------|-------------|
| FR-03.1 | Categorize tasks by project/tag alignment with stated goals |
| FR-03.2 | Calculate alignment score: (aligned tasks / total tasks) × 100 |
| FR-03.3 | Detect schedule issues: overloaded days (>6 tasks), empty days, no buffer |
| FR-03.4 | Compare goals list against task titles/descriptions for coverage |
| FR-03.5 | Identify focus mode conflicts (task categories vs focus mode) |

#### FR-03.A: Alignment Detection Algorithm

A task is considered **aligned** with the current focus if ANY of the following are true:

1. **Tag Match:** Task has a tag that matches a keyword from focus.md or current goal
2. **Project Match:** Task's project name appears in goals.md or projects.md as active/priority
3. **Title Match:** Task title contains keywords from the primary goal (fuzzy match, case-insensitive)
4. **AI Classification:** When heuristics are inconclusive, Claude classifies the task against the stated focus (batched for efficiency)

**Alignment Score Interpretation:**
| Score | Interpretation | Guidance |
|-------|----------------|----------|
| >70% | Well-aligned | Schedule supports your focus |
| 40-70% | Mixed alignment | Review lower-priority tasks |
| <40% | Significant misalignment | Consider deferring or rescheduling |

#### FR-03.B: Goal Extraction Strategy

Context files are parsed using a **hybrid approach**:

1. **Structured Extraction:** Look for markdown headers (`## This Week`, `## Goals`) and extract bullet points
2. **Frontmatter Parsing:** If YAML frontmatter present, extract structured fields
3. **AI Fallback:** If no structure detected, send file content to Claude with extraction prompt
4. **Caching:** Parsed context cached for session to avoid repeated parsing

### FR-04: AI-Powered Plan Generation

| Requirement | Description |
|-------------|-------------|
| FR-04.1 | Send context + tasks + analysis to Claude API |
| FR-04.2 | Generate daily breakdown with theme and recommendations |
| FR-04.3 | Produce actionable suggestions with ready-to-run commands |
| FR-04.4 | Respect context-defined constraints and patterns |

### FR-05: Output Formatting

| Requirement | Description |
|-------------|-------------|
| FR-05.1 | Use Rich library for terminal formatting (consistent with existing commands) |
| FR-05.2 | Display 4-section output: Focus Summary, Current Reality, Gap Analysis, Recommended Plan |
| FR-05.3 | Use visual indicators: ✓ (aligned), ⚠️ (warning), + (suggestion), → (action) |
| FR-05.4 | Support `--json` output for programmatic use [FUTURE] |

### FR-06: Interactive Mode

| Requirement | Description |
|-------------|-------------|
| FR-06.1 | After initial plan, enter conversational Q&A if `--interactive` |
| FR-06.2 | Generate 2-5 contextual questions based on gaps detected |
| FR-06.3 | Update recommendations based on user responses |
| FR-06.4 | Allow exit at any prompt (type 'q', 'quit', 'exit', or Ctrl+C) |

---

## 5. Non-Functional Requirements

### NFR-01: Performance

| Requirement | Target |
|-------------|--------|
| Plan generation time | < 5 seconds (excluding API latency) |
| Context file loading | < 500ms |
| Task query time | < 2 seconds |
| Memory usage | < 100MB peak |

### NFR-02: Reliability

| Requirement | Target |
|-------------|--------|
| Handle missing context files | Graceful degradation with warnings |
| Handle knowledge baseconnection failures | Clear error message with retry suggestion |
| Handle API rate limits | Retry with backoff |

### NFR-03: Usability

| Requirement | Target |
|-------------|--------|
| Command discoverability | Appears in `jarvis --help` |
| Error messages | Actionable, not cryptic |
| Output readability | Scannable in < 30 seconds |

### NFR-04: Compatibility

| Requirement | Target |
|-------------|--------|
| Backend support | AnyType and Notion via adapter layer |
| Terminal support | Works in standard terminals (iTerm, Terminal.app, Windows Terminal) |
| Python version | 3.11+ (matches project requirement) |

---

## 6. User Experience Design

### Information Architecture

```
jarvis plan
│
├── Section 1: Focus Summary
│   ├── Current mode (emoji + label)
│   ├── Primary goal
│   ├── Decision rule
│   └── Duration remaining
│
├── Section 2: Current Reality
│   ├── Task count summary
│   ├── Category breakdown (with alignment indicators)
│   └── Alignment score
│
├── Section 3: Gap Analysis
│   ├── Goals without tasks
│   ├── Focus conflicts
│   └── Schedule issues
│
└── Section 4: Recommended Plan
    ├── Daily breakdown (7 days)
    │   ├── Existing tasks (✓)
    │   ├── Suggestions (+)
    │   └── Actions to take (→)
    └── Quick Actions (copy-paste commands)
```

### Visual Design

**Color Scheme (consistent with existing Jarvis commands):**
- Headers: Cyan boxes with white text
- Success/Aligned: Green ✓
- Warnings: Yellow ⚠️
- Suggestions: Blue +
- Actions: Magenta →

**Typography:**
- Section headers in bordered boxes
- Hierarchical indentation for nested items
- Monospace for commands and technical details

### Interaction Flow

```
┌─────────────────────────────────────────────────────────┐
│                    jarvis plan                          │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ Load context files    │
              │ Query knowledge basefor tasks    │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ Analyze alignment     │
              │ Detect gaps           │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ Generate plan via AI  │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ Display formatted     │
              │ plan output           │
              └───────────┬───────────┘
                          │
            ┌─────────────┴─────────────┐
            │                           │
            ▼                           ▼
   ┌─────────────────┐        ┌─────────────────┐
   │ --interactive?  │        │ --save?         │
   │ Enter Q&A mode  │        │ Write to file   │
   └─────────────────┘        └─────────────────┘
```

---

## 7. Feature Prioritization

### MVP (P0) — Must Have

| Feature | Rationale |
|---------|-----------|
| Basic `jarvis plan` command | Core functionality |
| Focus summary from context | Essential for alignment |
| Task retrieval and categorization | Foundation for analysis |
| Gap analysis (goals without tasks) | Key differentiator |
| Daily recommendations | Actionable output |
| Quick action commands | Immediate usability |

### P1 — Should Have

| Feature | Rationale |
|---------|-----------|
| `--days N` flag | Flexibility |
| Alignment score calculation | Quantified insight |
| Focus conflict detection | Deeper analysis |
| `jarvis p` alias | Convenience |

### P2 — Nice to Have

| Feature | Rationale |
|---------|-----------|
| `--interactive` mode | Deeper engagement |
| `--save` flag | Persistence |
| Schedule issue detection (overload, no buffer) | Polish |
| `--json` output | Programmatic use |

### Future Considerations

| Feature | Notes |
|---------|-------|
| Plan history tracking | Compare plans over time |
| `jarvis review` companion | End-of-week reflection |
| Plan templates | Predefined planning styles |
| Calendar integration | Factor in external events |

---

## 8. Technical Architecture

### System Context

```
┌─────────────────────────────────────────────────────────────────┐
│                         User's System                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │   Context   │    │  Knowledge  │    │   Anthropic API     │  │
│  │   Files     │    │    Base     │    │   (Claude)          │  │
│  │  (~/.jarvis │    │  (AnyType/  │    │                     │  │
│  │   /context) │    │   Notion)   │    │                     │  │
│  └──────┬──────┘    └──────┬──────┘    └──────────┬──────────┘  │
│         │                  │                      │             │
│         └────────┬─────────┴──────────────────────┘             │
│                  │                                              │
│                  ▼                                              │
│         ┌───────────────┐                                       │
│         │  jarvis plan  │                                       │
│         │   command     │                                       │
│         └───────────────┘                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Component Architecture

```
src/jarvis/plan/
├── __init__.py          # Package exports
├── cli.py               # CLI command definition (Click)
├── context.py           # Context aggregation and parsing
├── analyzer.py          # Task analysis and alignment scoring
├── gaps.py              # Gap detection logic
├── generator.py         # AI-powered plan generation
├── formatter.py         # Rich output formatting
└── interactive.py       # Interactive Q&A mode
```

### Data Flow

1. **Input Collection**
   - CLI parses arguments (`--days`, `--interactive`, `--save`)
   - Context aggregator loads and merges context files
   - Task analyzer queries knowledge basevia adapter

2. **Analysis**
   - Analyzer categorizes tasks by alignment
   - Gap detector compares goals vs tasks
   - Focus conflict checker validates schedule against mode

3. **Generation**
   - Plan generator builds AI prompt with context + analysis
   - Claude generates personalized recommendations
   - Response parsed into structured plan

4. **Output**
   - Formatter renders plan with Rich library
   - If `--interactive`, enter Q&A loop
   - If `--save`, write to file

### Integration Points

| Component | Integration |
|-----------|-------------|
| Context files | Via `context_reader.py` (existing) |
| Knowledge base | Via adapter layer (existing) |
| AI generation | Via `ai_client.py` (existing) |
| CLI framework | Via Click (existing pattern) |
| Output formatting | Via Rich (existing pattern) |

---

## 9. Data Requirements

### Input Data

**Context Files (Markdown with optional frontmatter):**

| File | Key Data Extracted |
|------|-------------------|
| goals.md | Goal list with timeframes (this week, this month) |
| priorities.md | Priority hierarchy, decision rules |
| focus.md | Current mode, duration, protection rules |
| patterns.md | Best times for work types, energy patterns |
| constraints.md | Hard scheduling constraints |
| projects.md | Active projects and status |
| blockers.md | Current blockers |
| calendar.md | Known commitments |
| recurring.md | Recurring responsibilities |

**Task Data (from KB):**

| Field | Usage |
|-------|-------|
| title | Display, goal matching |
| due_date | Day assignment |
| priority | Importance weighting |
| tags | Categorization |
| project | Alignment checking |
| done | Exclusion filter |

### Output Data

**Plan Structure:**

```python
@dataclass
class WeeklyPlan:
    focus_summary: FocusSummary
    current_reality: TaskReality
    gap_analysis: GapAnalysis
    daily_plans: list[DailyPlan]
    quick_actions: list[QuickAction]
    generated_at: datetime
    planning_horizon: int  # days

@dataclass
class FocusSummary:
    mode: str  # "Shipping", "Learning", "Exploring", "Recovery"
    mode_emoji: str
    primary_goal: str
    decision_rule: str
    until_date: date | None

@dataclass
class TaskReality:
    total_tasks: int
    tasks_by_day: dict[date, list[Task]]
    tasks_by_category: dict[str, list[Task]]  # category -> tasks
    alignment_score: float  # 0.0 - 1.0
    overloaded_days: list[date]  # days with >6 tasks
    empty_days: list[date]  # days with 0 tasks

@dataclass
class GapAnalysis:
    goals_without_tasks: list[str]
    focus_conflicts: list[str]
    schedule_issues: list[str]
    alignment_score: float  # 0.0 - 1.0

@dataclass
class DailyPlan:
    date: date
    day_name: str
    theme: str  # "Deep work day", "Light day", etc.
    existing_tasks: list[Task]
    suggestions: list[str]
    actions: list[str]
    warnings: list[str]
```

---

## 10. API & Integrations

### Internal APIs (Reused)

| API | Purpose |
|-----|---------|
| `context_reader.load_context()` | Load merged context |
| `adapter.get_tasks(space_id, start_date, end_date)` | Query tasks |
| `ai_client.generate()` | Claude API call |

### External APIs

| API | Purpose | Error Handling |
|-----|---------|----------------|
| Anthropic Claude | Plan generation | Retry with backoff, fallback to basic plan |

### New Internal APIs

```python
# plan/context.py
def aggregate_context() -> PlanContext:
    """Load and structure all context files for planning."""

# plan/analyzer.py
def analyze_alignment(tasks: list[Task], context: PlanContext) -> AlignmentResult:
    """Calculate alignment score and categorize tasks."""

# plan/gaps.py
def detect_gaps(tasks: list[Task], context: PlanContext) -> GapAnalysis:
    """Find gaps between goals and scheduled work."""

# plan/generator.py
def generate_plan(context: PlanContext, tasks: list[Task], gaps: GapAnalysis) -> WeeklyPlan:
    """Generate AI-powered weekly plan."""
```

---

## 11. Security & Privacy

### Data Handling

| Data Type | Handling |
|-----------|----------|
| Context files | Read-only, local filesystem |
| Task data | Retrieved via existing authenticated adapters |
| AI prompts | Sent to Anthropic API (user's own API key) |
| Plan output | Terminal display, optional local file save |

### Privacy Considerations

- No data leaves the user's machine except to Anthropic API
- User controls what goes in context files
- No telemetry or analytics
- Saved plans stored locally in `~/.jarvis/plans/`

### Security Measures

- Reuse existing adapter authentication (no new credentials)
- No sensitive data in logs
- File permissions match user's umask

---

## 12. Testing Strategy

### Unit Tests

| Component | Test Focus |
|-----------|-----------|
| context.py | Context file parsing, merging, missing file handling |
| analyzer.py | Alignment scoring, task categorization |
| gaps.py | Gap detection logic, edge cases |
| formatter.py | Output formatting, special characters |

### Integration Tests

| Scenario | Validation |
|----------|-----------|
| Full plan generation | End-to-end with mock knowledge baseand AI |
| AnyType backend | Real adapter integration |
| Notion backend | Real adapter integration |
| Interactive mode | Q&A flow with mock input |

### Manual Testing

| Scenario | Steps |
|----------|-------|
| Happy path | Run `jarvis plan` with populated context and tasks |
| Empty context | Run with no context files |
| No tasks | Run with context but empty knowledge base |
| Overloaded schedule | 50+ tasks in planning window |
| Long horizon | Run `jarvis plan --days 30` with 100+ tasks |
| API failure | Test with invalid API key or network disconnection |
| Empty goals.md | Create goals.md with no bullet points or structure |

---

## 13. Success Metrics

### Usage Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Command adoption | Qualitative: regular use in dogfooding | Manual observation during testing |
| Weekly usage | 1+ runs per user per week | User feedback |
| Interactive mode usage | ~20% of plan runs | User feedback |

**Note:** Formal analytics are out of scope for MVP. Metrics will be gathered through dogfooding and user feedback. Consider adding opt-in telemetry in future release.

### Quality Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Plan generation success rate | 99% | Error tracking |
| User-reported usefulness | >4/5 | Survey feedback |
| Gap detection accuracy | >80% true positives | User feedback |

### Performance Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to first output | < 5 seconds | Performance profiling |
| Memory usage | < 100MB | Resource monitoring |

---

## 14. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| AI generates unhelpful recommendations | Medium | High | Provide structured context, use system prompts tuned for planning |
| Context files too unstructured to parse | Medium | Medium | Use fuzzy matching, graceful fallbacks, provide guidance |
| Performance too slow | Low | High | Cache context, parallelize knowledge basequeries and AI calls |
| Users don't maintain context files | Medium | High | Provide useful output even with minimal context |
| Alignment scoring feels arbitrary | Medium | Medium | Make scoring transparent, allow user override |

---

## 15. Release Strategy

### Phase 1: MVP Release

**Scope:** Core `jarvis plan` command with focus summary, task reality, gap analysis, and recommendations

**Validation:**
- Internal dogfooding for 1 week
- Fix critical bugs
- Gather feedback on output format

### Phase 2: Enhancement Release

**Scope:** Add `--days`, `--interactive`, `--save` flags

**Validation:**
- Beta release to interested users
- Iterate on interactive mode questions
- Refine gap detection accuracy

### Phase 3: Polish Release

**Scope:** Performance optimization, edge case handling, documentation

**Validation:**
- Full documentation in README and `jarvis docs`
- Integration tests passing
- Ready for general use

---

## Appendix A: Example Output

```
╭──────────────────────────────────────────────╮
│ 🎯 Weekly Focus: ICML Deadline Crunch        │
╰──────────────────────────────────────────────╯

Mode: 🚀 Shipping (until Jan 28)
Primary Goal: Submit GND paper to ICML 2026
Decision Rule: If it doesn't contribute to submission, defer it.

╭──────────────────────────────────────────────╮
│ 📋 Scheduled Tasks (Jan 25 - Feb 1)          │
╰──────────────────────────────────────────────╯

24 tasks scheduled across 7 days

By Category:
  🔬 Research/GND:     8 tasks (33%) ✓ Aligned
  💼 Business:         9 tasks (38%) ⚠️ Potential conflict
  🔧 Maintenance:      4 tasks (17%)
  📝 Admin:            3 tasks (12%)

Alignment Score: 45%

╭──────────────────────────────────────────────╮
│ 🔍 Gap Analysis                              │
╰──────────────────────────────────────────────╯

⚠️  MISALIGNMENT DETECTED

Goals without tasks:
  • "Write paper abstract" — No task found
  • "Generate figures from B1 results" — No task found

Focus conflicts:
  • Focus mode is "Shipping" but 38% business tasks scheduled
  • Monday is overloaded (9 tasks)

╭──────────────────────────────────────────────╮
│ 📅 Recommended Weekly Plan                   │
╰──────────────────────────────────────────────╯

MONDAY (Jan 26) — Deep work day
  ⚠️ 9 tasks (overloaded)
  → Defer 5 business research tasks
  → Protect 4-hour block for paper writing

TUESDAY (Jan 27) — Execution
  ✓ 3 tasks scheduled
  + Suggested: Write abstract
  + Suggested: Generate B1 figures

... (continues)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Quick Actions:
  [1] jarvis t "Write paper abstract" -d tuesday -p high -t gnd
  [2] jarvis t "Generate B1 figures" -d tuesday -t gnd
  [3] jarvis suggest --days 7
```

---

## Appendix B: Context File Format Reference

### goals.md Example

```markdown
# Goals & Objectives

## This Week
- Submit GND paper to ICML 2026 by January 28
- Run experiment B2 (CIFAR-10)
- Generate all paper figures

## This Month
- ICML 2026 submission
- Post-submission: prepare rebuttal materials
```

### focus.md Example

```markdown
# Current Focus Mode

**Current:** 🚀 Shipping (ICML Deadline Crunch)

## Until
January 28, 2026

## What This Means
- Protect maximum deep work time daily (6+ hours)
- Minimize context switching
- No new project commitments
```

---

## Appendix C: Glossary

| Term | Definition |
|------|------------|
| **Context files** | Markdown files in `~/.jarvis/context/` (global) or `./.jarvis/context/` (local) that describe user goals, priorities, and preferences |
| **Knowledge base** | The backend data store (AnyType or Notion) where tasks are stored |
| **Adapter** | Abstraction layer that allows Jarvis to work with different knowledge bases |
| **Focus mode** | A declared operational state (Shipping, Learning, Exploring, Recovery) that influences planning recommendations |
| **Alignment score** | Percentage of scheduled tasks that support the user's stated focus and goals |
| **Gap analysis** | Comparison between stated goals and scheduled tasks to identify missing work |

---

## Appendix D: Open Questions Resolution

| Question | Resolution |
|----------|------------|
| Plan persistence | File-based (`~/.jarvis/plans/`) for simplicity |
| Plan history | Deferred to future release |
| Integration with suggest | Yes, offer naturally when overload detected |
| Weekly review command | Deferred to future release |
