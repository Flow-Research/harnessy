# Quarterly Plan - Q{{ quarter }} {{ year }}

**Last Updated:** {{ date }}
**Status:** In Progress
**Review Date:** {{ review_date }}

---

## Executive Summary

This quarter focuses on:
1. **[Focus Area 1]** - [Brief description]
2. **[Focus Area 2]** - [Brief description]
3. **[Focus Area 3]** - [Brief description]

**Key Metrics:**
- Target MRR: ₦{{ target_mrr }}
- Target Subscribers: {{ target_subs }}
- Target Test Coverage: {{ target_coverage }}%

---

## 🎯 Strategic Goals

### Goal 1: [Title]
**Success Criteria:**
- [ ] Criteria 1
- [ ] Criteria 2
- [ ] Criteria 3

**Impact:** [Describe business/technical impact]
**Priority:** Critical/High/Medium/Low
**Timeline:** {{ start_date }} - {{ end_date }}
**Owner:** @user

---

### Goal 2: [Title]
...

### Goal 3: [Title]
...

---

## 📋 Initiatives

### Initiative 1: MCP Integration for AI Agent Decoupling
**Status:** 🟢 On Track / 🟡 At Risk / 🔴 Blocked
**Progress:** {{ progress }}%

**Milestones:**
- [x] Phase 1: PoC with 2-3 tools (1-2 days) - Completed YYYY-MM-DD
- [ ] Phase 2: Full tool migration (3-5 days) - Due YYYY-MM-DD
- [ ] Phase 3: Production deployment (1-2 days) - Due YYYY-MM-DD

**Owner:** @user
**Dependencies:**
- [ ] Code review approved
- [ ] Infrastructure team provisioning MCP servers

**Risks:**
- Learning curve for MCP SDK
- Integration testing complexity

**Mitigation:**
- Pair programming for MCP learning
- Dedicated testing environment

---

### Initiative 2: Test Coverage Improvement (4.8% → 70%)
**Status:** 🟡 At Risk
**Progress:** {{ progress }}% (Week {{ current_week }}/6)

**Milestones:**
- [x] Week 1: Foundation tests (4 files) - Completed
- [ ] Week 2: Handler tests (4 files) - Due {{ week2_date }}
- [ ] Week 3: External integrations (3 files) - Due {{ week3_date }}
- [ ] Week 4: Flow services (4 files) - Due {{ week4_date }}
- [ ] Week 5: API integration tests (5 files) - Due {{ week5_date }}
- [ ] Week 6: Utilities (4 files) - Due {{ week6_date }}

**Owner:** @user
**Dependencies:**
- [ ] Dedicated tester allocation
- [ ] Supertest installation

**Risks:**
- Developer time constraints
- Blocking issues in complex services

**Mitigation:**
- Prioritize critical paths first
- Reduce scope if needed

---

### Initiative 3: Business Metrics Implementation
**Status:** 🟢 On Track
**Progress:** {{ progress }}%

**Milestones:**
- [ ] Define KPIs and tracking strategy - Due {{ date }}
- [ ] Implement Prometheus metrics - Due {{ date }}
- [ ] Build Grafana dashboards - Due {{ date }}
- [ ] Configure alerts - Due {{ date }}

**Owner:** @user

---

## 📊 Key Performance Indicators

### Business KPIs
| Metric | Q{{ quarter-1 }} Actual | Q{{ quarter }} Target | Q{{ quarter }} Forecast | Status |
|--------|---------------------|-------------------|-------------------|--------|
| MRR | ₦{{ q_prev_mrr }} | ₦{{ target_mrr }} | ₦{{ forecast_mrr }} | 🟢/🟡/🔴 |
| Subscribers | {{ q_prev_subs }} | {{ target_subs }} | {{ forecast_subs }} | 🟢/🟡/🔴 |
| Retention Rate | {{ q_prev_retention }}% | {{ target_retention }}% | {{ forecast_retention }}% | 🟢/🟡/🔴 |
| Churn Rate | {{ q_prev_churn }}% | {{ target_churn }}% | {{ forecast_churn }}% | 🟢/🟡/🔴 |

