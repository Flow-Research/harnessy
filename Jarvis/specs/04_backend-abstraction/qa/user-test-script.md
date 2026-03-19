# User Test Script: Backend Abstraction Layer

> **Epic:** 04_backend-abstraction
> **Version:** 1.0
> **Generated:** 2026-01-25
> **Purpose:** Manual E2E testing checklist for backend abstraction features

---

## Prerequisites

Before running these tests, ensure:

- [ ] AnyType desktop app is running on `localhost:31009`
- [ ] Python 3.11+ installed
- [ ] Jarvis installed (`uv sync` or `pip install -e .`)
- [ ] (Optional for Notion tests) `JARVIS_NOTION_TOKEN` environment variable set
- [ ] (Optional for Notion tests) Notion workspace configured in `~/.jarvis/config.yaml`

---

## Test Suite 1: Configuration System

### TC-1.1: View Configuration Path
```bash
jarvis config path
```
**Expected:** Shows path to `~/.jarvis/config.yaml`

- [ ] Path displayed correctly
- [ ] Path includes `.jarvis/config.yaml`

### TC-1.2: View Current Backend
```bash
jarvis config backend
```
**Expected:** Shows current active backend and available backends

- [ ] Active backend displayed (anytype or notion)
- [ ] Available backends listed (anytype, notion)
- [ ] Status indicators shown

### TC-1.3: Show Full Configuration
```bash
jarvis config show
```
**Expected:** Displays current configuration settings

- [ ] Configuration file path shown
- [ ] Active backend shown
- [ ] Backend-specific settings displayed

### TC-1.4: View Backend Capabilities
```bash
jarvis config capabilities
```
**Expected:** Shows capabilities of current backend

- [ ] Capability table displayed
- [ ] Shows tasks, journal, tags, search support
- [ ] Indicates ✓/✗ for each capability

### TC-1.5: Initialize Configuration
```bash
jarvis config init --force
```
**Expected:** Creates or overwrites config file

- [ ] Config file created/updated at `~/.jarvis/config.yaml`
- [ ] Default settings applied
- [ ] Success message displayed

---

## Test Suite 2: Space Operations (AnyType)

### TC-2.1: List Spaces
```bash
jarvis spaces
```
**Expected:** Lists available AnyType spaces

- [ ] At least one space listed
- [ ] Space names displayed
- [ ] Space IDs shown (or selectable by number)

### TC-2.2: Select Space
```bash
jarvis spaces
# Then select a space by number
```
**Expected:** Space selection saved

- [ ] Selection prompt appears
- [ ] Selection confirmed
- [ ] Subsequent commands use selected space

---

## Test Suite 3: Task Operations

### TC-3.1: Create Task (Minimal)
```bash
jarvis task add "Test task from backend abstraction"
```
**Expected:** Task created successfully

- [ ] Task created
- [ ] Task ID/confirmation displayed
- [ ] No errors

### TC-3.2: Create Task (Full)
```bash
jarvis task add "Important test task" --due tomorrow --priority high
```
**Expected:** Task created with all attributes

- [ ] Task created
- [ ] Due date set correctly
- [ ] Priority set to high

### TC-3.3: List Tasks
```bash
jarvis task list
```
**Expected:** Shows tasks including newly created ones

- [ ] Tasks listed
- [ ] Test tasks from TC-3.1 and TC-3.2 visible
- [ ] Due dates and priorities shown

### TC-3.4: View Task Analysis
```bash
jarvis analyze
```
**Expected:** Shows task distribution analysis

- [ ] Analysis displayed
- [ ] Shows workload distribution
- [ ] No backend errors

---

## Test Suite 4: Journal Operations

### TC-4.1: Write Journal Entry (Quick)
```bash
jarvis j "Testing journal from backend abstraction layer"
```
**Expected:** Journal entry created

- [ ] Entry created
- [ ] Title auto-generated (or prompt shown)
- [ ] Confirmation displayed

### TC-4.2: Write Journal Entry (With Title)
```bash
jarvis j "This is my test entry content" --title "Backend Test Entry"
```
**Expected:** Journal entry created with custom title

- [ ] Entry created
- [ ] Title is "Backend Test Entry"
- [ ] Content saved

### TC-4.3: List Journal Entries
```bash
jarvis journal list
```
**Expected:** Shows recent journal entries

- [ ] Entries listed
- [ ] Test entries visible
- [ ] Dates shown correctly

### TC-4.4: Read Journal Entry
```bash
jarvis journal read 1
```
**Expected:** Displays the most recent journal entry

