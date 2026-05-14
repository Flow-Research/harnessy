# Harnessy Experiment Verification Checklist

Use this checklist to ensure your environment is ready to run the controlled regression & recovery experiment.

## Pre-Experiment Verification

### Environment Setup

- [ ] **Python 3.9+** installed
  ```bash
  python3 --version
  ```
  
- [ ] **Bash 4.0+** available
  ```bash
  bash --version
  ```

- [ ] **Git** installed and configured
  ```bash
  git --version
  git config --global user.name
  ```

- [ ] Running from Harnessy repository root
  ```bash
  pwd
  # Should show: .../Flow-Research/harnessy
  ls -la AGENTS.md program.md README.md
  ```

### Harnessy Installation

- [ ] **Harnessy installed** in workspace
  ```bash
  ls -la tools/flow-install/index.mjs
  ls -la tools/flow-install/skills/_shared/ratchet.py
  ```

- [ ] **Experiment scripts exist**
  ```bash
  ls -la tests/harness/run-regression-recovery-experiment.sh
  ls -la tests/harness/experiment_analysis.py
  ```

- [ ] **Target skill installed**
  ```bash
  # For engineer skill
  ls -la ~/.agents/skills/engineer/SKILL.md
  # OR
  ls -la tools/flow-install/skills/engineer/SKILL.md
  ```

### Permissions & Access

- [ ] **Execute permissions on scripts**
  ```bash
  chmod +x tests/harness/run-regression-recovery-experiment.sh
  chmod +x tests/harness/experiment_analysis.py
  ```

- [ ] **Write access to output directory**
  ```bash
  mkdir -p .experiments
  touch .experiments/test.txt && rm .experiments/test.txt
  ```

- [ ] **PYTHONPATH includes skill utilities**
  ```bash
  export PYTHONPATH="$PYTHONPATH:./tools/flow-install/skills/_shared"
  python3 -c "from ratchet import extract_variables; print('✓ ratchet importable')"
  ```

### Test Suite Validation

- [ ] **Test suite script exists**
  ```bash
  ls -la tests/harness/run-flow-install-eval.sh
  ```

- [ ] **Test suite is executable**
  ```bash
  bash tests/harness/run-flow-install-eval.sh --help 2>/dev/null || \
    echo "Test suite ready (or requires specific flags)"
  ```

- [ ] **Test fixtures available**
  ```bash
  ls -la tests/fixtures/ | head
  ```

### Data & Traces

- [ ] **Traces directory available**
  ```bash
  mkdir -p ~/.agents/traces
  mkdir -p .jarvis/context/autoflow
  ls -la ~/.agents/traces/ 2>/dev/null || echo "Traces dir will be created"
  ```

- [ ] **No stale locks from previous runs**
  ```bash
  # Clean up any leftover lock files
  rm -f ~/.agents/traces/harnessy.lock.* 2>/dev/null
  echo "✓ Cleaned stale locks"
  ```

## Pre-Experiment Sanity Checks

### Can We Measure?

- [ ] **Run one metric extraction**
  ```bash
  python3 tools/flow-install/skills/_shared/ratchet.py score \
    --skill engineer --json 2>&1 | head -5 || \
    echo "First run - metrics will populate after initial test runs"
  ```

### Can We Modify Skills?

- [ ] **Test skill backup & restore**
  ```bash
  SKILL_PATH="$HOME/.agents/skills/engineer/SKILL.md"
  [[ -f "$SKILL_PATH" ]] && {
    cp "$SKILL_PATH" "/tmp/SKILL.backup.md"
    echo "# TEST COMMENT" >> "$SKILL_PATH"
    diff /tmp/SKILL.backup.md "$SKILL_PATH" > /dev/null && {
      echo "✗ Modification failed"
      exit 1
    }
    cp /tmp/SKILL.backup.md "$SKILL_PATH"
    echo "✓ Skill backup & restore works"
  } || echo "Skill not yet installed - will use repo copy"
  ```

### Can We Run Tests?

- [ ] **Quick test run** (optional, takes 1-2 min)
  ```bash
  bash tests/harness/run-flow-install-eval.sh \
    --skip-remote \
    --timeout 60 2>&1 | tail -20
  # Or skip if too slow: just verify script exists
  ```

## Experiment Readiness

### Configuration

- [ ] **Decide on experiment parameters**
  - Skill to test: `engineer` (default) or other?
  - Failure type: `missing-step` (default), `corrupted-logic`, or `incomplete-doc`?
  - Enable recovery: `true` (default) or `false`?
  - Output directory: `.experiments` (default) or custom?

- [ ] **Create experiment plan document**
  ```bash
  cat > EXPERIMENT_PLAN.md << 'EOF'
  # Regression & Recovery Experiment Plan
  
  **Date:** $(date)
  **Skill:** engineer
  **Failure Type:** missing-step
  **Recovery Enabled:** true
  **Expected Duration:** 10 minutes
  
  ## Success Criteria
  - [ ] ΔS > 0.02 (recovery confirmed)
  - [ ] Baseline delta ≥ -0.02 (no regression)
  - [ ] Hard constraints passed
  
  ## Stakeholders
  - Results will be shared with: [your boss/team]
  EOF
  ```

### Communication

- [ ] **Notify relevant parties**
  - Experimentation will take ~5-15 minutes
  - May use CPU/memory resources
  - Will generate test artifacts in `.experiments/`