### Technical KPIs
| Metric | Q{{ quarter-1 }} Actual | Q{{ quarter }} Target | Q{{ quarter }} Forecast | Status |
|--------|---------------------|-------------------|-------------------|--------|
| Test Coverage | {{ q_prev_coverage }}% | {{ target_coverage }}% | {{ forecast_coverage }}% | 🟢/🟡/🔴 |
| P95 Latency | {{ q_prev_p95 }}ms | <500ms | {{ forecast_p95 }}ms | 🟢/🟡/🔴 |
| Uptime | {{ q_prev_uptime }}% | 99.9% | {{ forecast_uptime }}% | 🟢/🟡/🔴 |
| Technical Debt Resolved | {{ q_prev_debt }} | 10 | {{ forecast_debt }} | 🟢/🟡/🔴 |

---

## 🗓️ Monthly Breakdown

### Month {{ month_1 }} 2026
**Focus:** [Key focus area]

**Key Deliverables:**
- [ ] Deliverable 1 - Due Date - Owner
- [ ] Deliverable 2 - Due Date - Owner

**Target Metrics:**
- MRR: ₦{{ m1_target }}
- Subscribers: {{ m1_subs }}

**Notes:**
- Any notable events or changes

---

### Month {{ month_2 }} 2026
**Focus:** [Key focus area]

**Key Deliverables:**
- [ ] Deliverable 1 - Due Date - Owner
- [ ] Deliverable 2 - Due Date - Owner

**Target Metrics:**
- MRR: ₦{{ m2_target }}
- Subscribers: {{ m2_subs }}

**Notes:**

---

### Month {{ month_3 }} 2026
**Focus:** [Key focus area]

**Key Deliverables:**
- [ ] Deliverable 1 - Due Date - Owner
- [ ] Deliverable 2 - Due Date - Owner

**Target Metrics:**
- MRR: ₦{{ m3_target }}
- Subscribers: {{ m3_subs }}

**Notes:**

---

## 🚨 Risks & Mitigation

### Risk 1: [Title]
**Likelihood:** High/Medium/Low
**Impact:** Critical/High/Medium/Low
**Description:** [Describe risk]

**Mitigation:**
- Strategy 1
- Strategy 2

**Owner:** @user
**Review Date:** {{ date }}

---

## 💰 Budget & Resources

### Engineering Hours Allocation
| Initiative | Estimated Hours | Q{{ quarter }} Allocation | Remaining |
|------------|-----------------|---------------------|-----------|
| MCP Integration | 40h | 0h / 40h | 40h |
| Test Coverage | 120h | 0h / 120h | 120h |
| Business Metrics | 40h | 0h / 40h | 40h |
| Technical Debt | 80h | 0h / 80h | 80h |
| **Total** | **280h** | **0h / 280h** | **280h** |

### Team Capacity
- **Engineers:** X FTE
- **Available Hours:** X hours/quarter
- **Capacity Utilization:** X% (280h / Xh)

---

## 🎉 Wins & Learnings

### This Quarter's Wins
- [ ] [Win 1] - Impact: [Description]
- [ ] [Win 2] - Impact: [Description]

### Key Learnings
- [ ] Learning 1: [What worked well]
- [ ] Learning 2: [What didn't work]
- [ ] Learning 3: [What to change]

---

## 📋 Next Quarter Planning

### Carryover Initiatives
- [ ] [Initiative 1] - Why it's carrying over
- [ ] [Initiative 2] - Why it's carrying over

### New Initiatives for Q{{ quarter+1 }}
- [ ] [Initiative 1] - Rationale
- [ ] [Initiative 2] - Rationale

---

## Notes
- Any context for future reference
- Major announcements or changes
- Strategic shifts

---

## Related Documents
- [.notes/priorities.md](./priorities.md) - Detailed priorities
- [.notes/technical-debt.md](./technical-debt.md) - Debt tracker
- [.notes/architecture-decisions.md](./architecture-decisions.md) - ADRs
- [./docs/CHANGELOG.md](./docs/CHANGELOG.md) - Implementation history
