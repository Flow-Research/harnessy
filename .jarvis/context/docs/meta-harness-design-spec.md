# Meta-Harness Design Specification
## A Conservative, Evidence-Driven Evolution of Harnessy

> This specification replaces the earlier expansive draft with a narrower and more operationally realistic design.
> 
> The goal is not to build a fully autonomous optimization layer immediately. The goal is to build a trustworthy observability and recommendation system that can support future optimization work without destabilizing the existing harness.
>
> Status note: this document is now a revision-oriented design spec, not a greenfield build spec. Phase 1 descriptive attribution has already been implemented in the shared harness tooling. The remaining value of this document is to define what should be validated next and what should remain deferred.

---

## 1. Executive Summary

Harnessy already has a useful self-improvement loop: traces are captured, quality is scored by the ratchet, and `skill-improve` proposes targeted edits to mutable skill artifacts. That loop should remain the center of gravity. The meta-harness initiative adds a layer around that loop, but only in a controlled order:

1. **Make improvement effects more legible** via descriptive attribution and per-component performance tracking.
2. **Validate whether those analytics are actually useful** before allowing them to drive anything important.
3. **Surface reusable lessons and cross-skill suggestions as advisory inputs** to humans and to `skill-improve`.
4. **Defer autonomous proactive optimization** until stronger evidence, better external quality signals, and safer workload controls exist.

The previous version of this spec treated attribution, transfer, proactive optimization, and meta-evaluation as a near-linear build program. That was too aggressive. The revised design makes four important changes:

- **Attribution is descriptive first, not causal.** It explains observed score movement and local evidence. It does not claim to identify the true cause of improvement.
- **Validation gates sit between phases.** New subsystems do not advance merely because code exists. They advance only if the output is stable, useful, and empirically aligned with downstream quality.
- **Advanced optimization remains advisory until the data is ready.** Lessons, transfer, and meta-evaluation produce recommendations before they produce automated mutations.
- **Live A/B testing and proactive optimization are explicitly deferred.** These remain research tracks until instrumentation, assignment fairness, and external quality signals are strong enough.

In repository reality, the descriptive-attribution MVP is no longer hypothetical. `attribute.py` and `attribute_validate.py` already implement the first safe slice of this design. That changes the near-term question from "what should we build first" to "is the current attribution output decision-useful enough to justify the next phase." This document should therefore be read as a sequencing and governance spec for the next increments, not as a request to rebuild Phase 1.

---

## 2. Design Goals

### 2.1 Primary Goals

1. Improve visibility into which parts of a skill appear to help or hurt quality outcomes.
2. Improve proposal ranking for `skill-improve` using historical evidence instead of only raw trace counts.
3. Capture lessons that survive across sessions and projects without pretending those lessons are universally valid.
4. Preserve the integrity of the existing ratchet and trace pipeline.
5. Reduce the chance that the harness optimizes its own proxy metrics while drifting away from actual output quality.

### 2.2 Non-Goals

This design does **not** aim to do the following in its initial implementation:

1. Prove causal attribution from sparse run data.
2. Autonomously rewrite `ratchet.py`, `program.md`, or the fixed evaluation layer.
3. Run live multi-variant testing on heterogeneous workloads as a default operating mode.
4. Autonomously loosen gate criteria based on ratchet deltas.
5. Autonomously propagate patterns across the skill portfolio.
6. Treat small score deltas over tiny windows as robust evidence.

### 2.3 Success Criteria

The revised meta-harness is successful if:

1. Humans can identify bottleneck components and recent high-signal changes more easily than today.
2. `skill-improve` proposal quality improves measurably without increasing regressions.
3. Lessons and cross-skill suggestions reduce redundant rediscovery without increasing bad transfers.
4. The system remains understandable and debuggable by humans.
5. No change to the meta-harness undermines the Three-File Contract or silently alters evaluation truth.

---

## 3. Current State

### 3.1 What Exists Today

Harnessy already has the foundation needed for a conservative meta-harness:

**Fixed evaluation layer**

| File | Role |
|------|------|
| `tools/flow-install/skills/_shared/ratchet.py` | Computes composite score, hard gates, and keep/revert decisions |
| `tools/flow-install/skills/_shared/trace_capture.py` | Records structured gate traces |
| `tools/flow-install/skills/_shared/trace_query.py` | Loads and summarizes trace histories |
| `tools/flow-install/skills/_shared/run_metrics.py` | Aggregates run-level quality metrics |
| `tools/flow-install/skills/_shared/promote_check.py` | Checks whether proven installed changes have been promoted |

