---
description: Prioritize and track technical debt from codebase TODOs with ROI scoring
argument-hint: "Optional: specific area to scan or manual debt items"
---

# CTO Technical Debt Tracker

You are analyzing and prioritizing technical debt in the codebase.

## User Input

$ARGUMENTS

## Context

- Current date: !`date +%Y-%m-%d`

### Existing Technical Debt
!`cat .notes/technical-debt.md 2>/dev/null || echo "No technical-debt.md yet"`

### TODO Comments in Codebase
!`grep -rn "TODO" src/ --include="*.ts" --include="*.tsx" 2>/dev/null | head -50 || echo "No TODOs found or src/ doesn't exist"`

### FIXME Comments
!`grep -rn "FIXME" src/ --include="*.ts" --include="*.tsx" 2>/dev/null | head -20 || echo "No FIXMEs found"`

## Your Task

### Step 1: Scan for TODOs

Search the codebase for:
- `TODO` comments
- `FIXME` comments
- `HACK` comments
- `XXX` comments

### Step 2: Categorize & Score Each Item

For each debt item, determine:

**Impact Score:**
| Level | Score | Criteria |
|-------|-------|----------|
| Critical | 10 | Affects core revenue, user safety, data privacy |
| High | 7 | Affects performance, user experience |
| Medium | 4 | Technical quality, maintainability |
| Low | 2 | Nice to have, optimization |

**Effort Score:**
| Size | Score | Time |
|------|-------|------|
| Small | 1 | 1-3 hours |
| Medium | 3 | 4-8 hours |
| Large | 7 | 1-3 days |
| XLarge | 10 | 1+ weeks |

**ROI Calculation:**
```
ROI = (Impact Score ÷ Effort Score) × 10
```

Higher ROI = prioritize first

### Step 3: Generate Debt Tracker

Create/update `.notes/technical-debt.md`:

```markdown
# Technical Debt Tracker

**Last Updated:** [date]
**Total Debt Items:** [X]
**Resolved This Quarter:** [X]
**New This Quarter:** [X]

## Summary
- **Critical Debt:** [X]
- **High Debt:** [X]
- **Medium Debt:** [X]
- **Low Debt:** [X]

---

## 🔴 Critical Debt (Immediate Action Required)

| ID | File | Description | Impact | Effort | ROI | Status | Owner | Due |
|----|------|-------------|--------|--------|-----|--------|-------|-----|
| TD-001 | file.ts:42 | Description | 10 | 3 | 33 | Open | TBD | TBD |

---

## 🟠 High Debt (This Quarter)

| ID | File | Description | Impact | Effort | ROI | Status | Owner | Due |
|----|------|-------------|--------|--------|-----|--------|-------|-----|

---

## 🟡 Medium Debt (Next Quarter)

---

## 🟢 Low Debt (Backlog)

---

## Debt Reduction Progress

**Target:** 10 items resolved this quarter
**Current:** 0/10
**Completion:** 0%

### Recent Completions
- [x] TD-XXX: [Title] - Resolved on YYYY-MM-DD

## ROI Formula
ROI = (Impact Score ÷ Effort Score) × 10
```

### Step 4: Present Findings

Show:
1. Total TODOs found
2. Categorization breakdown
3. Top 10 by ROI score
4. Recommended order of attack

Ask user to confirm before writing the file.

## Error Handling

| Situation | Response |
|-----------|----------|
| No TODOs found | Ask user to manually list known debt items |
| src/ doesn't exist | Ask for correct source directory |
| Too many TODOs (>100) | Focus on top 50 by file, ask to narrow scope |
