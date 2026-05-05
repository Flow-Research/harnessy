# 📑 Harnessy Experiment System — Complete File Index

## 🎯 Entry Points (Start Here!)

### 1. **COMPLETE_SUMMARY.md** ← START HERE!
- **Length:** ~20 KB
- **Time to read:** 10 min
- **Contains:** Complete overview of everything delivered
- **Audience:** Everyone
- **Content:** What was built, why, how to use it, expected results

### 2. **START_HERE.md** ← QUICK START
- **Length:** ~8 KB
- **Time to read:** 5 min
- **Contains:** 4-step workflow, quick reference
- **Audience:** Operators
- **Content:** "How do I run this right now?"

### 3. **ARCHITECTURE.md** ← VISUAL SYSTEM DESIGN
- **Length:** ~6 KB (ASCII diagrams)
- **Time to read:** 3 min
- **Contains:** System architecture, data flow diagrams
- **Audience:** Technical leads
- **Content:** How all pieces fit together

---

## 📚 Detailed Documentation

### 4. **EXPERIMENT_GUIDE.md** ← METHODOLOGY BIBLE
- **Length:** 15 KB
- **Time to read:** 15 min
- **Contains:** Complete experiment methodology
- **Key Sections:**
  - Quick start guide
  - Metrics definitions (f, p, q, r, S)
  - All 6 experiment phases explained
  - Expected results and graphs
  - Environment-specific instructions
  - Troubleshooting guide
  - Stakeholder reporting templates
- **Audience:** Operators, stakeholders, developers
- **When to read:** Before running or understanding the system

### 5. **EXPERIMENT_VERIFICATION.md** ← PRE-FLIGHT CHECKLIST
- **Length:** 10 KB
- **Time to read:** 10 min (while checking boxes)
- **Contains:** Pre-experiment validation checklist
- **Key Sections:**
  - Environment setup validation
  - Harnessy installation checks
  - Permissions & access validation
  - Test suite validation
  - Sanity checks
  - Expected outputs
  - Troubleshooting
- **Audience:** Operators
- **When to read:** Before running the experiment

### 6. **EXPERIMENT_IMPLEMENTATION.md** ← INTEGRATION GUIDE
- **Length:** 15 KB
- **Time to read:** 15 min
- **Contains:** Integration with existing systems
- **Key Sections:**
  - Implementation summary
  - Each component explained
  - Running in different environments
  - CI/CD integration examples
  - Custom metrics
- **Audience:** Developers, DevOps engineers
- **When to read:** When integrating with your systems

---

## 🔧 Executable Scripts

### 7. **tests/harness/run-regression-recovery-experiment.sh** ← MAIN ORCHESTRATOR
- **Type:** Bash script
- **Size:** 13 KB (~400 lines)
- **Runtime:** 5-15 minutes (depends on test suite)
- **Purpose:** Runs the complete 6-phase experiment
- **Input:** Command-line flags (skill, failure type, etc)
- **Output:** Directory with metrics, logs, reports
- **Usage:**
  ```bash
  bash tests/harness/run-regression-recovery-experiment.sh \
    --skill engineer \
    --injected-failure missing-step \
    --with-recovery true \
    --output-dir .experiments
  ```
- **Key Phases:**
  1. Baseline measurement
  2. Entropy injection
  3. Degradation measurement
  4. Recovery trigger
  5. Validation
  6. Evidence generation

### 8. **tests/harness/experiment_analysis.py** ← ANALYSIS & REPORTING
- **Type:** Python 3.9+ script
- **Size:** 12 KB (~400 lines)
- **Runtime:** 1 minute
- **Purpose:** Analyzes baseline/degraded/recovered metrics
- **Input:** Three JSON metric files
- **Output:** Markdown report + JSON export
- **Usage:**
  ```bash
  python3 tests/harness/experiment_analysis.py \
    --baseline baseline_metrics.json \
    --degraded degraded_metrics.json \
    --recovered recovered_metrics.json \
    --output results_dir \
    --json export.json
  ```
- **Key Features:**
  - Computes composite scores
  - Validates hard constraints
  - Generates markdown report
  - Exports structured JSON

### 9. **tests/harness/README_EXPERIMENT.md** ← QUICK REFERENCE
- **Length:** 9 KB
- **Time to read:** 5 min (while executing)
- **Purpose:** One-page quick reference
- **Content:** Files, usage, options, troubleshooting
- **Audience:** Operators
- **Use:** Keep open in another terminal during execution