**Current analysis layer**

| File | Role |
|------|------|
| `tools/flow-install/skills/_shared/attribute.py` | Computes descriptive attribution records and regenerates the component index |
| `tools/flow-install/skills/_shared/attribute_validate.py` | Produces validation summaries for attribution maturity and usefulness review |

**Mutable improvement layer**

| File | Role |
|------|------|
| `tools/flow-install/skills/skill-improve/SKILL.md` | Reads traces and proposes edits to mutable skill artifacts |
| Skill `SKILL.md`, `commands/*.md`, and templates | The editable surface area of behavior |

**Orchestration and human control**

| File | Role |
|------|------|
| `tools/flow-install/skills/autoflow/commands/autoflow.md` | Session orchestrator and improvement trigger logic |
| `tools/flow-install/skills/_shared/autoresearch.md` | Defines the Three-File Contract |
| `program.md` | Human-authored config, thresholds, and control surface |

### 3.2 What Is Missing

The current system can answer:

- Which gates fail often
- Which skills need improvement
- Whether a candidate skill version beat its baseline under ratchet rules
- Which changed components were associated with observed local score movement after accepted improvements
- Which components appear repeatedly in local attribution summaries

It cannot yet answer well:

- Whether the current component attribution output is actually useful in real proposal review or mutation decisions
- Which **change type** has historically helped in that component strongly enough to support lessons promotion
- Which patterns seem reusable across skills
- Whether the ratchet score is aligned with downstream quality rather than just local gate success

That is the remaining gap this design addresses.

---

## 4. Feasibility Assessment

### 4.1 What Is Feasible Now

The following are feasible with the existing data model and operational footprint:

1. Descriptive, per-component attribution based on before/after deltas.
2. Per-component indexes showing frequency, associated improvement types, and local trend information.
3. Read-only lessons distillation from repeated evidence.
4. Advisory cross-skill suggestions surfaced to humans and to `skill-improve`.
5. Reporting-only meta-evaluation once enough history exists.

### 4.2 What Is Not Yet Feasible as Production Automation

The following should be treated as deferred or research-only:

1. Strong causal attribution from small evaluation windows.
2. Live A/B testing across naturally heterogeneous workloads.
3. Autonomous proactive optimization of already-working skills.
4. Reliable statistical tuning of ratchet exponents before downstream outcome data is instrumented.

### 4.3 Current Workspace Priority Reality

The workspace is currently centered on the Flow Platform POC and agent runtime work. This matters because a meta-harness program competes for the same implementation bandwidth. The design therefore favors:

1. low-risk additions,
2. strong standalone value,
3. minimal intrusion into the ratchet core, and
4. clear stop points after each phase.

---

## 5. Core Principles

### 5.1 Preserve the Three-File Contract

The fixed evaluation layer remains the source of scoring and gate truth. The meta-harness may read from it and produce reports around it, but it does not self-modify the evaluator.

### 5.2 Prefer Descriptive Evidence Over False Precision

If the system cannot support a causal claim, it should not pretend to. A weaker but honest description is better than a strong but misleading attribution number.

### 5.3 Separate Observation, Recommendation, and Mutation

These are distinct stages:

1. **Observation**: record, aggregate, and summarize
2. **Recommendation**: generate ranked suggestions with evidence
3. **Mutation**: edit skills or config

The design advances from one stage to the next only after validation.

### 5.4 Keep Humans in High-Blast Decisions

Changes to scoring, thresholds, gate removal, and broad transfer behavior require human review. The system may propose them; it may not auto-apply them.

### 5.5 Optimize for Legibility

Every new artifact should be readable and auditable by a human. If a report cannot be explained clearly, it should not drive automated behavior.

---

## 6. Architecture Overview

The revised meta-harness has four layers:

1. **Observability layer**
   Reads ratchet state, trace history, and improvement history.
2. **Analysis layer**
   Produces attribution records, component indexes, and validation summaries.
3. **Recommendation layer**
   Produces lessons, cross-skill suggestions, and meta-evaluation reports.
4. **Mutation layer**
   Remains the existing `skill-improve` flow, with richer inputs but unchanged authority boundaries.

### 6.1 Data Flow

```
traces.ndjson + runs.ndjson + improvements.ndjson + ratchet state
    -> attribution analysis
    -> component index
    -> validation summaries
    -> lessons and cross-skill recommendation inputs
    -> surfaced to humans and skill-improve
```

