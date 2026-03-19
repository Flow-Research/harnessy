# [PROJECT_NAME] - Manual User Test Script

**Epic:** [EPIC_ID]
**Date:** [DATE]
**Tester:** ________________
**Environment:** Local Development

---

## Prerequisites

Before starting, ensure:

```bash
# Start command (project-specific)
[START_COMMAND]

# Verify services are running:
# - Backend: [BACKEND_URL]
# - Frontend: [FRONTEND_URL]
# - Database: [DB_URL]
```

**Stop command:**
```bash
[STOP_COMMAND]
```

### Environment Checklist
- [ ] Backend running at `[BACKEND_URL]`
- [ ] Frontend running at `[FRONTEND_URL]`
- [ ] Database/services running
- [ ] Test data exists (if required)
- [ ] Browser DevTools open (Network tab for monitoring API calls)

---

## Test Session Checklist

| Section | Status | Notes |
|---------|--------|-------|
[TEST_SECTIONS_TABLE]

---

[TEST_SECTIONS]

---

## Test Session Summary

**Date:** ________________
**Tester:** ________________
**Total Tests:** [TOTAL_TESTS]
**Passed:** ____
**Failed:** ____
**Blocked:** ____

### Issues Found

| # | Severity | Description | Steps to Reproduce |
|---|----------|-------------|-------------------|
| 1 | | | |
| 2 | | | |
| 3 | | | |

### Notes

```
[Additional observations, suggestions, or notes]
```

---

## Quick Reference: API Endpoints Used

| Feature | Endpoint | Method |
|---------|----------|--------|
[API_ENDPOINTS_TABLE]

---

## Quick Start Commands

```bash
[QUICK_START_COMMANDS]
```

---

## Test Section Template

Use this format for each test section:

```markdown
## N. [Section Name]

### N.1 [Subsection Name]
| # | Action | Expected Result | Pass/Fail |
|---|--------|-----------------|-----------|
| N.1.1 | [Action description] | [Expected behavior] | ⬜ |
| N.1.2 | [Action description] | [Expected behavior] | ⬜ |
```

### Test Categories

When generating test sections, cover these categories as applicable:

1. **Initial State** - Page loads correctly, default values
2. **Happy Path** - Main user flows work as expected
3. **Edge Cases** - Empty states, boundary conditions
4. **Error Handling** - Network failures, validation errors
5. **Keyboard Navigation** - Shortcuts, accessibility
6. **Responsive Behavior** - Different screen sizes
7. **State Persistence** - Navigation, refresh behavior
8. **Cross-Feature Integration** - Features working together

### Severity Levels for Issues

| Severity | Description |
|----------|-------------|
| Critical | Blocks core functionality, data loss |
| High | Feature doesn't work as specified |
| Medium | Workaround available, non-blocking |
| Low | Cosmetic, minor usability |
