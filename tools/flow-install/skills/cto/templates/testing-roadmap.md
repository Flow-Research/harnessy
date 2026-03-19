# Testing Roadmap

**Last Updated:** {{ date }}
**Current Coverage:** {{ current_coverage }}% ({{ current_tests }} tests in {{ test_files }} files)
**Target Coverage:** {{ target_coverage }}% ({{ target_tests }} tests)
**Timeline:** {{ weeks }} weeks ({{ start_date }} - {{ end_date }})

---

## Current Status

### Coverage Summary
| Category | Files | Testable Now | With Mocking | Challenging | Current Coverage | Target |
|-----------|--------|--------------|--------------|-------------|-----------------|--------|
| Services | 36 | 12 | 18 | 6 | 4.8% | 70% |
| Handlers | 9 | 2 | 5 | 2 | 11% | 70% |
| Utils | 26 | 20 | 5 | 1 | 77% | 80% |
| Libs | 20 | 10 | 8 | 2 | 50% | 70% |

### Existing Tests ({{ existing_tests_count }} files)
- ✅ `ai-response.service.test.ts`
- ✅ `beacon.service.test.ts`
- ✅ `subscription-selection.service.test.ts`
- ✅ `list-reply.handler.test.ts`
- ✅ `reply-button.handler.test.ts`
- ✅ `qdrant.test.ts`
- ✅ `list-registry.test.ts`
- ✅ `admin.validation.test.ts`
- ✅ `invite-code.validation.test.ts`
- ✅ `countries.test.ts`
- ✅ `international-date.test.ts`
- [ ] [And {{ existing_tests_count - 11 }} more...]

---

## Weekly Plan

### Week 1: Foundation & Quick Wins
**Dates:** {{ week1_dates }}
**Goal:** Establish patterns and cover high-value business logic

| Day | Test File | Source File | Key Test Cases | Effort | Status |
|-----|-----------|-------------|----------------|--------|--------|
| 1 | `coupon.service.test.ts` | `src/service/coupon.service.ts` | Coupon validation, expiry, usage limits | 2h | ⬜ |
| 2 | `payment.service.test.ts` | `src/service/payment.service.ts` | Luhn validation, card expiry, screens | 3h | ⬜ |
| 3-4 | `subscription.service.test.ts` | `src/service/subscription.service.ts` | Activation, renewal, date calculations | 4h | ⬜ |
| 5 | `unified-tracking.service.test.ts` | `src/service/unified-tracking.service.ts` | Usage recording, quota enforcement | 3h | ⬜ |

**Week 1 Progress:** 0/4 complete (0%)
**Coverage Target:** +10 tests → ~25% coverage

---

### Week 2: Handler Coverage
**Dates:** {{ week2_dates }}
**Goal:** Cover message processing pipelines

| Day | Test File | Source File | Key Test Cases | Effort | Status |
|-----|-----------|-------------|----------------|--------|--------|
| 1-2 | `base.handler.test.ts` | `src/handlers/base.handler.ts` | Access control, usage calculation | 4h | ⬜ |
| 3 | `text.handler.test.ts` | `src/handlers/text.handler.ts` | Text processing, AI dispatch | 3h | ⬜ |
| 4 | `audio.handler.test.ts` | `src/handlers/audio.handler.ts` | Voice transcription, duration | 3h | ⬜ |
| 5 | `media.handler.test.ts` | `src/handlers/media.handler.ts` | Image/document handling | 2h | ⬜ |

**Week 2 Progress:** 0/4 complete (0%)
**Coverage Target:** +50 tests → ~35% coverage

---

### Week 3: External Integrations
**Dates:** {{ week3_dates }}
**Goal:** Cover payment providers and external APIs

| Day | Test File | Source File | Key Test Cases | Effort | Status |
|-----|-----------|-------------|----------------|--------|--------|
| 1-2 | `flutterwave.service.test.ts` | `src/service/flutterwave.service.ts` | Payment initiation, webhooks, status | 4h | ⬜ |
| 3 | `vendy.service.test.ts` | `src/service/vendy.service.ts` | Bank transfer, status checks | 3h | ⬜ |
| 4-5 | `wellahealth.service.test.ts` | `src/service/wellahealth.service.ts` | Drug ordering, fulfillment | 4h | ⬜ |

**Week 3 Progress:** 0/3 complete (0%)
**Coverage Target:** +40 tests → ~45% coverage

---

### Week 4: Flow Services
**Dates:** {{ week4_dates }}
**Goal:** Cover user journey flows

| Day | Test File | Source File | Key Test Cases | Effort | Status |
|-----|-----------|-------------|----------------|--------|--------|
| 1-2 | `onboardingFlow.service.test.ts` | `src/service/onboardingFlow.service.ts` | Registration, country detection, terms | 4h | ⬜ |
| 3 | `drugSelection.service.test.ts` | `src/service/drugSelection.service.ts` | Drug search, selection, prescriptions | 3h | ⬜ |
| 4 | `beaconFlow.service.test.ts` | `src/service/beaconFlow.service.ts` | Emergency flow, location handling | 3h | ⬜ |
| 5 | `fulfillment.service.test.ts` | `src/service/fulfillment.service.ts` | Order processing, delivery updates | 2h | ⬜ |

**Week 4 Progress:** 0/4 complete (0%)
**Coverage Target:** +50 tests → ~55% coverage

---

