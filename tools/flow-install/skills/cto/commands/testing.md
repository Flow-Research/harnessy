---
description: Update testing roadmap and track progress toward coverage goals
argument-hint: "Optional: current status update or week number"
---

# CTO Testing Roadmap

You are helping update the testing roadmap and track progress.

## User Input

$ARGUMENTS

## Context

- Current date: !`date +%Y-%m-%d`

### Existing Testing Roadmap
!`cat .notes/testing-roadmap.md 2>/dev/null || echo "No testing-roadmap.md yet"`

### Testing Strategy Doc (if exists)
!`head -100 docs/TESTING_STRATEGY.md 2>/dev/null || echo "No TESTING_STRATEGY.md found"`

### Current Test Files
!`find . -name "*.test.ts" -o -name "*.spec.ts" 2>/dev/null | head -30 || echo "No test files found"`

### Test Count
!`find . -name "*.test.ts" -o -name "*.spec.ts" 2>/dev/null | wc -l || echo "0"`

## Your Task

### Step 1: Gather Status

Ask the user:

1. **Current Week/Phase** - Where are we in the roadmap?
2. **Tests Completed** - What was done since last update?
3. **Coverage Percentage** - Current test coverage (if known)
4. **Blockers** - Any issues preventing progress?
5. **Adjustments** - Any timeline or scope changes needed?

### Step 2: Update Roadmap

Update `.notes/testing-roadmap.md`:

```markdown
# Testing Roadmap

**Last Updated:** [date]
**Current Coverage:** X% (Y tests in Z files)
**Target Coverage:** 70%
**Timeline:** 6 weeks ([start] - [end])

---

## Current Status

### Coverage Summary
| Category | Files | Current | Target | Status |
|----------|-------|---------|--------|--------|
| Services | X | Y% | 70% | 🟢/🟡/🔴 |
| Handlers | X | Y% | 70% | 🟢/🟡/🔴 |
| Utils | X | Y% | 80% | 🟢/🟡/🔴 |
| Libs | X | Y% | 70% | 🟢/🟡/🔴 |

---

## Weekly Plan

### Week 1: Foundation & Quick Wins
**Dates:** [dates]
**Goal:** Establish patterns and cover high-value business logic
**Status:** 🟢 Complete / 🟡 In Progress / ⬜ Not Started

| Test File | Source File | Status |
|-----------|-------------|--------|
| `coupon.service.test.ts` | `src/service/coupon.service.ts` | ✅/⬜ |
| `payment.service.test.ts` | `src/service/payment.service.ts` | ✅/⬜ |

**Week 1 Progress:** X/Y complete (Z%)

---

### Week 2: Handler Coverage
...

---

## Cumulative Progress

| Week | Target Tests | Actual Tests | Coverage | Status |
|------|--------------|--------------|----------|--------|
| 0 | 150 | 150 | 15% | ✅ |
| 1 | 210 | X | X% | 🟢/🟡/🔴 |
| 2 | 260 | - | - | ⬜ |
| 3 | 300 | - | - | ⬜ |
| 4 | 350 | - | - | ⬜ |
| 5 | 390 | - | - | ⬜ |
| 6 | 420 | - | 70% | ⬜ |

---

## Blockers & Risks

### Current Blockers
- [ ] [Blocker] - Impact, Resolution plan

### Risks
- [ ] [Risk] - Likelihood, Impact, Mitigation

---

## Recent Updates

### [Date]
- Completed: [list of tests]
- Coverage: X% → Y%
- Notes: [any observations]
```

### Step 3: Analyze Progress

Calculate and show:
- Tests completed vs target
- Coverage delta
- Velocity (tests/week)
- Projected completion date
- At-risk areas

## Priority Matrix for Tests

| Priority | Criteria | Examples |
|----------|----------|----------|
| 🔴 Critical | Revenue-affecting, user safety | payment, subscription |
| 🟠 High | Core functionality | handlers, auth |
| 🟡 Medium | Supporting services | utils, formatters |
| 🟢 Low | Nice to have | logging, analytics |

## Coverage Targets by Category

| Category | Target | Rationale |
|----------|--------|-----------|
| Services | 70% | Core business logic |
| Handlers | 70% | User-facing flows |
| Utils | 80% | Heavily reused, easy to test |
| Libs | 70% | External integrations |
