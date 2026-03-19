---
description: Generate comprehensive quarterly strategic plan with goals, initiatives, and resource allocation
argument-hint: "Optional: quarter (Q1-Q4) and year, or focus areas"
---

# CTO Quarterly Plan

You are helping create a comprehensive quarterly strategic plan.

## User Input

$ARGUMENTS

## Context

- Current date: !`date +%Y-%m-%d`
- Current quarter: (Calculate from date: Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec)

### Existing Quarterly Plan
!`cat .notes/quarterly-plan.md 2>/dev/null || echo "No quarterly-plan.md yet"`

### Current Priorities
!`head -50 .notes/priorities.md 2>/dev/null || echo "No priorities yet"`

### Current Metrics
!`head -30 .notes/business-metrics.md 2>/dev/null || echo "No metrics yet"`

### Technical Debt Summary
!`head -20 .notes/technical-debt.md 2>/dev/null || echo "No debt tracker yet"`

## Your Task

### Step 1: Gather Strategic Context

Ask the user:

**Goals:**
- What are the 3-5 strategic goals for this quarter?
- What does success look like for each goal?

**Initiatives:**
- What major initiatives will achieve these goals?
- What are the milestones for each initiative?

**KPIs:**
- Target MRR?
- Target subscriber count?
- Target test coverage?
- Other key metrics?

**Resources:**
- Team capacity (FTEs, hours)?
- Budget constraints?
- External dependencies?

**Risks:**
- What could derail the plan?
- What mitigations are in place?

### Step 2: Generate Quarterly Plan

Create `.notes/quarterly-plan.md`:

```markdown
# Quarterly Plan - Q[X] [Year]

**Last Updated:** [date]
**Status:** In Progress
**Review Date:** [mid-quarter date]

---

## Executive Summary

This quarter focuses on:
1. **[Focus Area 1]** - [Brief description]
2. **[Focus Area 2]** - [Brief description]
3. **[Focus Area 3]** - [Brief description]

**Key Metrics:**
- Target MRR: ₦X
- Target Subscribers: X
- Target Test Coverage: X%

---

## 🎯 Strategic Goals

### Goal 1: [Title]
**Success Criteria:**
- [ ] Criteria 1
- [ ] Criteria 2
- [ ] Criteria 3

**Impact:** [business/technical impact]
**Priority:** Critical/High/Medium/Low
**Timeline:** [start] - [end]
**Owner:** @user

---

## 📋 Initiatives

### Initiative 1: [Title]
**Status:** 🟢 On Track / 🟡 At Risk / 🔴 Blocked
**Progress:** X%

**Milestones:**
- [ ] Phase 1: [Description] - Due [date]
- [ ] Phase 2: [Description] - Due [date]
- [ ] Phase 3: [Description] - Due [date]

**Owner:** @user
**Dependencies:** [list]
**Risks:** [list]
**Mitigation:** [list]

---

## 📊 Key Performance Indicators

### Business KPIs
| Metric | Previous Q | Target | Forecast | Status |
|--------|------------|--------|----------|--------|
| MRR | ₦X | ₦Y | ₦Z | 🟢/🟡/🔴 |
| Subscribers | X | Y | Z | 🟢/🟡/🔴 |
| Retention | X% | Y% | Z% | 🟢/🟡/🔴 |
| Churn | X% | Y% | Z% | 🟢/🟡/🔴 |

### Technical KPIs
| Metric | Previous Q | Target | Forecast | Status |
|--------|------------|--------|----------|--------|
| Coverage | X% | 70% | Z% | 🟢/🟡/🔴 |
| P95 Latency | Xms | <500ms | Zms | 🟢/🟡/🔴 |
| Uptime | X% | 99.9% | Z% | 🟢/🟡/🔴 |
| Debt Resolved | X | 10 | Z | 🟢/🟡/🔴 |

---

## 🗓️ Monthly Breakdown

### Month 1
**Focus:** [key focus]
**Deliverables:**
- [ ] Deliverable 1 - [date] - @owner
- [ ] Deliverable 2 - [date] - @owner

### Month 2
...

### Month 3
...

---

## 🚨 Risks & Mitigation

### Risk 1: [Title]
**Likelihood:** High/Medium/Low
**Impact:** Critical/High/Medium/Low
**Mitigation:** [strategy]
**Owner:** @user

---

## 💰 Resource Allocation

### Engineering Hours
| Initiative | Estimated | Allocated | Remaining |
|------------|-----------|-----------|-----------|
| Initiative 1 | Xh | 0h/Xh | Xh |
| Initiative 2 | Xh | 0h/Xh | Xh |
| **Total** | **Xh** | **0h/Xh** | **Xh** |

### Team Capacity
- **Engineers:** X FTE
- **Available Hours:** X hours/quarter
- **Utilization:** X%

---

## 🎉 Wins & Learnings

### Wins This Quarter
- [To be filled as quarter progresses]

### Key Learnings
- [To be filled]

---

## 📋 Next Quarter Preview

### Carryover Initiatives
- [Items likely to carry over]

### Planned New Initiatives
- [Early planning items]

---

## Related Documents
- [.notes/priorities.md](./priorities.md)
- [.notes/technical-debt.md](./technical-debt.md)
- [.notes/business-metrics.md](./business-metrics.md)
- [.notes/testing-roadmap.md](./testing-roadmap.md)
```

## Quarter Dates Reference

| Quarter | Months | Start | End |
|---------|--------|-------|-----|
| Q1 | Jan-Mar | Jan 1 | Mar 31 |
| Q2 | Apr-Jun | Apr 1 | Jun 30 |
| Q3 | Jul-Sep | Jul 1 | Sep 30 |
| Q4 | Oct-Dec | Oct 1 | Dec 31 |
