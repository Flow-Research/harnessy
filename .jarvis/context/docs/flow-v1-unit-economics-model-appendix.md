# Flow V1 Unit Economics Model Appendix

Date: 2026-03-12
Status: Working appendix
Scope: V1 economics for Flow as a managed human+AI work platform

## Purpose

This appendix translates the Flow system into a v1 unit economics model that can be tested before launch.

The goal is not to predict exact outcomes yet. The goal is to define the variables, formulas, thresholds, and stress cases needed to determine whether the first version of Flow is economically viable.

## Core Principle

V1 must be modeled as a narrow, managed work platform with AI assistance.

Do not model v1 as:

- a full token economy
- a generalized decentralized marketplace
- a fully autonomous operator economy
- a protocol-first network

Model it as:

- one narrow task category
- one primary buyer segment
- one payout corridor
- one managed quality process
- one simple value split

## V1 Revenue Identity

Before modeling, choose one primary v1 revenue identity:

### Option A - Buyer-Funded Managed Work

Businesses pay Flow directly for completed work.

This is the recommended default for v1 because it is easiest to explain, easiest to price, and easiest to measure.

### Option B - Reward-Harvesting / Miner-Led Distribution

Flow earns from external reward systems such as Bittensor and distributes downstream earnings.

This can be a backend bootstrap, but should not be the primary public unit economics story for v1.

### Option C - Hybrid

Buyer-funded work plus external reward capture.

This is viable only if reporting clearly separates the two, otherwise margin quality will be obscured.

## Recommended V1 Modeling Assumption

Use this default for the first model:

- primary revenue: buyer-funded managed work
- Bittensor/reward flows: optional upside or bootstrap supply, modeled separately
- user payout promise: fiat-equivalent or stable local-currency payout
- Flow take: explicit spread after quality and operations costs

## Core Unit Definition

The primary unit should be:

- `one accepted task output`

Not:

- one registered user
- one operator session
- one subnet reward event

The business only works if one accepted output is contribution-margin positive.

## Per-Task Value Flow

For each accepted task output, model:

- buyer price
- worker gross payout
- operator compute cost
- review / QA cost
- orchestration cost
- support cost
- payout and FX cost
- fraud / dispute loss allocation
- platform retained contribution margin

Formula:

```text
Contribution Margin per Accepted Task
= Buyer Price
- Worker Payout
- Compute Cost
- Review Cost
- Orchestration Cost
- Support Cost
- Payout/FX Cost
- Fraud and Dispute Loss Allocation
```

## Per-Task Variable Definitions

### Revenue

- `BP` = buyer price per accepted task

### Direct Worker Cost

- `WP` = worker payout for the task

### Operator / Compute Costs

- `CC` = compute cost from personal operator usage, sandboxes, inference, storage, and related runtime costs

### Quality Costs

- `QC` = review, QA, correction, aggregation, editor, or supervisor cost

### Coordination Costs

- `OC` = orchestration and routing cost, including task decomposition and dispatch overhead

### Support Costs

- `SC` = user support, clarification, onboarding assistance, payout support, and intervention overhead allocated per task

### Payout Costs

- `PC` = payout rail fees, FX spread, treasury conversion spread, and settlement cost allocated per task

### Loss Costs

- `LC` = expected loss allocation from fraud, disputes, rejected work, chargebacks, reward reversals, or idle commitments

### Contribution Margin

- `CM` = BP - WP - CC - QC - OC - SC - PC - LC

## Secondary Unit Definitions

V1 also needs supporting unit economics at the cohort level.

### Worker Cohort Unit

- one newly activated worker over 30 days

Track:

- activation rate
- time to first task
- time to first payout
- task acceptance rate
- completion rate
- retention
- gross payouts earned
- support cost incurred
- review burden generated

### Buyer Cohort Unit

- one newly activated buyer over 90 days

Track:

- number of tasks posted
- average buyer spend
- repeat rate
- defect / revision rate
- time to second purchase
- gross margin generated

## Minimum Viable Task Economics

Each launch task type should satisfy all of the following:

- clear scope and acceptance criteria
- low ambiguity
- measurable quality output
- short turnaround time
- low dispute likelihood
- meaningful buyer willingness to pay
- limited review burden relative to payout
- capability for progressive worker learning

If a task type fails any of these, it is a weak v1 candidate.

## Worker Economics Model

### Effective Hourly Earnings

Workers will judge the platform by effective earnings, not gross task payouts.

Formula:

```text
Effective Hourly Earnings
= (Total Worker Payouts - Worker-Side Friction Costs)
/ Total Time Spent
```

Where total time spent includes:

- task execution time
- waiting and clarification time
- rework time
- unpaid rejected time

### Worker-Side Friction Costs

Track explicitly:

- internet/data cost
- cash-out fees
- FX slippage if relevant
- time lost to unresolved disputes

### Worker Sustainability Thresholds

Set explicit thresholds for v1:

- target time to first payout
- minimum acceptable effective hourly earnings
- minimum weekly payout reliability
- target graduation rate into higher-value task bands

## Operator Economics Model

The operator must prove economic usefulness.

### Operator Value Test

Compare three cases:

- human only
- human + operator
- operator-heavy execution

Measure difference in:

- completion speed
- accepted output rate
- revision rate
- support demand
- compute spend
- buyer satisfaction

### Operator ROI Formula

