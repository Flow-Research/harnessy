# Product Specification: Jarvis Task Creation

**CLI-First Task Capture for AnyType**

---

## 1. Executive Summary

### Product Vision

Extend Jarvis with a `jarvis task` command that enables users to create tasks directly in AnyType from the command line, supporting both rapid capture and detailed task setup workflows.

### Value Proposition

For Jarvis users who want to capture tasks without leaving their terminal, `jarvis task` eliminates the friction of context-switching to the AnyType desktop app. Quick thoughts become tasks in seconds, complete with due dates, priorities, and tags.

### Feature Name

**Task Creation Command** — The missing piece that completes the Jarvis task management workflow: create → analyze → suggest → apply.

---

## 2. Problem Statement

### The Problem

Currently, Jarvis can analyze, reschedule, and optimize existing tasks in AnyType, but users must open the AnyType desktop application to create new tasks. This breaks the CLI-first workflow that Jarvis users expect.

### Current State

When a user thinks of a new task while working in the terminal:
1. They must open AnyType desktop app
2. Navigate to the correct space
3. Create a new task object
4. Fill in title, due date, priority, tags
5. Return to their terminal

This 5-step process creates friction that leads to:
- Delayed task capture (and potential forgetting)
- Broken flow state during development work
- Inconsistent use of Jarvis scheduling features (tasks created in AnyType may not match scheduler expectations)

### Impact

- **Lost thoughts**: Quick ideas not captured immediately are often forgotten
- **Context switching cost**: Opening the GUI breaks terminal workflow
- **Adoption barrier**: Users who prefer CLI avoid creating tasks, limiting Jarvis's value
- **Incomplete workflow**: Jarvis can manage tasks but not create them, requiring two tools

---

## 3. Target Users

### Primary Persona: The Terminal-Centric Developer

**Demographics:**
- Software developer or technical professional
- Already using Jarvis for task scheduling
- Spends majority of work time in terminal/IDE
- Values keyboard-driven workflows

**Behaviors:**
- Uses `jarvis j` (journal) regularly for quick thoughts
- Runs `jarvis analyze` and `jarvis suggest` for schedule optimization
- Prefers CLI over GUI when possible
- Creates tasks multiple times per day

**Pain Points:**
- "I have to open AnyType just to add a quick task"
- "By the time I switch apps, I sometimes forget what I was going to add"
- "I wish I could create tasks as fast as I create journal entries"

**Goals:**
- Capture tasks in under 5 seconds
- Never leave the terminal for task management
- Have tasks immediately available for Jarvis scheduling

### Secondary Persona: The Automation Enthusiast

- Writes shell scripts and automation workflows
- Wants to create tasks programmatically
- Values scriptable, pipeable CLI commands
- May integrate Jarvis into CI/CD or cron jobs

---

## 4. User Stories & Requirements

### Epic: Task Creation Command

**US-4.1: Quick Task Capture**
> As a user, I want to create a task with a single command so that I can capture thoughts immediately.

Acceptance Criteria:
- `jarvis t "Task title"` creates a task in AnyType
- Task appears in the currently selected space
- Confirmation message shows task was created
- Command completes in under 2 seconds

**US-4.2: Due Date Assignment**
> As a user, I want to specify a due date using natural language so that I don't have to think about date formats.

Acceptance Criteria:
- `--due tomorrow` sets due date to next day
- `--due friday` sets due date to upcoming Friday
- `--due "next week"` sets due date 7 days out
- `--due 2025-02-15` sets exact date
- Invalid dates show helpful error message

**US-4.3: Priority Assignment**
> As a user, I want to set task priority so that important tasks are flagged appropriately.

Acceptance Criteria:
- `--priority high` sets high priority
- `--priority medium` sets medium priority
- `--priority low` sets low priority
- Priority appears correctly in AnyType task properties
- No priority flag = no priority set (AnyType default)

**US-4.4: Tag Assignment**
> As a user, I want to add tags to tasks so that I can categorize and filter them.

Acceptance Criteria:
- `-t work` adds "work" tag
- Multiple tags: `-t work -t urgent`
- Tags appear in AnyType task's tag/multi-select field
- Tags with spaces work: `-t "code review"`

**US-4.5: Task Description via Editor**
> As a user, I want to add a longer description by opening my editor so that I can add detailed notes.

Acceptance Criteria:
- `--editor` or `-e` opens $EDITOR
- Editor content becomes task description/notes
- Empty editor = no description (task still created)
- Respects user's EDITOR environment variable

**US-4.6: Space Override**
> As a user, I want to specify which AnyType space to use so that I can create tasks in different spaces.

Acceptance Criteria:
- `--space "Work"` creates task in "Work" space
- Partial matching: `--space work` matches "Work Projects"
- Invalid space shows available spaces
- No flag = use currently selected/default space

**US-4.7: Command Alias**
> As a user, I want a short alias for quick task creation so that I can type less.

Acceptance Criteria:
- `jarvis t` is alias for `jarvis task create`
- Mirrors `jarvis j` → `jarvis journal write` pattern
- Full command `jarvis task create` also works