### 6.2 New Artifacts

| Artifact | Purpose | Mutability |
|---------|---------|------------|
| `attributions.ndjson` | Records descriptive before/after component evidence | append-only |
| `component_index.json` | Summarizes component health and local evidence | regenerated |
| `lessons.ndjson` | Stores advisory lessons with confidence tiers | append/update with validation metadata |
| `cross_skill_recommendations.ndjson` | Stores advisory transfer candidates | append-only |
| `meta_eval_reports/*.json` | Stores advisory evaluation reports | immutable report files |
| `validation_summary.json` | Tracks whether a phase is mature enough to enable the next one | regenerated |

---

## 7. Phase 0: Prerequisites and Instrumentation

Before the meta-harness is allowed to influence behavior, the following must be explicit.

### 7.1 Outcome Signals

The system needs better downstream quality signals than ratchet score alone.

Minimum required outcome catalog:

1. local gate success and refinement burden
2. human escalation rate
3. downstream regression or reopen signals where available
4. optional external quality review samples

### 7.2 External Quality Sampling

The system should support a small, periodic external quality sample that is **not** the same as gate success. This can be lightweight, but it must exist before advanced optimization is trusted.

Suggested field:

```json
{
  "external_quality": {
    "sampled": true,
    "reviewer": "human",
    "score_1_to_5": 4,
    "notes": "Passed gates, but missed one edge case in rollback narrative"
  }
}
```

This signal is optional in early phases, but mandatory before proactive optimization is considered.

### 7.3 Version and Lineage Discipline

Every recommendation and attribution record must clearly link:

1. source skill version
2. target skill version
3. improvement record IDs
4. ratchet decision window
5. evidence window boundaries

Without clean lineage, the system becomes impossible to audit.

---

## 8. Phase 1: Descriptive Attribution MVP

### 8.1 Objective

Build a read-only analysis layer that describes observed score movement at the component level and helps humans see which parts of a skill are bottlenecks.

### 8.2 Explicit Constraint

Phase 1 attribution is **descriptive, not causal**.

Approved claims in this phase:

- "This component changed before an observed improvement"
- "This gate improved after a change touching this section"
- "This improvement type has historically correlated with positive outcomes here"

Forbidden claims in this phase:

- "This component caused the improvement"
- "This pattern is universally good"
- "This change should be auto-applied elsewhere"

### 8.3 Component Definition

A component is any versionable, human-legible unit likely to influence behavior:

1. SKILL phase blocks
2. command files
3. template blocks
4. gate criteria blocks

Script-level attribution is deferred until the text-level component model is stable.

### 8.4 Minimal Algorithm

The MVP algorithm should be intentionally conservative.

Inputs:

1. ratchet state
2. recent improvement record
3. traces before snapshot
4. traces in the candidate evaluation window

Outputs:

1. touched components
2. touched gates/phases
3. before/after deltas for those gates/phases
4. uncertainty flags
5. residual/interaction notes

### 8.5 Required Uncertainty Labels

Each attribution record must carry one of:

- `descriptive_low_confidence`
- `descriptive_medium_confidence`
- `validated_local`

Promotion to `validated_local` requires stronger evidence than a single ratchet cycle.

### 8.6 Suggested Confidence Rules

These are intentionally simple:

| Tier | Minimum Evidence |
|------|------------------|
| `descriptive_low_confidence` | Single improvement cycle, small sample, or batched changes |
| `descriptive_medium_confidence` | Repeated local pattern over multiple non-identical cycles |
| `validated_local` | Repeated local pattern plus consistent downstream or external quality support |

### 8.7 Data Model

```json
{
  "attribution_id": "attr_20260401_001",
  "timestamp": "2026-04-01T15:30:00Z",
  "skill": "issue-flow",
  "improvement_id": "imp_20260401_001",
  "evidence_window": {
    "snapshot_tag": "ratchet/issue-flow/20260401-143000",
    "runs_analyzed": 5,
    "traces_analyzed": 14
  },
  "touched_components": [
    {
      "component_key": "SKILL.md::Phase 3 - Implementation",
      "change_type": "added_constraint",
      "associated_gates": ["implementation-review", "code-quality"],
      "observed_deltas": {
        "first_pass_rate_delta": 0.08,
        "avg_refinement_loops_delta": -0.3
      },
      "confidence": "descriptive_medium_confidence",
      "notes": "Observed improvement after change; causality not established"
    }
  ],
  "residual_notes": "Other concurrent factors may have influenced outcomes",
  "status": "descriptive"
}
```

