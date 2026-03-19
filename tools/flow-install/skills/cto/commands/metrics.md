---
description: Define business metrics and KPIs for executive dashboards
argument-hint: "Optional: specific metrics to track or current values"
---

# CTO Business Metrics

You are helping define business metrics and KPIs.

## User Input

$ARGUMENTS

## Context

- Current date: !`date +%Y-%m-%d`
- Current quarter: (Calculate from date: Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec)

### Existing Metrics
!`cat .notes/business-metrics.md 2>/dev/null || echo "No business-metrics.md yet"`

### Quarterly Plan Context
!`head -50 .notes/quarterly-plan.md 2>/dev/null || echo "No quarterly plan yet"`

## Your Task

### Step 1: Gather Information

Ask the user about:

**Revenue Metrics:**
- Current MRR (Monthly Recurring Revenue)
- Target MRR and timeline
- Revenue breakdown by tier
- Revenue by country/region

**User Metrics:**
- Total subscribers
- New subscribers this month
- Churn rate
- Conversion funnel metrics

**SaaS Health:**
- CAC (Customer Acquisition Cost)
- LTV (Lifetime Value)
- ARPU (Average Revenue Per User)
- Payback period

**Technical KPIs:**
- P95/P99 response times
- Error rates
- Uptime targets
- Test coverage

### Step 2: Generate Metrics Dashboard

Create `.notes/business-metrics.md`:

```markdown
# Business Metrics & KPIs

**Last Updated:** [date]
**Reporting Period:** [Q# Year]

---

## Executive Dashboard Summary

| Metric | Current | Target | Status | Trend |
|--------|---------|--------|--------|-------|
| MRR | ₦X | ₦Y | 🟢/🟡/🔴 | ↗️/↘️/→ |
| Active Subscribers | X | Y | 🟢/🟡/🔴 | ↗️/↘️/→ |
| Test Coverage | X% | 70% | 🟢/🟡/🔴 | ↗️/↘️/→ |
| Uptime | X% | 99.9% | 🟢/🟡/🔴 | → |

---

## 💰 Revenue Metrics

### Monthly Recurring Revenue (MRR)
- **Current:** ₦X
- **Target:** ₦Y (by [date])
- **Growth:** X% MoM

### Revenue by Tier
| Tier | Subscribers | MRR | Growth |
|------|-------------|-----|--------|
| Free | X | ₦0 | X% |
| Pro | X | ₦Y | X% |
| Premium | X | ₦Y | X% |

---

## 👥 User Metrics

### Subscriber Growth
- **Total Subscribers:** X
- **New This Month:** X
- **Churned This Month:** X
- **Net Growth:** X

### Retention & Churn
- **Retention Rate:** X% (target: 80%)
- **Churn Rate:** X% (target: <10%)

### Conversion Funnel
| Stage | Count | Conversion Rate |
|-------|-------|-----------------|
| New Users | X | - |
| Free Tier | X | X% |
| Pro Upgrade | X | X% |
| Premium Upgrade | X | X% |

---

## 🎯 SaaS Health Metrics

- **CAC:** ₦X (target: ₦Y)
- **LTV:** ₦X
- **LTV:CAC Ratio:** Xx (target: >3x)
- **ARPU:** ₦X
- **Payback Period:** X months (target: <12)

---

## ⚙️ Technical KPIs

### Performance
| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| P95 Response Time | <500ms | Xms | 🟢/🟡/🔴 |
| API Error Rate | <0.1% | X% | 🟢/🟡/🔴 |
| AI Response Time | <3s | Xs | 🟢/🟡/🔴 |

### Quality
| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Test Coverage | 70% | X% | 🟢/🟡/🔴 |
| Critical Bugs | 0 | X | 🟢/🟡/🔴 |
| Uptime | 99.9% | X% | 🟢/🟡/🔴 |

---

## 📊 Monitoring Implementation

### Prometheus Metrics Needed
- [ ] `project_revenue_total` - Revenue counter
- [ ] `project_subscriptions_total` - Subscription counter by tier
- [ ] `project_users_active` - Active users gauge
- [ ] `project_churn_total` - Churn counter

### Grafana Dashboards Needed
- [ ] Executive Dashboard
- [ ] SaaS Health Dashboard
- [ ] Conversion Funnel Dashboard

---

## 🎯 Quarterly Goals

- [ ] Reach ₦X MRR
- [ ] Reach X active subscribers
- [ ] Achieve 70% test coverage
- [ ] Reduce churn to <10%
```

## Status Thresholds

| Status | Meaning |
|--------|---------|
| 🟢 | On track (≥90% of target) |
| 🟡 | At risk (70-89% of target) |
| 🔴 | Off track (<70% of target) |

## Trend Indicators

| Trend | Meaning |
|-------|---------|
| ↗️ | Improving |
| → | Stable |
| ↘️ | Declining |