---

## 5. Feature Specifications

### 5.1 Command Structure

```
jarvis task create <title> [options]
jarvis t <title> [options]          # Alias
```

### 5.2 Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--due` | `-d` | string | None | Due date (natural language or ISO) |
| `--priority` | `-p` | choice | None | Priority: high, medium, low |
| `--tag` | `-t` | string[] | [] | Tags (repeatable) |
| `--editor` | `-e` | flag | false | Open editor for description |
| `--space` | none | string | saved | Override space selection |
| `--verbose` | `-v` | flag | false | Show detailed output |

### 5.3 Natural Language Date Parsing

Supported formats:
- **Relative**: today, tomorrow
- **Weekdays**: monday, tuesday, ..., friday, next monday
- **Relative periods**: next week, in 3 days, in 2 weeks
- **Absolute**: 2025-02-15, feb 15, february 15, 15 feb
- **Mixed**: next friday, this saturday

**Past dates:** Allowed but show a warning: "Note: Due date is in the past"

Implementation: Use `dateparser` Python library (well-maintained, 10k+ GitHub stars).

### 5.4 Output Format

**Default (minimal):**
```
✓ Created: "Buy groceries" (due: Jan 25)
```

**With priority and tags:**
```
✓ Created: "Write Q1 roadmap" (due: Jan 31, priority: high, tags: planning, q1)
```

**Verbose mode:**
```
✓ Task Created
  Title:    Write Q1 roadmap
  Due:      Friday, January 31, 2025
  Priority: High
  Tags:     planning, q1
  Space:    Personal
  ID:       bafyrei...
```

**Error:**
```
✗ Could not parse date: "nextt friday"
  Try: tomorrow, next friday, 2025-02-15
```

### 5.5 Editor Integration

