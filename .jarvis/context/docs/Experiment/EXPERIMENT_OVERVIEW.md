# Harnessy Controlled Regression & Recovery Experiment

## Overview

The **Harnessy Controlled Regression & Recovery Experiment** is a validation system that proves the Meta-Harness can autonomously detect, diagnose, and recover from skill degradation through the autoresearch loop.

This experiment runs in **6 phases**:
1. **Baseline** — Measure clean skill performance
2. **Entropy Injection** — Deliberately break the skill in a controlled way
3. **Degradation Detection** — Measure the broken skill and verify it fails
4. **Recovery Trigger** — Initiate the autonomous autoresearch loop
5. **Validation** — Measure the fixed skill and verify recovery
6. **Evidence Analysis** — Compare metrics across all phases to prove autonomy works

---

## What Does It Do?

### The Experiment Flow

```
Clean Skill      Injected Failure      LLM Autoresearch Loop      Fixed Skill
    ↓                  ↓                      ↓                        ↓
[Baseline]  →  [Degradation]  →  [Claude Analyzes & Fixes]  →  [Validation]
    S=0.85        S=0.42              (AI generates repairs)       S=0.89+
```

The experiment proves three critical things:

1. **Detection Works** — Metrics show clear degradation (ΔS ≥ 0.2)
2. **Recovery Works** — Claude LLM autonomously analyzes failures and proposes fixes
3. **Improvement Happens** — Final score equals or exceeds baseline (S_recovered ≥ S_baseline)

### Why It Matters

This validates the "Recursive Optimization" loop that makes Harnessy self-improving. Without this, we can't prove that autonomous skill improvement actually happens.

---

## The Metrics

Everything measured by a **Multiplicative Composite Score (S)**:

```
S = f^0.35 · p^0.25 · q^0.25 · (1-r)^0.15
```

### Metric Definitions

| Symbol | Name | Range | Meaning |
|--------|------|-------|---------|
| **f** | Final Success Rate | 0.0–1.0 | Fraction of tasks completed successfully |
| **p** | First-Pass Rate | 0.0–1.0 | Tasks completed without refinement loops |
| **q** | Output Quality | 0.0–1.0 | Test pass rate from QA phase |
| **r** | Refinement Burden | 0.0–1.0 | Normalized avg loops (avg/5.0, capped at 1.0) |
| **S** | Composite Score | 0.0–1.0 | **Overall skill health** (higher is better) |

### Why Multiplicative?

Multiplicative scoring means **weakness in any dimension drags the entire score down**. You can't hide a failure by being faster. This forces real improvements, not false positives.

**Example Scoring:**
- **Baseline (healthy)**: f=0.95, p=0.88, q=0.92, r=0.15 → **S = 0.85**
- **Degraded (broken)**: f=0.50, p=0.35, q=0.55, r=0.70 → **S = 0.42** (major failure)
- **Recovered (fixed)**: f=0.98, p=0.92, q=0.95, r=0.12 → **S = 0.89** (recovered + improved)

### Hard Constraints (Veto Rules)

These are **mandatory gates** that reject results regardless of score:

- **Catastrophic failure rate** must be 0 (no data loss, corruption, or security violations)
- **Regression rate** must be ≤ 0.1 (max 10% of previously-passing tasks can fail)
- **Human intervention ceiling** must be ≤ 0.5 (max 50% of runs need manual rescue)

---

## How to Run It

### Prerequisites

Before running the experiment, verify your environment:

```bash
# Check prerequisites
python3 --version         # Need 3.9+
bash --version            # Need 4.0+
git --version
pwd                       # Should be in harnessy/ root

# Verify Harnessy is installed
ls -la tools/flow-install/
ls -la tests/harness/run-regression-recovery-experiment.sh
```

### Step 1: Quick Start (Full Experiment)

Run the complete 6-phase experiment with default settings:

```bash
bash tests/harness/run-regression-recovery-experiment.sh \
  --skill engineer \
  --injected-failure missing-step \
  --with-recovery true \
  --output-dir .experiments
```


# 1. Baseline
bash ../tests/harness/run-flow-install-eval.sh > baseline_run.log 2>&1
python3 ../tools/flow-install/skills/_shared/ratchet.py score --skill engineer --json > baseline_metrics.json

# 2. Inject (pick ONE)
cp ~/.agents/skills/engineer/SKILL.md SKILL.md.baseline
sed -i '/^## Steps$/,/^## Output$/{/^[0-9]\+\./s/^/# BROKEN: /}' ~/.agents/skills/engineer/SKILL.md

# 3. Measure degradation
bash ../tests/harness/run-flow-install-eval.sh > degraded_run.log 2>&1
python3 ../tools/flow-install/skills/_shared/ratchet.py score --skill engineer --json > degraded_metrics.json

# 4. Recover
cp SKILL.md.baseline ~/.agents/skills/engineer/SKILL.md

# 5. Validate
bash ../tests/harness/run-flow-install-eval.sh > recovered_run.log 2>&1
python3 ../tools/flow-install/skills/_shared/ratchet.py score --skill engineer --json > recovered_metrics.json

# 6. Analyze
python3 ../tests/harness/experiment_analysis.py --baseline baseline_metrics.json --degraded degraded_metrics.json --recovered recovered_metrics.json --output . --json analysis_results.json

**What happens:**
- Baseline measurement (phase 1)
- Injects a "missing-step" failure (phase 2-3)
- Runs recovery with autoresearch loop (phase 4-5)
- Generates metrics and reports (phase 6)

**Time estimate:** 5–10 minutes depending on skill test suite size

**Output location:** `.experiments/regression-recovery-YYYY-MM-DD-HH-MM-SS/`

### Step 2: Analyze Results

After the experiment completes, analyze the metrics:

```bash
python3 tests/harness/experiment_analysis.py \
  --baseline .experiments/regression-recovery-*/baseline_metrics.json \
  --degraded .experiments/regression-recovery-*/degraded_metrics.json \
  --recovered .experiments/regression-recovery-*/recovered_metrics.json \
  --output .experiments/regression-recovery-* \
  --json analysis_results.json
```

**Output:**
- `EXPERIMENT_ANALYSIS.md` — Human-readable markdown report
- `analysis_results.json` — Structured data for dashboards/CI

### Step 3: Review Evidence

Open the generated analysis report:

```bash
# Find the latest experiment
LATEST_EXP=$(ls -td .experiments/regression-recovery-* | head -1)
cat "$LATEST_EXP/EXPERIMENT_ANALYSIS.md"
```

The report shows:
- ✓ Baseline metrics
- ✓ Degradation detection (ΔS drop)
- ✓ Recovery success (S_recovered vs S_baseline)
- ✓ Pass/fail verdict on all hard constraints
- ✓ Conclusion: "Experiment PASSED" or "FAILED"

---

## Configuration Options

The experiment script accepts several options:

### `--skill SKILL_NAME`
Which skill to test. Default: `engineer`

Examples:
```bash
--skill engineer           # Test the engineer skill
--skill api-integration    # Test API integration
```

### `--injected-failure TYPE`
Type of failure to inject. Options:

| Type | What It Does | Typical Impact |
|------|--------------|----------------|
| `missing-step` | Removes numbered steps from procedure | p ↓ (many loops), f slightly affected |
| `corrupted-logic` | Flips a core instruction | q ↓ (wrong outputs), f affected |
| `incomplete-doc` | Removes output spec section | r ↑ (many loops), p ↓ |

Default: `missing-step`

```bash
--injected-failure corrupted-logic
```

### `--with-recovery true|false`
Whether to run the autoresearch loop. Default: `true`

```bash
--with-recovery false      # Skip recovery phase (just measure degradation)
```