---

## 📊 Output Files (Generated After Running)

When you run the experiment, you'll get these outputs in `.experiments/regression-recovery-TIMESTAMP/`:

### Generated Metrics
- **baseline_metrics.json** - Ratchet scores for baseline phase
- **degraded_metrics.json** - Ratchet scores for degraded phase
- **recovered_metrics.json** - Ratchet scores for recovered phase

### Generated Logs
- **baseline_run.log** - Test execution log (baseline)
- **degraded_run.log** - Test execution log (degraded)
- **recovered_run.log** - Test execution log (recovered)

### Generated Reports
- **EXPERIMENT_REPORT.md** - Overview report
- **EXPERIMENT_ANALYSIS.md** - ✨ **DETAILED ANALYSIS (SHARE THIS!)**
- **visualization_data.json** - Graph data for stakeholders
- **analysis_results.json** - Structured results for dashboards

### Backups
- **SKILL.md.baseline** - Original skill backup

---

## 📖 Reading Order (Recommended)

### For First-Time Users
1. **COMPLETE_SUMMARY.md** (10 min) ← Start here!
2. **ARCHITECTURE.md** (3 min) ← See the big picture
3. **EXPERIMENT_VERIFICATION.md** (10 min) ← Check your environment
4. **START_HERE.md** (5 min) ← Quick start reference

### For Running the Experiment
1. **EXPERIMENT_VERIFICATION.md** ← Check boxes
2. **tests/harness/run-regression-recovery-experiment.sh** ← Execute
3. **tests/harness/README_EXPERIMENT.md** ← Reference while running
4. **tests/harness/experiment_analysis.py** ← Run analysis
5. **EXPERIMENT_ANALYSIS.md** ← Review results

### For Understanding Everything
1. **EXPERIMENT_GUIDE.md** ← Complete methodology
2. **program.md** ← Scoring system details
3. **AGENTS.md** ← Framework documentation
4. **tools/flow-install/skills/_shared/ratchet.py** ← Implementation

### For Integration
1. **EXPERIMENT_IMPLEMENTATION.md** ← Integration guide
2. **GitHub Actions examples** ← CI/CD setup

---

## 🎯 Quick Lookup

**Question** | **Answer** | **Read This**
---|---|---
"What did you build?" | Complete experiment system | COMPLETE_SUMMARY.md
"How do I run it?" | 4-step workflow | START_HERE.md
"How does it work?" | 6-phase methodology | EXPERIMENT_GUIDE.md
"Is my setup ready?" | Validation checklist | EXPERIMENT_VERIFICATION.md
"What will I see?" | Example outputs | EXPERIMENT_GUIDE.md + ARCHITECTURE.md
"How do I integrate?" | CI/CD & dashboards | EXPERIMENT_IMPLEMENTATION.md
"Is it broken?" | Troubleshooting guide | EXPERIMENT_GUIDE.md
"What are the metrics?" | Scoring system | program.md + EXPERIMENT_GUIDE.md
"How do I share results?" | Reporting templates | EXPERIMENT_GUIDE.md + COMPLETE_SUMMARY.md
"One-page reference?" | Quick card | tests/harness/README_EXPERIMENT.md

---

## 📊 File Statistics

### Documentation (5 files, ~65 KB total)
```
COMPLETE_SUMMARY.md ................. 20 KB
EXPERIMENT_GUIDE.md ................. 15 KB
EXPERIMENT_IMPLEMENTATION.md ........ 15 KB
EXPERIMENT_VERIFICATION.md ......... 10 KB
ARCHITECTURE.md ..................... 5 KB
START_HERE.md ....................... 8 KB
```

### Scripts (3 files, ~40 KB total)
```
run-regression-recovery-experiment.sh  13 KB
experiment_analysis.py ................ 12 KB
README_EXPERIMENT.md ................... 9 KB
```

### Total Delivery: **~105 KB** of code & documentation

---

## ✨ What Each File Does

### COMPLETE_SUMMARY.md
**"Tell me everything in one readable document"**
- Overview of all deliverables
- What the experiment does
- How to run it
- What you'll see
- For stakeholders
- All in one place