- [ ] Entry content displayed
- [ ] Title shown
- [ ] Date shown

---

## Test Suite 5: Backend Switching

### TC-5.1: Check Current Backend
```bash
jarvis status
```
**Expected:** Shows current backend status

- [ ] Backend name displayed
- [ ] Connection status shown
- [ ] Space information shown

### TC-5.2: Switch to Different Backend (Config Edit)

1. Edit `~/.jarvis/config.yaml`
2. Change `active_backend: anytype` to `active_backend: notion`
3. Run:
```bash
jarvis config backend
```

**Expected:**
- If Notion configured: Shows Notion as active
- If Notion not configured: Shows error about missing Notion config

- [ ] Backend change reflected
- [ ] Appropriate error if Notion not configured

### TC-5.3: Verify Backend Independence
After switching backends and back:
```bash
# Switch back to anytype
# Edit config or use config commands

jarvis task list
jarvis journal list
```

**Expected:** Commands work identically

- [ ] Same CLI interface
- [ ] Same output format
- [ ] Backend shown in status

---

## Test Suite 6: Error Handling

### TC-6.1: Connection Error (AnyType not running)

1. Stop AnyType desktop app
2. Run:
```bash
jarvis task list
```

**Expected:** Clear error message

- [ ] Error indicates connection failed
- [ ] Suggests starting AnyType
- [ ] No stack trace (user-friendly)

### TC-6.2: Invalid Backend
Edit config to have invalid backend:
```yaml
active_backend: invalid_backend
```
```bash
jarvis status
```

**Expected:** Clear error about invalid backend

- [ ] Error message mentions invalid backend
- [ ] Lists valid options
- [ ] Suggests fix

### TC-6.3: Missing Notion Configuration
With Notion as active_backend but no Notion config:
```bash
jarvis task list
```

**Expected:** Error about missing Notion configuration

- [ ] Error mentions Notion not configured
- [ ] Suggests adding config
- [ ] No crash

---

## Test Suite 7: CLI Help & Documentation

### TC-7.1: Main Help
```bash
jarvis --help
```

**Expected:** Shows all available commands

- [ ] All main commands listed
- [ ] Descriptions provided
- [ ] No errors

### TC-7.2: Config Help
```bash
jarvis config --help
```

**Expected:** Shows config subcommands

- [ ] backend, capabilities, show, init, path commands listed
- [ ] Descriptions clear

### TC-7.3: AI Agent Documentation
```bash
jarvis docs
```

**Expected:** Outputs full CLI documentation

- [ ] Markdown formatted output
- [ ] All commands documented
- [ ] Examples included

### TC-7.4: AI Agent Documentation (JSON)
```bash
jarvis docs --json
```

**Expected:** Machine-readable JSON output

- [ ] Valid JSON output
- [ ] All commands included
- [ ] Parseable by AI agents

---

## Test Suite 8: Integration Verification

### TC-8.1: Full Workflow Test

Run complete workflow:
```bash
# 1. Check status
jarvis status

# 2. Create a task
jarvis task add "Full workflow test task" --due "next monday" --priority medium

# 3. List tasks
jarvis task list

# 4. Create journal entry
jarvis j "Completed full workflow test"

# 5. List journal
jarvis journal list

# 6. View analysis
jarvis analyze
```

**Expected:** All operations complete successfully

- [ ] Status shows connected
- [ ] Task created
- [ ] Task appears in list
- [ ] Journal entry created
- [ ] Journal entry appears in list
- [ ] Analysis completes

### TC-8.2: Context System Integration
```bash
# Check context status
jarvis context status

# Should show context sources
```

**Expected:** Context system works with backend abstraction

- [ ] Context files detected
- [ ] Global/folder context shown
- [ ] No errors

---

## Results Summary

| Suite | Tests | Passed | Failed | Notes |
|-------|-------|--------|--------|-------|
| Configuration | 5 | | | |
| Spaces | 2 | | | |
| Tasks | 4 | | | |
| Journal | 4 | | | |
| Backend Switching | 3 | | | |
| Error Handling | 3 | | | |
| Help & Docs | 4 | | | |
| Integration | 2 | | | |
| **Total** | **27** | | | |

---

## Sign-Off

**Tester:** _______________
**Date:** _______________
**Environment:**
- OS: _______________
- Python: _______________
- AnyType: _______________
- Jarvis Version: _______________

**Overall Result:** ☐ PASS / ☐ FAIL

**Notes:**