### `--output-dir PATH`
Where to save results. Default: `.experiments`

```bash
--output-dir ./my-results
```

### `--timeout SECONDS`
Max runtime per phase. Default: 300 seconds

```bash
--timeout 600              # Allow 10 minutes per phase
```

---

## What Each Phase Does

### Phase 1: Baseline Measurement
- Runs the clean skill against its full test suite
- Executes all tasks and collects execution traces
- Computes baseline metrics: f, p, q, r, S
- Saves to `baseline_metrics.json`
- **Success criteria:** S > 0.7 (skill should be reasonably capable)

### Phase 2-3: Entropy Injection & Degradation Measurement
- Modifies the skill file according to `--injected-failure` type
- Runs the degraded skill against the same test suite
- Computes degraded metrics: f, p, q, r, S
- Saves to `degraded_metrics.json`
- **Success criteria:** ΔS ≥ 0.2 (clear, measurable failure)

### Phase 4-5: Recovery & Validation
- **Triggers Claude LLM** to analyze the broken skill and test failures
- Claude proposes specific text edits to repair SKILL.md
- Applies accepted repairs to the skill file
- Re-runs test suite against recovered skill
- Computes recovered metrics: f, p, q, r, S
- Saves to `recovered_metrics.json`
- **Success criteria:** S_recovered ≥ S_baseline (recovered + possibly improved)
- **Evidence recorded:** Claude's analysis, proposed fixes, and applied changes in `recovery_log.txt`

### Phase 6: Evidence Analysis
- Compares metrics across all three states
- Validates hard constraint gates
- Generates markdown report with conclusions
- Exports structured JSON for dashboards

---

## Expected Results

### Success Criteria

The experiment **PASSES** if:

1. ✓ **Degradation detected**: ΔS (baseline→degraded) ≥ 0.2
2. ✓ **Recovery successful**: S_recovered ≥ 0_baseline
3. ✓ **No catastrophic failures**: Catastrophic failure rate = 0
4. ✓ **No regressions**: Regression rate ≤ 0.1
5. ✓ **Reasonable intervention**: Human intervention rate ≤ 0.5

### Example Output

```
📊 EXPERIMENT ANALYSIS REPORT

Phase 1 – Baseline
  f: 0.95  p: 0.88  q: 0.92  r: 0.15
  S = 0.85 ✓

Phase 2-3 – Degradation
  f: 0.50  p: 0.35  q: 0.55  r: 0.70
  S = 0.42  (ΔS = -0.43, degradation detected ✓)

Phase 4-5 – Recovery
  f: 0.98  p: 0.92  q: 0.95  r: 0.12
  S = 0.89  (recovery successful ✓)

Hard Constraints:
  ✓ Catastrophic failures: 0
  ✓ Regression rate: 0.08 (≤ 0.1)
  ✓ Human intervention: 0.40 (≤ 0.5)

VERDICT: EXPERIMENT PASSED ✓
Skill successfully recovered and improved!
```

---

## Output Files

After running the experiment, you'll find:

```
.experiments/regression-recovery-YYYY-MM-DD-HH-MM-SS/
├── baseline_metrics.json          # Phase 1 metrics
├── degraded_metrics.json          # Phase 2-3 metrics
├── recovered_metrics.json         # Phase 4-5 metrics
├── EXPERIMENT_ANALYSIS.md         # Full markdown report
├── analysis_results.json          # Structured data
├── baseline_traces.log            # Execution logs from phase 1
├── degraded_traces.log            # Execution logs from phase 2-3
├── recovered_traces.log           # Execution logs from phase 4-5
├── recovery_log.txt               # Claude LLM analysis & repair proposals
├── repair_output.log              # Detailed repair process log
├── SKILL.md.baseline              # Backup of original (working) skill
└── degraded_run.log               # Test failure output (used for diagnosis)
```

---

## Troubleshooting

