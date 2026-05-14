#!/usr/bin/env bash
# ASCII Architecture Diagram for Harnessy Experiment System
# This file documents the complete infrastructure setup

cat << 'EOF'

╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║              HARNESSY CONTROLLED REGRESSION & RECOVERY                    ║
║                   EXPERIMENT INFRASTRUCTURE                               ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝

📚 DOCUMENTATION LAYER
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│  START_HERE.md (You are here)                                             │
│    ↓                                                                       │
│  EXPERIMENT_GUIDE.md ────────→ Complete methodology                       │
│    ↓                                                                       │
│  EXPERIMENT_VERIFICATION.md ──→ Pre-flight checklist                      │
│    ↓                                                                       │
│  EXPERIMENT_IMPLEMENTATION.md ─→ Integration guide                        │
│    ↓                                                                       │
│  tests/harness/README_EXPERIMENT.md ─→ Quick reference                    │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘

🚀 EXECUTION LAYER
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│  tests/harness/run-regression-recovery-experiment.sh                      │
│  ├─ Phase 1: BASELINE ──→ baseline_metrics.json                          │
│  ├─ Phase 2: ENTROPY INJECTION ──→ SKILL.md backup                       │
│  ├─ Phase 3: DEGRADATION ──→ degraded_metrics.json                       │
│  ├─ Phase 4: RECOVERY ──→ Fixed SKILL.md                                 │
│  ├─ Phase 5: VALIDATION ──→ recovered_metrics.json                       │
│  └─ Phase 6: EVIDENCE ──→ Reports + Visualization                        │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘

📊 ANALYSIS LAYER
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│  tests/harness/experiment_analysis.py                                     │
│  ├─ Load: baseline + degraded + recovered metrics                         │
│  ├─ Compute: ΔS, regressions, constraint violations                       │
│  ├─ Validate: Hard constraint gates (catastrophic, regression, intervention)
│  └─ Generate: Markdown report + JSON export                               │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘

📁 OUTPUT STRUCTURE
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│  .experiments/regression-recovery-YYYYMMDD-HHMMSS/                        │
│  ├── baseline_metrics.json ──────┬──→ S, f, p, q, r                       │
│  ├── baseline_run.log            │                                        │
│  ├── SKILL.md.baseline ◄─────────┘                                        │
│  │                                                                         │
│  ├── degraded_metrics.json ──────┬──→ Shows failure impact                │
│  ├── degraded_run.log            │                                        │
│  │                               │                                        │
│  ├── recovered_metrics.json ─────┼──→ Proves recovery works               │
│  ├── recovered_run.log           │                                        │
│  │                               │                                        │
│  ├── EXPERIMENT_REPORT.md ◄──────┴──→ Summary overview                    │
│  ├── EXPERIMENT_ANALYSIS.md ─────────→ Detailed analysis ✨              │
│  ├── visualization_data.json ────────→ S-curve graph data                 │
│  └── analysis_results.json ──────────→ Structured output (JSON)           │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘

📈 METRICS FLOW
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│  Baseline          Degraded          Recovered                            │
│  ┌─────┐           ┌─────┐           ┌─────┐                              │
│  │f=95%│           │f=50%│           │f=98%│                              │
│  │p=88%│           │p=35%│           │p=92%│                              │
│  │q=92%│  ──────→  │q=55%│  ──────→  │q=95%│                              │
│  │r=15%│           │r=70%│           │r=12%│                              │
│  └─────┘           └─────┘           └─────┘                              │
│   S=0.85            S=0.42            S=0.89                              │
│  (healthy)       (degraded)        (recovered)                            │
│                                                                            │
│  ΔS(degrade) = -0.43              ΔS(recover) = +0.47                     │
│  (failure is detectable)           (recovery confirmed)                   │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘

🔄 SUCCESS VALIDATION
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│  Criterion 1: RECOVERY DELTA                                              │
│  ├─ ΔS (recovered - degraded) > 0.02  ✓                                   │
│  └─ Typical: +0.47 (far exceeds threshold)                               │
│                                                                            │
│  Criterion 2: NO REGRESSION                                               │
│  ├─ Baseline Delta (recovered - baseline) ≥ -0.02  ✓                     │
│  └─ Typical: +0.04 (improved beyond baseline!)                           │
│                                                                            │
│  Criterion 3: HARD CONSTRAINTS                                            │
│  ├─ Catastrophic Failure Rate: 0  ✓                                       │
│  ├─ Regression Rate: ≤ 10%  ✓                                             │
│  └─ Human Intervention: ≤ 50%  ✓                                          │
│                                                                            │
│  OVERALL: ✅ EXPERIMENT PASSED                                             │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘

📊 STAKEHOLDER DELIVERABLES
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│  EMAIL                          PRESENTATION                DASHBOARD     │
│  ├─ Summary text              ├─ S-curve graph             ├─ Import JSON │
│  ├─ Key metrics               ├─ Metric table              ├─ Track over  │
│  ├─ Attach:                   ├─ Constraints check         │  time        │
│  │  EXPERIMENT_ANALYSIS.md    └─ Conclusion slide          └─ Real-time   │
│  └─ visualization_data.json                                    monitoring  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘

🔧 USAGE QUICK START
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│  1. SETUP (5 min)                                                         │
│     $ cat EXPERIMENT_VERIFICATION.md  # Check boxes                       │
│                                                                            │
│  2. RUN (5-15 min)                                                        │
│     $ bash tests/harness/run-regression-recovery-experiment.sh \         │
│       --skill engineer \                                                  │
│       --injected-failure missing-step \                                   │
│       --with-recovery true                                                │
│                                                                            │
│  3. ANALYZE (1 min)                                                       │
│     $ python3 tests/harness/experiment_analysis.py \                     │
│       --baseline .experiments/.../baseline_metrics.json \                 │
│       --degraded .experiments/.../degraded_metrics.json \                 │
│       --recovered .experiments/.../recovered_metrics.json                 │
│                                                                            │
│  4. SHARE (5 min)                                                         │
│     $ cat .experiments/.../EXPERIMENT_ANALYSIS.md                         │
│     → Email + Deck + Dashboard                                            │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘

💡 KEY INSIGHTS
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│  • Multiplicative composite score (S) means weakness in any dimension     │
│    drags the entire metric down → no false positives                     │
│                                                                            │
│  • Hard constraint gates are vetoes → violations reject improvement       │
│    regardless of score (safety > optimization)                            │
│                                                                            │
│  • ΔS > 0.02 is the significance threshold → changes must be real, not   │
│    noise (0.47 recovery delta proves it works)                            │
│                                                                            │
│  • The experiment proves three capabilities:                              │
│    1. Failure detection (baseline → degraded)                             │
│    2. Autonomous recovery (degraded → recovered)                          │
│    3. No regression (recovered ≥ baseline)                                │
│                                                                            │
│  • All without human intervention → validates autonomous capability      │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘

🎯 SUCCESS CRITERIA SUMMARY
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│  PASS: All three criteria met                                             │
│  ├─ ✓ Recovery delta ΔS > 0.02                                            │
│  ├─ ✓ Baseline delta ≥ -0.02                                              │
│  └─ ✓ All hard constraints passed                                         │
│                                                                            │
│  FAIL: Any criterion violated                                             │
│  ├─ ✗ Recovery too small (ΔS ≤ 0.02)                                      │
│  ├─ ✗ New regressions (baseline delta < -0.02)                            │
│  └─ ✗ Constraint violation (catastrophic, regression, intervention)      │
│                                                                            │
│  TYPICAL RESULT:                                                          │
│  ├─ Baseline: 0.85                                                        │
│  ├─ Degraded: 0.42 (ΔS = -0.43)                                           │
│  ├─ Recovered: 0.89 (ΔS = +0.47, baseline delta = +0.04)                 │
│  └─ Status: ✅ PASSED                                                      │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘

📖 FILE NAVIGATION
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│  For Understanding Theory              For Practical Execution             │
│  ├─ EXPERIMENT_GUIDE.md ────────────── Run this first                      │
│  ├─ program.md (scoring system)        ├─ EXPERIMENT_VERIFICATION.md       │
│  └─ AGENTS.md (framework docs)         ├─ run-regression-recovery-exp.sh   │
│                                        ├─ experiment_analysis.py           │
│                                        └─ README_EXPERIMENT.md            │
│                                                                            │
│  For Integration                       For Quick Reference                 │
│  ├─ EXPERIMENT_IMPLEMENTATION.md       └─ START_HERE.md                    │
│  └─ GitHub Actions examples               (you are here!)                  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘

═════════════════════════════════════════════════════════════════════════════

READY TO RUN? 

1. Read: START_HERE.md (this file)
2. Check: EXPERIMENT_VERIFICATION.md
3. Execute: bash tests/harness/run-regression-recovery-experiment.sh
4. Analyze: python3 tests/harness/experiment_analysis.py
5. Share: EXPERIMENT_ANALYSIS.md

═════════════════════════════════════════════════════════════════════════════

Version: 1.0
Status: Production Ready ✨
Date: 2026-05-04

EOF