### 8.8 Component Index

The component index is the main operator-facing artifact.

It should answer:

1. Which components are touched often?
2. Which components are repeatedly associated with poor gate outcomes?
3. Which improvement types have historically looked helpful there?
4. How strong is the evidence?

### 8.9 What Phase 1 Must Not Do

Phase 1 outputs must **not** yet:

1. reorder proposals automatically without a human-visible rationale
2. create active lessons
3. trigger cross-skill transfer
4. trigger proactive optimization

---

## 9. Phase 1.5: Validation Gate

This is the missing stage from the earlier spec. It exists to prevent noisy analytics from becoming automation prematurely.

### 9.1 Objective

Check whether attribution output is stable, legible, and decision-useful.

### 9.2 Validation Questions

1. Do repeated runs identify similar bottleneck components?
2. Do humans find the component index useful in actual review or mutation decisions?
3. Do the strongest local patterns align with downstream or external quality signals?
4. Are uncertainty labels appropriately conservative?

### 9.3 Exit Criteria

Phase 2 is only allowed if:

1. attribution output has been generated across enough real cycles to show repeated structure
2. humans report it is useful for proposal review
3. there is no evidence that the analysis layer is systematically pointing in the wrong direction

If those criteria are not met, the correct response is to improve observability, not to continue building the stack upward.

---

## 10. Phase 2: Advisory Lessons Registry

### 10.1 Objective

Persist reusable lessons from repeated evidence while keeping them clearly advisory.

### 10.2 Design Change from the Earlier Spec

The earlier design made lessons feel too close to canon. In this revision, lessons are explicitly **evidence-backed heuristics**, not rules.

### 10.3 Lesson Tiers

| Tier | Meaning |
|------|---------|
| `candidate` | Emerging pattern with local evidence only |
| `local` | Repeated evidence in one skill or one project |
| `cross_skill_advisory` | Repeated evidence across multiple skills, but still advisory |
| `externally_supported` | Cross-skill pattern with downstream or external quality support |
| `deprecated` | No longer supported by recent evidence |

### 10.4 Admission Rules

A lesson may be created only if:

1. the supporting attribution is at least `descriptive_medium_confidence`
2. the pattern has repeated more than once
3. the summary is specific enough to be falsifiable

### 10.5 Required Fields

```json
{
  "lesson_id": "lsn_20260401_001",
  "title": "Explicit failure mode lists reduce loop burden in implementation-like phases",
  "tier": "candidate",
  "pattern_category": "phase_design",
  "claim": "Adding a brief failure-mode list near the start of a phase often correlates with fewer refinement loops in implementation-oriented gates.",
  "scope": {
    "validated_skills": ["issue-flow"],
    "validated_projects": ["flow-network"],
    "applicable_phase_types": ["implementation", "testing"]
  },
  "evidence": {
    "attribution_ids": ["attr_20260401_001"],
    "sample_count": 3,
    "external_quality_support": false
  },
  "confidence": "low",
  "status": "active"
}
```

### 10.6 Query Behavior

Lessons should be queryable by:

1. category
2. applicable phase type
3. skill context

But query results must always show:

1. tier
2. evidence count
3. whether external quality support exists
4. whether the lesson is local or cross-skill

### 10.7 What Lessons Can Influence

Lessons may:

1. inform human review
2. appear as advisory context in `skill-improve`
3. help rank suggestions for consideration

Lessons may not:

1. directly mutate skills
2. remove gate criteria automatically
3. change evaluator settings

---

## 11. Phase 3: Advisory Cross-Skill Recommendations

### 11.1 Objective

Surface possible transfer ideas between structurally similar skills without auto-applying them.

### 11.2 Revision to Original Design

The earlier design moved too quickly from similarity to mutation. This revision keeps transfer advisory-only until evidence quality is stronger.

### 11.3 Similarity Model

A similarity model is still useful, but it should be treated as a coarse routing hint, not proof that a transfer is safe.

Initial similarity inputs:

1. gate names
2. phase names
3. command structure
4. top recurring failure categories

### 11.4 Transfer Recommendation Record

```json
{
  "recommendation_id": "xrec_20260401_001",
  "source_skill": "issue-flow",
  "target_skill": "feature-flow",
  "source_lesson_id": "lsn_20260401_001",
  "source_component": "SKILL.md::Phase 3 - Implementation",
  "similarity": {
    "composite": 0.68,
    "notes": "Strong phase overlap, moderate gate overlap"
  },
  "recommendation_type": "advisory_transfer",
  "summary": "Consider adding an explicit failure-mode list in the implementation phase preamble.",
  "evidence_strength": "cross_skill_advisory",
  "status": "pending_human_review"
}
```