When `--editor` is used:
1. Create temporary file with template
2. Open user's $EDITOR (default: vim)
3. Wait for editor to close
4. Read file content as description (strip comment lines starting with #)
5. Delete temporary file
6. Create task with description

**Cancellation behavior:** If the editor exits with a non-zero status (e.g., `:cq` in vim) or the temp file is deleted, abort task creation and show: "Task creation cancelled."

**Template content:**
```
# Task: {title}
# Add your description below. Lines starting with # are ignored.
# Save and close to create the task. Exit without saving to cancel.

```

### 5.6 Input Validation

| Input | Validation | Error |
|-------|------------|-------|
| Title | Required, max 500 characters | "Task title is required" / "Title too long (max 500 chars)" |
| Title | Special characters allowed (quotes, etc.) | N/A - handled by shell quoting |
| Due date | Must parse to valid date | "Could not parse date: '{input}'" |
| Due date | Past dates allowed (with warning) | "Note: Due date is in the past" |
| Priority | Must be high/medium/low | "Invalid priority. Use: high, medium, low" |
| Tags | Duplicates auto-removed | N/A - silently deduplicated |
| Tags | Max 20 tags | "Too many tags (max 20)" |

---

## 6. User Experience

### 6.1 Quick Capture Flow

```
User types: jarvis t "Review PR #234" --due tomorrow -p high

System:
1. Parses title: "Review PR #234"
2. Parses --due: tomorrow → 2025-01-25
3. Parses --priority: high
4. Gets saved space (or prompts if first use)
5. Creates task via AnyType API
6. Displays: ✓ Created: "Review PR #234" (due: Jan 25, priority: high)

Total time: < 2 seconds
```

### 6.2 Full Creation Flow

```
User types: jarvis task create "Q1 Planning Document" --due "next friday" -t planning -t q1 -e

System:
1. Parses all options
2. Opens $EDITOR with template
3. User writes description, saves, closes editor
4. Creates task with all metadata
5. Displays: ✓ Created: "Q1 Planning Document" (due: Jan 31, tags: planning, q1)
```

### 6.3 Error Handling

| Error | Message | Recovery |
|-------|---------|----------|
| AnyType not running | "Cannot connect to AnyType. Is the desktop app running?" | Start AnyType |
| Invalid date | "Could not parse date: '{input}'. Try: tomorrow, next friday, 2025-02-15" | Re-run with valid date |
| Invalid priority | "Invalid priority: '{input}'. Use: high, medium, low" | Re-run with valid priority |
| No space selected | Prompts user to select space | Selection saved for future |
| Space not found | "Space '{name}' not found. Available: [list]" | Re-run with valid space |
| Empty title | "Task title is required" | Provide title |
| Title too long | "Title too long (max 500 chars)" | Shorten title |
| Editor cancelled | "Task creation cancelled." | Re-run command |
| Past due date | "Note: Due date is in the past" (warning, not error) | Task still created |

---

## 7. Technical Requirements

### 7.1 Dependencies

| Dependency | Purpose | Status |
|------------|---------|--------|
| Click | CLI framework | Existing |
| Rich | Terminal formatting | Existing |
| anytype-client | AnyType API | Existing |
| dateparser | Natural language dates | **New** |

### 7.2 AnyType Integration

New method required in `AnyTypeClient`:

```python
def create_task(
    self,
    space_id: str,
    title: str,
    due_date: date | None = None,
    priority: str | None = None,
    tags: list[str] | None = None,
    description: str | None = None,
) -> str:
    """Create a task in AnyType.

    Returns:
        Task object ID
    """
```

**Property mapping:**
- `title` → Task name (required)
- `due_date` → `due_date` property (date format)
- `priority` → `priority` property (select field: high/medium/low)
- `tags` → `tag` property (multi-select field)
- `description` → Task body/content (markdown text block)

Implementation pattern: Similar to existing `create_page()` method.

### 7.3 Documentation Updates

- Update `_generate_docs()` in `cli.py`
- Add `task` command group to documentation dictionary
- Add `t` alias to documentation
- Update `CLAUDE.md` with examples
- Update `jarvis docs --json` output

### 7.4 Testing Requirements

| Test Type | Coverage |
|-----------|----------|
| Unit tests | Date parsing, option validation |
| Integration tests | Task creation in AnyType |
| E2E tests | Full command execution |

---

## 8. Success Metrics

### Primary Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Command success rate | > 99% | Tasks created / commands run |
| Time to create task | < 2 seconds | CLI timing |
| Date parsing accuracy | > 95% | Valid dates parsed correctly |

### Adoption Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Daily active usage | > 5 tasks/day | Usage tracking [ASSUMPTION] |
| Feature awareness | 100% | Listed in `jarvis docs` |

### Quality Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Integration with scheduler | 100% | Created tasks appear in `jarvis analyze` |
| Zero data loss | 100% | All tasks persist in AnyType |

---

## 9. Release Strategy

### Phase 1: Core Creation (MVP)

- `jarvis task create` command
- `jarvis t` alias
- Title and due date support
- Priority and tags support
- Basic error handling

### Phase 2: Enhanced UX

- `--editor` flag for descriptions
- `--space` override
- `--verbose` output mode
- Improved error messages

### Phase 3: Documentation & Polish

- Update `jarvis docs` output
- Update `CLAUDE.md`
- Add command examples to README

---

## 10. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| dateparser library issues | Date parsing fails | Low | Fallback to ISO format only |
| AnyType API changes | Task creation breaks | Low | Pin anytype-client version |
| Editor integration issues | Description feature fails | Medium | Make editor optional, test with common editors |
| Task type not found in space | Cannot create tasks | Low | Clear error message, guide user |

---

## 11. Out of Scope

Explicitly excluded from this specification:

- **Task listing** (`jarvis task list`) — Future epic
- **Task completion** (`jarvis task done`) — Future epic
- **Task editing** (`jarvis task edit`) — Future epic
- **Recurring tasks** — Future epic
- **Task templates** — Future epic
- **Bulk task creation** — Future epic
- **Task import/export** — Future epic

---

## 12. Open Questions

### Resolved

| Question | Decision | Rationale |
|----------|----------|-----------|
| Due date vs scheduled date? | Single `--due` flag | Simplicity; existing code uses due_date |
| Interactive mode? | No | Tasks should be quick; use --editor for details |
| Tag format? | Repeatable `--tag` flag | Cleaner than comma-separated |
| Default priority? | None (null) | Let AnyType handle defaults |

### Resolved (During Review)

| Question | Decision | Rationale |
|----------|----------|-----------|
| Should `--editor` have a template? | Yes, with comment header | Helps users understand the format |
| Should we validate tags exist in AnyType? | No validation, create new tags | Simpler UX; AnyType handles tag creation |
| Editor cancellation behavior? | Abort task creation | User intent is clear when they cancel |
| Title length limit? | Max 500 characters | Reasonable for task titles |
| Duplicate tags? | Silently deduplicate | No user action needed |
| Past due dates? | Allow with warning | User may intentionally backdate |

---

## 13. Appendix

### A. Command Examples

```bash
# Quick capture
jarvis t "Buy milk"
jarvis t "Call mom" --due sunday
jarvis t "Fix bug #123" -d tomorrow -p high

# With tags
jarvis t "Review PR" -t work -t code-review -d friday

# Full creation with description
jarvis task create "Q1 Planning" --due "jan 31" -p high -t planning -e

# Different space
jarvis t "Personal errand" --space personal --due tomorrow
```

### B. Integration with Existing Commands

Tasks created with `jarvis task` will:
- Appear in `jarvis analyze` output
- Be considered for `jarvis suggest` rescheduling
- Be affected by `jarvis rebalance`
- Respect `bar_movement` tag if applied

### C. Comparison with Journal Command

| Aspect | Journal (`j`) | Task (`t`) |
|--------|---------------|------------|
| Primary content | Free-form text | Title |
| Date | Entry date (automatic) | Due date (optional) |
| Metadata | Title (optional) | Priority, tags |
| Editor mode | `--editor`, `--interactive` | `--editor` only |
| Output location | Journal hierarchy | Task list |

---

*Product Specification v1.1*
*Created: 2025-01-24*
*Reviewed: 2025-01-24 (5-perspective review complete)*
*Status: Ready for Technical Specification*
