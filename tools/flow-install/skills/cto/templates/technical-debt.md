# Technical Debt Tracker

**Last Updated:** {{ date }}
**Total Debt Items:** {{ total }}
**Resolved This Quarter:** {{ resolved }}
**New This Quarter:** {{ new }}

## Summary
- **Critical Debt:** {{ critical_count }}
- **High Debt:** {{ high_count }}
- **Medium Debt:** {{ medium_count }}
- **Low Debt:** {{ low_count }}

---

## 🔴 Critical Debt (Immediate Action Required)

| ID | File | Description | Impact | Effort | ROI | Priority | Status | Owner | Due Date |
|----|------|-------------|--------|--------|-----|----------|--------|----------|----------|
| TD-001 | example.service.ts | Description | High/Low | Small/Medium/Large | High/Med/Low | P0 | In Progress | @user | YYYY-MM-DD |

---

## 🟠 High Debt (This Quarter)

---

## 🟡 Medium Debt (Next Quarter)

---

## 🟢 Low Debt (Backlog)

---

## Debt Reduction Progress

**Target:** 10 items resolved this quarter
**Current:** {{ resolved_count }}/{{ target }}
**Completion:** {{ completion_percentage }}%

### Recent Completions
- [x] TD-XXX: [Title] - Resolved on YYYY-MM-DD by @user
- [x] TD-XXX: [Title] - Resolved on YYYY-MM-DD by @user

## ROI Formula
```
ROI = (Impact Score ÷ Effort Score) × 10

Impact Scores:
  Critical = 10  (affects core revenue, user safety, data privacy)
  High      = 7   (affects performance, user experience)
  Medium    = 4   (technical quality, maintainability)
  Low       = 2   (nice to have, optimization)

Effort Scores:
  Small     = 1   (1-3 hours)
  Medium     = 3   (4-8 hours)
  Large      = 7   (1-3 days)
  XLarge     = 10  (1+ weeks)
```

## Notes
- Any patterns emerging in debt
- Systemic issues requiring architectural changes
- Dependencies between debt items
