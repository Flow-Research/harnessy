# Brainstorm: Task Creation Command

## Overview

Add a `jarvis task` command for creating tasks directly in AnyType from the CLI, enabling both quick capture and full task creation workflows.

## Problem Statement

Currently, Jarvis can analyze, reschedule, and manage existing tasks in AnyType, but users must open the AnyType desktop app to create new tasks. This breaks the CLI-first workflow and adds friction to task capture — especially for quick thoughts that need to be captured immediately.

## Proposed Solution

A new `jarvis task` command group with:
1. **Quick capture mode** — Minimal friction for fast task entry
2. **Full creation mode** — Complete task setup with all metadata

### Command Structure

```bash
# Task command group
jarvis task create "Task title" [options]
jarvis task list                    # Future scope
jarvis task done <id>               # Future scope

# Quick alias (like 'j' for journal)
jarvis t "Task title" [options]
```

### Supported Fields

| Field | CLI Flag | Required | Description |
|-------|----------|----------|-------------|
| Title | positional | Yes | The task name |
| Due date | `--due`, `-d` | No | When the task is due (natural language supported) |
| Priority | `--priority`, `-p` | No | Task priority: `high`, `medium`, `low` |
| Tags | `--tag`, `-t` | No | Repeatable flag for multiple tags |
| Description | `--editor`, `-e` | No | Opens editor for longer task notes |

### Natural Language Date Support

The `--due` flag should accept:
- **Relative dates:** `today`, `tomorrow`, `next monday`, `in 3 days`, `next week`
- **Absolute dates:** `2025-02-15`, `feb 15`, `january 30`
- **Smart parsing:** Using `dateparser` library for flexibility

### Usage Examples

**Quick capture (most common):**
```bash
jarvis t "Buy groceries" --due tomorrow
# → ✓ Created: "Buy groceries" (due: Jan 25)

jarvis t "Review PR" -d friday -p high
# → ✓ Created: "Review PR" (due: Jan 31, priority: high)
```

**Full creation:**
```bash
jarvis task create "Write Q1 roadmap" --due "next friday" -p high -t planning -t q1 --editor
# Opens $EDITOR for description
# → ✓ Created: "Write Q1 roadmap" (due: Jan 31, priority: high, tags: planning, q1)
```

**Without due date (someday tasks):**
```bash
jarvis t "Learn Rust"
# → ✓ Created: "Learn Rust" (no due date)
```

## Design Decisions

### 1. Due Date vs Scheduled Date

**Decision:** Use a single `--due` flag that sets `due_date` in AnyType.

**Rationale:**
- The existing codebase treats `due_date` as the primary date field
- The scheduler reads `scheduled_date` with `due_date` as fallback
- Simplicity over flexibility — one date concept to understand

### 2. No Interactive Mode

**Decision:** Don't implement a multi-prompt interactive mode for task creation.

**Rationale:**
- Tasks should be quick to create (unlike journal entries which benefit from reflection)
- Use `--editor` flag for description if needed
- Keeps the command fast and scriptable

### 3. Command Alias

**Decision:** `jarvis t` as alias for `jarvis task create` (not `jarvis task`).

**Rationale:**
- Mirrors `jarvis j` → `jarvis journal write` pattern
- Most common action (create) gets the shortcut
- Future subcommands (`list`, `done`) remain accessible

### 4. Tag Input Format

**Decision:** Repeatable `--tag` flag instead of comma-separated.

**Rationale:**
- Cleaner: `-t work -t urgent` vs `--tags "work,urgent"`
- No quoting/escaping needed for tags with spaces
- Consistent with CLI conventions

## Technical Considerations

### AnyType Integration

- Need to add `create_task()` method to `AnyTypeClient`
- Similar pattern to existing `create_page()` for journal entries
- Must set the Task type and appropriate properties

### Dependencies

- **dateparser** library for natural language date parsing
- Already using Click + Rich for CLI (no new dependencies there)

### Space Selection

- Use existing `select_space()` / `get_selected_space()` pattern
- Task created in the currently selected AnyType space

### Documentation Updates

- Update `_generate_docs()` in `cli.py` to include the new `task` command group
- Add `task` and `t` commands to the documentation dictionary
- Ensure `jarvis docs` and `jarvis docs --json` output includes all new subcommands
- Update `CLAUDE.md` with new command examples

## Success Criteria

1. Create a task in AnyType with a single CLI command
2. Task appears correctly in AnyType with due date, priority, and tags
3. Created tasks work seamlessly with `jarvis analyze` and `jarvis suggest`
4. Natural language dates parse correctly
5. `--editor` flag opens editor and saves description to task

## Out of Scope (Future Epics)

- `jarvis task list` — List tasks from CLI
- `jarvis task done <id>` — Mark task complete
- `jarvis task edit <id>` — Edit existing task
- Recurring task creation
- Task templates

## Open Questions

1. **Default priority:** Should tasks without `--priority` default to `medium`, `low`, or `none`?
   - **Recommendation:** No default (null) — let AnyType handle it

2. **Space flag:** Should we add `--space` to override the selected space?
   - **Recommendation:** Yes, for consistency with other commands

3. **Confirmation output:** Verbose or minimal?
   - **Recommendation:** Single line with key info, verbose with `--verbose`

---

*Brainstorm completed: 2025-01-24*
*Ready for PRD generation*