- [ ] **Document where to find results**
  - Report: `.experiments/regression-recovery-*/EXPERIMENT_ANALYSIS.md`
  - Metrics: `.experiments/regression-recovery-*/baseline_metrics.json`
  - Visualizations: `.experiments/regression-recovery-*/visualization_data.json`

## Running the Experiment

### Start Sequence

1. **Open clean terminal**
   ```bash
   cd /path/to/harnessy
   export PYTHONPATH="$PYTHONPATH:./tools/flow-install/skills/_shared"
   ```

2. **Verify environment one more time**
   ```bash
   echo "Current directory: $(pwd)"
   echo "Python: $(python3 --version)"
   echo "Bash: $(bash --version | head -1)"
   ```

3. **Start experiment** (takes 5-15 minutes)
   ```bash
   bash tests/harness/run-regression-recovery-experiment.sh \
     --skill engineer \
     --injected-failure missing-step \
     --with-recovery true \
     --output-dir .experiments
   ```

4. **Monitor progress** (in another terminal)
   ```bash
   # Watch output directory grow
   watch -n 5 'ls -lah .experiments/regression-recovery-*/'
   
   # Or follow the main log
   tail -f .experiments/regression-recovery-*/baseline_run.log
   ```

### Expected Outputs

After successful completion, you should see:

```
.experiments/regression-recovery-YYYYMMDD-HHMMSS/
├── baseline_run.log                 # Test output (baseline)
├── baseline_metrics.json            # Ratchet metrics (baseline)
├── SKILL.md.baseline                # Original skill backup
├── degraded_run.log                 # Test output (broken)
├── degraded_metrics.json            # Ratchet metrics (degraded)
├── recovered_run.log                # Test output (fixed)
├── recovered_metrics.json           # Ratchet metrics (recovered)
├── EXPERIMENT_REPORT.md             # Markdown report
└── visualization_data.json          # Graph data
```

## Post-Experiment Analysis

### Quick Review

- [ ] **Check experiment report**
  ```bash
  LATEST=$(ls -t .experiments/regression-recovery-* | head -1)
  cat "$LATEST/EXPERIMENT_REPORT.md"
  ```

- [ ] **Verify success criteria**
  ```bash
  python3 tests/harness/experiment_analysis.py \
    --baseline "$LATEST/baseline_metrics.json" \
    --degraded "$LATEST/degraded_metrics.json" \
    --recovered "$LATEST/recovered_metrics.json"
  ```

### Detailed Analysis

- [ ] **Generate full report**
  ```bash
  python3 tests/harness/experiment_analysis.py \
    --baseline "$LATEST/baseline_metrics.json" \
    --degraded "$LATEST/degraded_metrics.json" \
    --recovered "$LATEST/recovered_metrics.json" \
    --output "$LATEST" \
    --json "$LATEST/analysis_results.json"
  ```

- [ ] **Review JSON for dashboards**
  ```bash
  cat "$LATEST/analysis_results.json" | python3 -m json.tool | less
  ```

### Troubleshooting

If experiment fails, check:

- [ ] **Logs for error messages**
  ```bash
  LATEST=$(ls -t .experiments/regression-recovery-* | head -1)
  grep -i error "$LATEST"/*.log | head -20
  ```

- [ ] **Script permissions**
  ```bash
  ls -la tests/harness/run-regression-recovery-experiment.sh
  # Should show: -rwxr-xr-x
  ```

- [ ] **Python environment**
  ```bash
  python3 -c "import json; print('✓ Python OK')"
  python3 -c "from ratchet import *; print('✓ Ratchet importable')" || \
    echo "Ratchet import failed - check PYTHONPATH"
  ```

- [ ] **Skill availability**
  ```bash
  [[ -f ~/.agents/skills/engineer/SKILL.md ]] && \
    echo "✓ Skill found in ~/.agents" || \
    echo "Using repo copy at tools/flow-install/skills/engineer/SKILL.md"
  ```

## Sharing Results

### With Management

- [ ] **Create summary email**
  - Include key metrics (ΔS, recovery delta)
  - Mention hard constraints validation
  - Attach report PDF
  
- [ ] **Prepare slide deck**
  - S-curve recovery graph
  - Metric comparison table
  - Success/failure conclusion

### With Technical Team

- [ ] **Share raw data**
  - JSON files: baseline_metrics.json, degraded_metrics.json, recovered_metrics.json
  - Analysis results: analysis_results.json
  - Logs: baseline_run.log, degraded_run.log, recovered_run.log

- [ ] **Document findings**
  - Which failure mode was most impactful?
  - Where did the recovery loop struggle?
  - Recommendations for future autoresearch improvements?

## Final Checklist

Before declaring success:

- [ ] Experiment completed without crashes
- [ ] All three metric files (baseline, degraded, recovered) generated
- [ ] Analysis report generated
- [ ] Success criteria confirmed:
  - [ ] ΔS > 0.02
  - [ ] Baseline delta ≥ -0.02
  - [ ] Hard constraints passed
- [ ] Results shared with stakeholders
- [ ] Artifacts archived (`.experiments/regression-recovery-*/`)

---

**Experiment Ready?** ✓ Check all boxes above, then run:

```bash
bash tests/harness/run-regression-recovery-experiment.sh
```

**Questions?** See [EXPERIMENT_GUIDE.md](EXPERIMENT_GUIDE.md) for detailed documentation.