### 11.5 Admission Rules

Cross-skill recommendations should only be generated when:

1. the underlying lesson is not merely `candidate`
2. the source evidence is repeated
3. the target skill does not already contain an equivalent pattern

### 11.6 Safety Rule

No cross-skill recommendation is auto-applied in this phase.

The only allowed path is:

1. recommendation generated
2. human or `skill-improve` surfaces it
3. human accepts it into a normal mutation workflow
4. normal ratchet keep/revert safety applies

### 11.7 What This Phase Must Not Do

1. no automatic propagation across a cluster
2. no cascade transfer chains
3. no transfer based solely on wording similarity

---

## 12. Deferred Research Track A: Meta-Evaluation

### 12.1 Why Deferred

Meta-evaluation is a good idea, but it should not be treated as an early implementation phase. It depends on longitudinal outcome data that does not yet appear fully operationalized.

### 12.2 Scope

When enough data exists, meta-evaluation may produce reports on:

1. whether ratchet variables correlate with downstream quality
2. whether some variables are saturated or underweighted
3. whether layer promotion rules make sense
4. whether thresholds appear too permissive or too strict

### 12.3 Allowed Behavior

Meta-evaluation may only:

1. generate reports
2. notify humans
3. record recommendation outcomes

It may not:

1. rewrite exponents
2. rewrite thresholds
3. rewrite `program.md`
4. modify the fixed evaluation layer

### 12.4 Minimum Preconditions

Meta-evaluation should not begin until all of the following are true:

1. enough longitudinal runs exist to avoid nonsense statistics
2. downstream quality signals are defined and linked to skill versions
3. external quality samples exist in meaningful volume

---

## 13. Deferred Research Track B: Live A/B Testing

### 13.1 Why Deferred

The earlier design assumed live variant testing could be done safely on natural workload streams. That is not credible without better assignment controls.

### 13.2 Preconditions Before Any Live Variant Testing

1. variant lineage is robust
2. workload balancing strategy exists
3. randomization or equivalent controls are defined
4. contamination and fairness are handled
5. operator overhead is acceptable

### 13.3 Interim Alternative

Before live A/B, prefer:

1. retrospective cohort analysis
2. offline replay where feasible
3. human-reviewed side-by-side comparisons

---

## 14. Deferred Research Track C: Proactive Optimization Loop

### 14.1 Why Deferred

Autonomous proactive optimization is the highest-blast-radius idea in the original spec. It is also the part most vulnerable to Goodhart effects and false confidence.

### 14.2 Policy Decision

The proactive optimization loop is explicitly out of MVP and out of the immediate follow-up phases.

It may be reconsidered only after:

1. attribution is validated,
2. lessons are useful,
3. cross-skill recommendations are safe,
4. meta-evaluation has enough evidence, and
5. external quality signals are in place.

### 14.3 Interim Replacement

Instead of POL, the system should support a lighter mechanism:

1. flag plateaued components in reports
2. surface possible experiments to humans
3. let humans decide whether to attempt a proactive mutation through normal ratchet safety

---

## 15. Integration with Existing Infrastructure

### 15.1 ratchet.py

`ratchet.py` remains unchanged in the initial program.

New tooling may read:

1. ratchet state
2. score deltas
3. keep/revert decisions

But it may not mutate evaluator logic.

### 15.2 trace_capture.py

No schema rewrite is required for the initial phases, though optional external quality sampling may add new fields through normal trace evolution if needed.

### 15.3 trace_query.py

The new analysis layer should compose on top of existing query/load functionality rather than bypass it.

### 15.4 run_metrics.py

This remains the source of run-level aggregates. The meta-harness reads from it; it does not replace it.

### 15.5 skill-improve

`skill-improve` is the main beneficiary of the new analysis, but its authority stays narrow.

The initial enhancement is:

1. show bottleneck components from `component_index.json`
2. show advisory lessons relevant to the skill
3. show advisory cross-skill recommendations when available

The operator still reviews and accepts or rejects proposals.

### 15.6 program.md

The only new knobs needed early are simple enable/disable controls for:

1. attribution
2. lessons surfacing
3. cross-skill recommendation surfacing
4. meta-evaluation reporting

No proactive optimization knobs are needed until that track is explicitly activated.

---