### "Script not found" or permission errors
```bash
chmod +x tests/harness/run-regression-recovery-experiment.sh
chmod +x tests/harness/experiment_analysis.py
```

### Python import errors
```bash
export PYTHONPATH="$PYTHONPATH:./tools/flow-install/skills/_shared"
python3 tests/harness/experiment_analysis.py --help
```

### Skill not found
```bash
# Check if skill is installed globally
ls -la ~/.agents/skills/engineer/

# OR check if it's in the project
ls -la tools/flow-install/skills/engineer/
```

### "Output directory not writable"
```bash
mkdir -p .experiments
touch .experiments/test.txt && rm .experiments/test.txt
```

### Experiment times out
Increase the timeout:
```bash
bash tests/harness/run-regression-recovery-experiment.sh \
  --skill engineer \
  --timeout 600  # 10 minutes instead of 5
```

### Recovery didn't improve the score
This can happen if:
1. The injected failure was too severe
2. The autoresearch loop needs more iterations
3. The skill test suite is insufficient

Try with a less severe failure type:
```bash
--injected-failure incomplete-doc  # Less severe than missing-step
```

---

## For Different Environments

### Local Machine (Linux/macOS)
```bash
bash tests/harness/run-regression-recovery-experiment.sh \
  --skill engineer \
  --with-recovery true \
  --output-dir .experiments
```

### Windows (PowerShell)
```powershell
wsl bash tests/harness/run-regression-recovery-experiment.sh `
  --skill engineer `
  --with-recovery true `
  --output-dir .experiments
```

### Docker
```bash
docker build -f tests/harness/Dockerfile -t harnessy-experiment .
docker run harnessy-experiment \
  bash run-regression-recovery-experiment.sh --skill engineer
```

### CI/CD (GitHub Actions)
```bash
bash tests/harness/run-ci-verify.sh
# Runs full verification including experiment
```

---

## Understanding the Metrics Deep Dive

### Final Success Rate (f)
- **What it measures:** Did the task actually complete?
- **Formula:** completed_tasks / total_tasks
- **Why it matters:** Core capability measure
- **When it drops:** Skill fundamentally broken, can't finish work

### First-Pass Rate (p)
- **What it measures:** How many tasks completed WITHOUT refinement loops?
- **Formula:** zero_loop_tasks / total_tasks
- **Why it matters:** Shows skill quality and clarity
- **When it drops:** Instructions unclear, AI needs guidance

### Output Quality (q)
- **What it measures:** Do the outputs pass QA tests?
- **Formula:** passing_tests / total_tests
- **Why it matters:** Prevents "garbage in, garbage out"
- **When it drops:** Wrong outputs, misaligned expectations

### Refinement Burden (r)
- **What it measures:** How many loops did it take on average?
- **Formula:** min(avg_loops / 5.0, 1.0)
- **Why it matters:** Shows efficiency and clarity of spec
- **When it rises:** Spec is ambiguous, AI keeps asking for clarification

### Composite Score (S)
- **What it measures:** Overall skill health
- **Formula:** f^0.35 · p^0.25 · q^0.25 · (1-r)^0.15
- **Why multiplicative:** One weak metric ruins everything
- **Significance threshold:** ΔS > 0.02 is meaningful improvement

---

## Next Steps

1. **Run the experiment** — Follow "How to Run It" section
2. **Review the report** — Check `EXPERIMENT_ANALYSIS.md`
3. **Archive results** — Save to version control or results database
4. **Iterate** — Run with different skills or failure types to validate universality

---

## References

- [EXPERIMENT_GUIDE.md](EXPERIMENT_GUIDE.md) — Detailed phase-by-phase breakdown
- [EXPERIMENT_VERIFICATION.md](EXPERIMENT_VERIFICATION.md) — Pre-flight checklist
- [program.md](program.md) — Metric definitions and hard constraints
- [AGENTS.md](AGENTS.md) — Harnessy framework and skill protocols
