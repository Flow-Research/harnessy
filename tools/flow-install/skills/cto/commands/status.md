---
description: Show current status of all CTO notes and overall progress
argument-hint: ""
---

# CTO Status

You are showing the current status of all CTO notes and overall progress.

## Context

- Current date: !`date +%Y-%m-%d`
- Current quarter: (Calculate from date: Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec)

### Notes Folder Status
!`ls -la .notes/ 2>/dev/null || echo "No .notes folder exists"`

### Priorities Summary
!`head -40 .notes/priorities.md 2>/dev/null || echo "❌ No priorities.md"`

### Technical Debt Summary
!`head -25 .notes/technical-debt.md 2>/dev/null || echo "❌ No technical-debt.md"`

### Business Metrics Summary
!`head -30 .notes/business-metrics.md 2>/dev/null || echo "❌ No business-metrics.md"`

### Testing Roadmap Summary
!`head -30 .notes/testing-roadmap.md 2>/dev/null || echo "❌ No testing-roadmap.md"`

### Quarterly Plan Summary
!`head -40 .notes/quarterly-plan.md 2>/dev/null || echo "❌ No quarterly-plan.md"`

### Architecture Decisions Summary
!`head -30 .notes/architecture-decisions.md 2>/dev/null || echo "❌ No architecture-decisions.md"`

## Your Task

Generate a comprehensive status report:

```markdown
# CTO Status Report

**Generated:** [date]
**Quarter:** Q[X] [Year]

---

## 📁 Notes Overview

| Note | Status | Last Updated | Summary |
|------|--------|--------------|---------|
| priorities.md | ✅/❌ | [date] | X critical, Y high items |
| technical-debt.md | ✅/❌ | [date] | X items, Y resolved |
| business-metrics.md | ✅/❌ | [date] | MRR: ₦X, Subs: Y |
| testing-roadmap.md | ✅/❌ | [date] | X% coverage, Week Y/6 |
| quarterly-plan.md | ✅/❌ | [date] | X/Y goals on track |
| architecture-decisions.md | ✅/❌ | [date] | X ADRs recorded |

---

## 🎯 Priorities Status

**Critical Items:** X
**High Items:** Y
**Blocked Items:** Z

Top 3 Critical:
1. [Priority 1] - [status]
2. [Priority 2] - [status]
3. [Priority 3] - [status]

---

## 🔧 Technical Debt Status

**Total Items:** X
**Resolved This Quarter:** Y
**Target:** 10/quarter

High-ROI Items Pending:
1. [Item] - ROI: X
2. [Item] - ROI: Y

---

## 📊 Metrics Snapshot

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| MRR | ₦X | ₦Y | 🟢/🟡/🔴 |
| Subscribers | X | Y | 🟢/🟡/🔴 |
| Test Coverage | X% | 70% | 🟢/🟡/🔴 |

---

## 🧪 Testing Progress

**Current Coverage:** X%
**Target Coverage:** 70%
**Week:** X/6
**Status:** 🟢 On Track / 🟡 At Risk / 🔴 Behind

---

## 📋 Quarterly Goals

| Goal | Progress | Status |
|------|----------|--------|
| [Goal 1] | X% | 🟢/🟡/🔴 |
| [Goal 2] | X% | 🟢/🟡/🔴 |

---

## ⚠️ Attention Needed

- [List items that need attention]
- [Blockers]
- [At-risk items]

---

## 📝 Recommended Actions

1. [Action 1] - Run `/cto:X`
2. [Action 2] - Run `/cto:Y`
```

## Status Indicators

| Icon | Meaning |
|------|---------|
| ✅ | Note exists and is up to date |
| ❌ | Note doesn't exist |
| 🟢 | On track |
| 🟡 | At risk |
| 🔴 | Needs attention |

## Recommendations

Based on what's missing or outdated, suggest which commands to run:

- Missing priorities? → `/cto:priorities`
- No debt tracking? → `/cto:debt`
- Outdated metrics? → `/cto:metrics`
- No quarterly plan? → `/cto:quarterly`
- Stale testing roadmap? → `/cto:testing`