### START_HERE.md
**"I just want to run it"**
- 4-step quick start
- Key metrics explained
- Success criteria
- Copy-paste commands

### ARCHITECTURE.md
**"Show me the system architecture"**
- ASCII diagrams
- Data flow
- How pieces connect
- Success validation flow

### EXPERIMENT_GUIDE.md
**"Teach me everything about this experiment"**
- Complete methodology
- Metrics definitions
- 6 phases explained
- Expected results
- Graphs & examples
- Troubleshooting
- Stakeholder templates

### EXPERIMENT_VERIFICATION.md
**"Is my system ready to run?"**
- Pre-flight checklist
- Environment validation
- Sanity checks
- Success criteria
- Problem diagnosis

### EXPERIMENT_IMPLEMENTATION.md
**"How do I integrate this?"**
- Implementation summary
- Component details
- Integration examples
- CI/CD setup
- Custom metrics

### run-regression-recovery-experiment.sh
**"Run the entire 6-phase experiment"**
- Phase 1: Baseline measurement
- Phase 2: Entropy injection
- Phase 3: Degradation measurement
- Phase 4: Recovery trigger
- Phase 5: Validation
- Phase 6: Evidence generation
- Outputs all metrics & reports

### experiment_analysis.py
**"Analyze the results and generate reports"**
- Load 3 metric files
- Compute composite scores
- Validate constraints
- Generate markdown report
- Export JSON

### tests/harness/README_EXPERIMENT.md
**"Quick reference while running"**
- One-page summary
- Files reference
- Usage options
- Quick troubleshooting

---

## 🚀 Getting Started

### For Executives/Managers
1. Read: **COMPLETE_SUMMARY.md** (10 min)
2. See: **Expected Metrics** section
3. Share: Use as stakeholder summary

### For Operators
1. Read: **EXPERIMENT_VERIFICATION.md** (10 min) ← Check boxes
2. Execute: **run-regression-recovery-experiment.sh** (10-15 min)
3. Analyze: **experiment_analysis.py** (1 min)
4. Share: **EXPERIMENT_ANALYSIS.md** (auto-generated)

### For Developers
1. Read: **EXPERIMENT_GUIDE.md** (15 min)
2. Study: **ARCHITECTURE.md** (3 min)
3. Review: **EXPERIMENT_IMPLEMENTATION.md** (15 min)
4. Integrate: GitHub Actions / CI/CD

### For Technical Leads
1. Review: **ARCHITECTURE.md** (3 min)
2. Study: **program.md** (10 min) ← Scoring system
3. Examine: **tools/flow-install/skills/_shared/ratchet.py**
4. Plan: Integration strategy

---

## 💾 Where to Find Everything

| What | Location |
|------|----------|
| Entry points | Root of repo |
| Experiment scripts | `tests/harness/` |
| Results | `.experiments/regression-recovery-*/` |
| Scoring system | `tools/flow-install/skills/_shared/ratchet.py` |
| Framework docs | `AGENTS.md` + `program.md` |

---

## 🎓 Learning Progression

```
1. COMPLETE_SUMMARY.md ──→ Understand what was built
                            ↓
2. ARCHITECTURE.md ──────→ See how it all connects
                            ↓
3. START_HERE.md ────────→ Learn quick start
                            ↓
4. EXPERIMENT_VERIFICATION.md → Validate your setup
                            ↓
5. RUN EXPERIMENT ──────→ Execute the system
                            ↓
6. EXPERIMENT_ANALYSIS.md → Review results
                            ↓
7. EXPERIMENT_GUIDE.md ──→ Deep dive into methodology
                            ↓
8. program.md ──────────→ Understand scoring system
                            ↓
9. EXPERIMENT_IMPLEMENTATION.md → Integrate with your systems
```

---

## 🎉 You Are Ready!

All files are created and tested. You can now:

✅ Read comprehensive documentation  
✅ Run the complete experiment  
✅ Analyze results automatically  
✅ Generate stakeholder reports  
✅ Integrate with your systems  
✅ Prove the Meta-Harness works  

**Next Step:** Read **COMPLETE_SUMMARY.md** or **START_HERE.md**

---

**Version:** 1.0  
**Status:** ✅ Complete & Ready  
**Total Files:** 11  
**Total Size:** ~105 KB  
**Time to First Results:** 15 minutes