```text
Operator ROI per Task
= Incremental Value Created by Operator Assistance
- Incremental Compute and Coordination Cost
```

If the operator does not improve accepted-margin economics, it should be simplified or partially hidden in v1.

## Platform Economics Model

### Contribution Margin

This is the most important v1 metric.

```text
CM = BP - WP - CC - QC - OC - SC - PC - LC
```

### Gross Margin at Cohort Level

```text
Gross Margin per Buyer Cohort
= Sum of Contribution Margin Across Buyer Tasks
```

### CAC Payback

Track separately for:

- worker acquisition
- buyer acquisition

```text
Buyer CAC Payback Period
= Buyer Acquisition Cost / Monthly Contribution Margin per Buyer
```

Worker acquisition cost should not be justified unless workers activate into real demand within a short period.

## Review / QA Economics Model

Review is a hidden economic driver and must be modeled directly.

### Review Cost per Accepted Task

```text
QC = Reviewer Time Cost + Correction Cost + Escalation Cost
```

### Review Burden Ratio

```text
Review Burden Ratio = QC / BP
```

If review burden becomes too large relative to buyer price, the task category is not viable for v1.

## Payout and Treasury Model

If Flow promises fast payouts, Flow may need to absorb timing and volatility mismatches.

### Payout Timing Gap

```text
Payout Timing Gap = Time User Is Paid - Time Flow Securely Realizes Revenue
```

If this gap is negative for Flow, treasury capital is required.

### Treasury Exposure

Track:

- days of payout float
- reward volatility exposure
- FX spread exposure
- settlement failure exposure
- dispute reserve requirements

### Reserve Coverage

```text
Reserve Coverage Ratio
= Available Liquid Reserve / Expected Short-Term Payout and Dispute Obligations
```

## Apprenticeship Economics Model

The apprenticeship system cannot be judged only by mission value. It must pay back economically.

### Progression Cost

Track:

- onboarding cost per worker
- support cost before first profitable output
- review cost during low-tier work
- compute assistance cost during learning phase

### Progression Value

Track:

- increase in buyer billable task complexity
- increase in worker throughput
- increase in acceptance rate
- increase in repeat buyer satisfaction

### Progression ROI

```text
Progression ROI
= Lifetime Contribution Margin After Graduation
- Total Pre-Graduation Cost
```

If too few workers graduate, the apprenticeship loop becomes a permanent subsidy.

## Idle Capacity Model

This is one of the most important hidden risks.

### Supply Utilization

```text
Supply Utilization Rate
= Paid Productive Worker Hours / Available Active Worker Hours
```

### Idle Cost

Idle cost includes:

- support burden from inactive workers
- expectation management
- operator maintenance if any persistent costs exist
- churn from workers who expected work but found none

The system should avoid scaling worker supply faster than proven task demand.

## Loss Waterfall Model

For every failure type, define who bears the loss.

Examples:

- rejected task output
- buyer dispute
- operator over-spend
- payout reversal
- reward drawdown
- fraud event

Recommended rule for v1:

- do not leave loss allocation implicit
- map each failure type to a single primary loss bearer and one reserve mechanism

## Scenario Model

Each v1 economics sheet should include at least three scenarios.

### Base Case

- expected buyer pricing
- expected review burden
- stable payout corridor
- modest worker progression

### Downside Case

- 20-30% higher review cost
- slower worker progression
- payout delays
- lower buyer repeat rate

### Stress Case

- major reward or liquidity disruption
- 50%+ increase in disputes or revisions
- significant drop in buyer demand
- external dependency shock from Bittensor or payout rails

If the system breaks immediately under the downside case, it is too fragile for launch.

## Required V1 Dashboards

The first operating dashboard should include:

- accepted tasks
- buyer revenue
- worker payouts
- contribution margin
- average review cost per task
- support cost per task
- payout cost per task
- worker effective hourly earnings
- buyer repeat rate
- worker retention
- graduation rate
- treasury reserve coverage

## Recommended Decision Gates

Do not scale v1 until these gates are met for one narrow task category:

- positive contribution margin on accepted tasks
- acceptable worker effective hourly earnings
- repeat buyer rate is strong enough to support acquisition spend
- review burden is stable and decreasing
- payouts are reliable without treasury stress
- operators show measurable productivity lift or are simplified

## Core Questions This Appendix Should Answer

- What is the minimum profitable task type for Flow?
- What buyer price range supports positive contribution margin?
- What worker payout range is attractive enough to retain supply?
- Does operator assistance improve or reduce per-task economics?
- How much working capital is needed to smooth payouts?
- What graduation rate is required for apprenticeship economics to work?
- How sensitive is the model to review cost and payout volatility?

## Recommended First Spreadsheet Tabs

- `Assumptions`
- `Task Unit Economics`
- `Worker Cohort Economics`
- `Buyer Cohort Economics`
- `Operator ROI`
- `Review and QA Costs`
- `Treasury and Payout Float`
- `Progression Economics`
- `Scenario Analysis`
- `Decision Dashboard`

## Bottom Line

V1 is economically coherent only if all of the following are true at once:

- one task category has positive contribution margin
- workers experience trustworthy and worthwhile earnings
- buyers receive reliably better outcomes than alternatives
- operators add more value than they cost
- payout smoothing does not break treasury health
- apprenticeship produces future margin rather than permanent subsidy

If any one of these fails, the system may still look active, but it will not yet be economically sound.