## 16. Validation and Governance

### 16.1 Required Boundaries

The following always require human approval:

1. evaluator changes
2. threshold changes
3. scoring exponent changes
4. removal of gate criteria
5. broad cross-skill propagation rules

### 16.2 Filesystem Write Boundaries

New meta-harness tooling should write only to:

1. new analysis artifacts under the trace/meta directories
2. optional autoflow support state
3. mutable skill artifacts only through existing human-reviewed mutation workflows

### 16.3 Reporting Discipline

Every recommendation artifact must include:

1. what evidence was used
2. what evidence was missing
3. what the system is claiming
4. what the system is explicitly **not** claiming

### 16.4 Kill Switches

The program should support fast suspension of:

1. lessons surfacing
2. cross-skill recommendation surfacing
3. meta-evaluation reporting

If recommendations are clearly degrading decision quality, the correct move is to turn them off and return to the baseline harness.

---

## 17. Risk Analysis

### 17.1 Goodhart's Law

This remains the central risk.

Mitigation in the revised design:

1. keep attribution descriptive early
2. require external quality support before strong confidence tiers
3. forbid evaluator self-modification
4. keep transfer advisory-only in early phases

### 17.2 Overfitting to Local Histories

A component can look good in one local context and fail elsewhere.

Mitigation:

1. lesson tiers that distinguish local from broader evidence
2. validation gates between phases
3. no proactive optimization until broader evidence exists

### 17.3 False Precision from Small Samples

Tiny score deltas over tiny windows can look scientific while being mostly noise.

Mitigation:

1. stronger evidence thresholds
2. uncertainty labels
3. explicit prohibition on causal claims in early phases

### 17.4 Cross-Skill Contamination

Bad ideas can spread quickly if transfer becomes automatic.

Mitigation:

1. advisory-only transfer
2. human review
3. normal ratchet validation after acceptance

### 17.5 Operational Complexity

A meta-layer can become harder to maintain than the thing it improves.

Mitigation:

1. start with one standalone analysis script
2. add one capability at a time
3. require every phase to deliver standalone value

---

## 18. Implementation Plan

### 18.1 Phase Sequence

| Phase | Build | Output | Promotion Gate |
|------|-------|--------|----------------|
| 0 | Instrumentation and lineage cleanup | Reliable outcome links and version references | Required for all later phases |
| 1 | Descriptive attribution MVP | `attributions.ndjson`, `component_index.json` | Implemented; now requires usefulness review |
| 1.5 | Validation gate | `validation_summary.json` | Partially implemented; must pass before phase 2 |
| 2 | Advisory lessons registry | `lessons.ndjson` | Lessons are useful and not misleading |
| 3 | Advisory cross-skill recommendations | `cross_skill_recommendations.ndjson` | Safe recommendation quality |
| R1 | Reporting-only meta-evaluation | reports only | Requires enough outcome data |
| R2 | Live A/B experimentation | research only | Requires assignment controls |
| R3 | Proactive optimization | research only | Requires success in all earlier phases |

### 18.2 MVP Recommendation

Do not build a fresh MVP first. Validate the implemented Phase 1 first.

That means:

1. run the existing attribution tooling on enough real cycles to test stability
2. review whether the current component index changes actual human decisions
3. keep evaluator changes at zero
4. keep autonomous mutation changes at zero

### 18.3 Exit Criteria Between Phases

Each phase should end with a written review answering:

1. Did this phase provide standalone value?
2. Did it increase or decrease operator trust?
3. What evidence says the next phase is safe?
4. What evidence says the next phase is not yet safe?

If the answers are weak, the program pauses.

---

## 19. Build-First Recommendation

If work starts now, the first implementation target should be:

**validation of the existing `attribute.py` and `component_index.json`, and nothing more ambitious.**

This gives immediate value while honoring the constraints that emerged from the feasibility review:

1. it is grounded in data that already exists,
2. it does not pretend to solve causality,
3. it does not destabilize the ratchet,
4. it tests whether the current observability layer improves operator visibility in practice, and
5. it creates the evidence base needed before lessons or transfer are introduced.

---

## 20. Final Position

The meta-harness is worth building, but only if it grows in the same way a good evaluator grows: cautiously, transparently, and with more humility than optimism.

The original vision was compelling but too eager to convert noisy analytics into automation. The revised design keeps the vision while tightening the contract:

1. **observe first**
2. **validate second**
3. **recommend third**
4. **automate last**

That is the version of the design most likely to survive contact with real workloads.