### Week 5: API Integration Tests
**Dates:** {{ week5_dates }}
**Goal:** Cover HTTP endpoints with Supertest

| Day | Test File | Source File | Key Test Cases | Effort | Status |
|-----|-----------|-------------|----------------|--------|--------|
| 1 | `admin-stats.controller.test.ts` | `src/routes/admin-api/stats.ts` | Analytics endpoints, date filtering | 2h | ⬜ |
| 2 | `subscription.routes.test.ts` | `src/routes/subscription/*` | Tier listing, activation, status | 3h | ⬜ |
| 3 | `webhook.routes.test.ts` | `src/routes/webhook/*` | WhatsApp webhooks, callbacks | 3h | ⬜ |
| 4 | `admin-users.controller.test.ts` | `src/routes/admin-api/users.ts` | User listing, search, management | 2h | ⬜ |
| 5 | `admin-broadcast.controller.test.ts` | `src/routes/admin-api/broadcast.ts` | Broadcast creation, scheduling | 2h | ⬜ |

**Week 5 Progress:** 0/5 complete (0%)
**Coverage Target:** +40 tests → ~65% coverage

---

### Week 6: Utilities & Edge Cases
**Dates:** {{ week6_dates }}
**Goal:** Cover remaining utilities and edge cases

| Day | Test File | Source File | Key Test Cases | Effort | Status |
|-----|-----------|-------------|----------------|--------|--------|
| 1 | `subscription-ui.util.test.ts` | `src/utils/subscription-ui.util.ts` | UI generation, button formatting | 2h | ⬜ |
| 2 | `message-formatter.test.ts` | `src/utils/message-formatter.ts` | Message templates, formatting | 2h | ⬜ |
| 3 | `helper.test.ts` | `src/libs/helper.ts` | Utility functions, error formatting | 2h | ⬜ |
| 4-5 | `task-scheduler.service.test.ts` | `src/service/task-scheduler.service.ts` | Scheduled jobs, cron execution | 4h | ⬜ |

**Week 6 Progress:** 0/4 complete (0%)
**Coverage Target:** +30 tests → ~70% coverage

---

## Cumulative Coverage Targets

| Week | New Tests | Cumulative Tests | Test Files | Coverage | Progress |
|------|-----------|-----------------|------------|-----------|-----------|
| 0 (Current) | 150 | 150 | 13 | 15% | 0% |
| 1 | +60 | 210 | 17 | 25% | ⬜⬜⬜⬜ |
| 2 | +50 | 260 | 21 | 35% | ⬜⬜⬜⬜ |
| 3 | +40 | 300 | 24 | 45% | ⬜⬜⬜⬜ |
| 4 | +50 | 350 | 28 | 55% | ⬜⬜⬜⬜ |
| 5 | +40 | 390 | 33 | 65% | ⬜⬜⬜⬜ |
| 6 | +30 | 420 | 37 | 70% | ⬜⬜⬜⬜ |

---

## Priority Matrix

| Priority | File | Business Impact | Effort | ROI | Status |
|----------|------|----------------|--------|-----|--------|
| 🔴 Critical | `subscription.service.ts` | Revenue, user access | 4h | ⭐⭐⭐⭐⭐ | Week 1 |
| 🔴 Critical | `payment.service.ts` | Payment processing | 3h | ⭐⭐⭐⭐⭐ | Week 1 |
| 🟠 High | `unified-tracking.service.ts` | Usage limits, quotas | 3h | ⭐⭐⭐⭐ | Week 1 |
| 🟠 High | `base.handler.ts` | All message processing | 4h | ⭐⭐⭐⭐ | Week 2 |
| 🟡 Medium | `flutterwave.service.ts` | Payment provider | 4h | ⭐⭐⭐ | Week 3 |
| 🟡 Medium | `onboardingFlow.service.ts` | User registration | 4h | ⭐⭐⭐ | Week 4 |
| 🟢 Low | `task-scheduler.service.ts` | Background jobs | 4h | ⭐⭐ | Week 6 |

---

## Blockers & Risks

### Current Blockers
- [ ] [Blocker 1] - Impact, Resolution plan, Expected resolution date
- [ ] [Blocker 2] - Impact, Resolution plan, Expected resolution date

### Risks
- [ ] [Risk 1] - Likelihood, Impact, Mitigation
- [ ] [Risk 2] - Likelihood, Impact, Mitigation

---

## Resources

### Team Allocation
- **Dedicated Tester:** 1 FTE
- **Reviewer:** @user (1-2 hour review turnaround)
- **Infrastructure:** Dev environment, test database

### Test Infrastructure
- **Jest:** ✅ Configured
- **Mocks:** ✅ Redis, MongoDB, OpenAI, Qdrant, Logger
- **Supertest:** ⬜ Need installation
- **Test Database:** ⬜ Need setup

---

## Dependencies

### External
- [ ] Install Supertest: `npm install --save-dev supertest @types/supertest`
- [ ] Set up test database (MongoDB, Redis)

### Internal
- [ ] Refactor `message-timeline.service.ts` (57KB) - Decompose for testability
- [ ] Resolve singleton testing patterns in service tests

---

## Notes
- Patterns discovered during testing
- Mocking challenges encountered
- Coverage gaps identified
- Timeline adjustments

---

## Related Documentation
- [./docs/TESTING_STRATEGY.md](./docs/TESTING_STRATEGY.md) - Detailed analysis
- [./tests/setup.ts](./tests/setup.ts) - Test infrastructure
