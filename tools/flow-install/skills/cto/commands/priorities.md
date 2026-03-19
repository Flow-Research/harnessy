---
description: Generate or update quarterly priorities with ranked items (Critical/High/Medium/Low)
argument-hint: "Optional: context about current priorities or focus areas"
---

# CTO Priorities

You are helping generate or update quarterly priorities.

## User Input

$ARGUMENTS

## Context

- Current date: !`date +%Y-%m-%d`
- Current quarter: (Calculate from date: Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec)

### Existing Priorities
!`cat .notes/priorities.md 2>/dev/null || echo "No priorities.md yet - will create from template"`

### Related Context
!`head -30 .notes/quarterly-plan.md 2>/dev/null || echo "No quarterly plan yet"`

## Template Reference

Use this structure for `.notes/priorities.md`:

```markdown
# Project Priorities

**Last Updated:** [date]
**Quarter:** Q[X] [Year]

---

## 🔴 Critical (Do Now)

### Priority 1: [Title]
- **Impact:** [Describe business/technical impact]
- **Effort:** [Small/Medium/Large] - [X] hours
- **Owner:** [Team member or role]
- **Due:** [YYYY-MM-DD]
- **Dependencies:** [List of blocking items]
- **Acceptance Criteria:**
  - [ ] [Criteria 1]
  - [ ] [Criteria 2]

---

## 🟠 High (This Quarter)

---

## 🟡 Medium (Next Quarter)

---

## 🟢 Low (Backlog)

---

## Progress Tracking

| Priority | Title | Status | % Complete | Last Updated |
|----------|-------|--------|------------|--------------|
| 1 | [Title] | [In Progress/Done/Blocked] | X% | Date |

---

## Notes

### Changes Since Last Update
- [Change 1] - Date

### Blockers
- [Blocker 1] - Impact, Expected Resolution
```

## Your Task

### If No Priorities Exist:

1. Ask the user:
   - What's the current quarter and year?
   - What are the major focus areas?
   - What are the top 3-5 things that MUST get done?
   - What's the team capacity?
   - Any known blockers or dependencies?

2. Generate `.notes/priorities.md` using the template

### If Priorities Exist:

1. Show current priorities summary
2. Ask what needs to change:
   - Add new priorities?
   - Re-rank existing items?
   - Mark items as completed?
   - Update status or progress?

3. Update the file preserving existing content

## Priority Criteria

| Level | Criteria |
|-------|----------|
| 🔴 Critical | Blocks revenue, affects user safety, regulatory requirement |
| 🟠 High | Significant business impact, committed deadline |
| 🟡 Medium | Important but not urgent, next quarter candidate |
| 🟢 Low | Nice to have, backlog item |

## Effort Estimation

| Size | Hours | Description |
|------|-------|-------------|
| Small | 1-4h | Quick fix, single file change |
| Medium | 4-16h | Feature addition, multiple files |
| Large | 16-40h | Major feature, cross-cutting |
| XLarge | 40h+ | Epic, requires breakdown |
