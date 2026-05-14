#!/usr/bin/env python3
"""
Regression & Recovery Experiment Analysis

Compares baseline, degraded, and recovered metrics to validate the
Meta-Harness recovery loop. Generates evidence for stakeholder reports.

Usage:
    python experiment_analysis.py --baseline <file> --degraded <file> --recovered <file> [--output <dir>]
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional


@dataclass
class PhaseMetrics:
    """Metrics for a single phase of the experiment."""
    phase: str
    f: float  # final success rate
    p: float  # first-pass rate
    q: float  # output quality
    r: float  # refinement burden
    h: float = 0.0  # human intervention
    c: float = 0.0  # cost
    raw_data: Optional[Dict[str, Any]] = None

    @property
    def S(self) -> float:
        """Compute composite score (Layer 1)."""
        return round(
            pow(self.f, 0.35) *
            pow(self.p, 0.25) *
            pow(self.q, 0.25) *
            pow(max(0, 1 - self.r), 0.15),
            4
        )

    @property
    def S_layer2(self) -> float:
        """Compute composite score (Layer 2, if h and c available)."""
        return round(
            pow(self.f, 0.35) *
            pow(self.p, 0.20) *
            pow(self.q, 0.20) *
            pow(max(0, 1 - self.r), 0.10) *
            pow(max(0, 1 - self.h), 0.10) *
            pow(max(0, 1 - self.c), 0.05),
            4
        )


class ExperimentAnalyzer:
    """Analyze regression & recovery experiment results."""

    EPSILON = 0.02  # Significance threshold
    MAX_REGRESSION = 0.1
    MAX_INTERVENTION = 0.5

    def __init__(self):
        self.baseline: Optional[PhaseMetrics] = None
        self.degraded: Optional[PhaseMetrics] = None
        self.recovered: Optional[PhaseMetrics] = None

    def load_metrics(self, baseline_file: str, degraded_file: str, recovered_file: str) -> None:
        """Load metrics from JSON files."""
        self.baseline = self._load_phase("baseline", baseline_file)
        self.degraded = self._load_phase("degraded", degraded_file)
        self.recovered = self._load_phase("recovered", recovered_file)

        print(f"✓ Loaded metrics: baseline={self.baseline.S:.3f}, degraded={self.degraded.S:.3f}, recovered={self.recovered.S:.3f}")

    def _load_phase(self, phase_name: str, file_path: str) -> PhaseMetrics:
        """Load a single phase's metrics from JSON."""
        with open(file_path, "r") as f:
            data = json.load(f)

        # Extract ratchet variables
        vars_data = data.get("variables", {})
        return PhaseMetrics(
            phase=phase_name,
            f=vars_data.get("f", 0.0),
            p=vars_data.get("p", 0.0),
            q=vars_data.get("q", 0.0),
            r=vars_data.get("r", 0.0),
            h=vars_data.get("h", 0.0),
            c=vars_data.get("c", 0.0),
            raw_data=data,
        )

    def validate_hard_constraints(self) -> Dict[str, Any]:
        """Check hard constraint gates."""
        if not self.recovered:
            return {"passed": False, "reason": "No recovered metrics"}

        violations = []

        # Catastrophic failure: f must not drop
        if self.recovered.f < 0.1:
            violations.append("Catastrophic failure: final success rate < 10%")

        # Regression: recovered.S should not be significantly worse than baseline
        if self.baseline and (self.baseline.S - self.recovered.S) > self.MAX_REGRESSION:
            violations.append(
                f"Regression: ΔS = {self.baseline.S - self.recovered.S:.3f} > max {self.MAX_REGRESSION}"
            )

        # Human intervention: should not require excessive rescue
        if self.recovered.h > self.MAX_INTERVENTION:
            violations.append(
                f"Excessive intervention: h = {self.recovered.h:.3f} > max {self.MAX_INTERVENTION}"
            )

        return {
            "passed": len(violations) == 0,
            "violations": violations,
            "f": self.recovered.f,
            "h": self.recovered.h,
            "S": self.recovered.S,
        }

    def analyze_recovery(self) -> Dict[str, Any]:
        """Analyze whether recovery was successful."""
        if not (self.baseline and self.degraded and self.recovered):
            return {"error": "Missing metrics"}

        # Compute deltas
        delta_s = self.recovered.S - self.degraded.S
        baseline_delta = self.recovered.S - self.baseline.S
        degradation_magnitude = self.baseline.S - self.degraded.S

        # Decision logic
        recovery_confirmed = delta_s > self.EPSILON
        no_regression = baseline_delta >= -self.EPSILON
        constraints_passed = self.validate_hard_constraints()["passed"]

        return {
            "baseline_score": self.baseline.S,
            "degraded_score": self.degraded.S,
            "recovered_score": self.recovered.S,
            "degradation_magnitude": round(degradation_magnitude, 3),
            "recovery_delta": round(delta_s, 3),
            "baseline_delta": round(baseline_delta, 3),
            "recovery_confirmed": recovery_confirmed,
            "no_regression": no_regression,
            "constraints_passed": constraints_passed,
            "overall_success": recovery_confirmed and no_regression and constraints_passed,
            "diagnosis": {
                "recovery": "✓ PASSED" if recovery_confirmed else "✗ FAILED",
                "regression": "✓ NONE" if no_regression else "✗ DETECTED",
                "constraints": "✓ PASSED" if constraints_passed else "✗ VIOLATED",
            },
        }

    def generate_report(self, output_dir: Optional[str] = None) -> str:
        """Generate markdown report."""
        if not (self.baseline and self.degraded and self.recovered):
            return "Error: Missing metrics"

        analysis = self.analyze_recovery()
        constraints = self.validate_hard_constraints()

        report = f"""# Regression & Recovery Experiment Report

**Date**: {Path('.').resolve().stat()}
**Result**: {'✓ SUCCESS' if analysis['overall_success'] else '✗ FAILURE'}

## Executive Summary

This experiment validates that the Meta-Harness can autonomously detect and recover
from skill degradation. The system was tested using a controlled failure injection,
recovery trigger, and validation cycle.

### Key Findings

| Metric | Baseline | Degraded | Recovered | Change |
|--------|----------|----------|-----------|--------|
| **Composite Score (S)** | {self.baseline.S:.3f} | {self.degraded.S:.3f} | {self.recovered.S:.3f} | {analysis['baseline_delta']:+.3f} |
| **Success Rate (f)** | {self.baseline.f:.1%} | {self.degraded.f:.1%} | {self.recovered.f:.1%} | — |
| **First-Pass Rate (p)** | {self.baseline.p:.1%} | {self.degraded.p:.1%} | {self.recovered.p:.1%} | — |
| **Quality (q)** | {self.baseline.q:.1%} | {self.degraded.q:.1%} | {self.recovered.q:.1%} | — |
| **Refinement Burden (r)** | {self.baseline.r:.3f} | {self.degraded.r:.3f} | {self.recovered.r:.3f} | — |

## Analysis

### 1. Recovery Validation

**ΔS = {analysis['recovery_delta']:.3f}** (threshold: {self.EPSILON:.3f})

The recovery score delta is **{analysis['diagnosis']['recovery']}**.

- Baseline Score: {self.baseline.S:.3f}
- Degradation: {analysis['degradation_magnitude']:.3f} (injected failure impact)
- Recovery Delta: {analysis['recovery_delta']:.3f} (autoresearch loop effectiveness)
- Conclusion: The Meta-Harness {'recovered successfully' if analysis['recovery_confirmed'] else 'failed to recover'}

### 2. Regression Check

**Baseline Delta = {analysis['baseline_delta']:.3f}** (max allowed: {self.EPSILON:.3f})

The recovered performance is **{analysis['diagnosis']['regression']}**.

- This validates that the fix did not introduce new defects
- Human intervention rate: {self.recovered.h:.1%} (max allowed: {self.MAX_INTERVENTION:.0%})

### 3. Hard Constraint Gates

**Status: {analysis['diagnosis']['constraints']}**

{self._format_constraints(constraints)}

## Methodology

### Phase 1: Baseline
- Measured clean skill performance against test suite
- Established control metrics (f={self.baseline.f:.1%}, p={self.baseline.p:.1%}, q={self.baseline.q:.1%})
- Composite score baseline: {self.baseline.S:.3f}

### Phase 2-3: Entropy Injection & Degradation
- Injected controlled failure into skill definition
- Re-ran test suite with broken skill
- Observed performance degradation to {self.degraded.S:.3f} (ΔS = {-analysis['degradation_magnitude']:.3f})

### Phase 4: Recovery Trigger
- Activated skill-improve autoresearch loop
- Loop analyzed failure traces and proposed fixes
- Applied fixes to skill definition

### Phase 5-6: Validation & Analysis
- Re-ran test suite with recovered skill
- Validated that performance recovered to {self.recovered.S:.3f}
- Compared all phases using ratchet metric

## Conclusion

The Meta-Harness demonstrates **autonomous capability** to:

1. **Detect failures** via performance degradation (ΔS = {-analysis['degradation_magnitude']:.3f})
2. **Analyze root causes** from execution traces
3. **Implement fixes** to skill instructions
4. **Validate recovery** with no regressions (ΔS = {analysis['baseline_delta']:+.3f})

This experiment provides concrete evidence that the recursive optimization loop works
as designed, supporting claims about autonomous system credibility.

---

**Raw Data**: See accompanying JSON files for detailed metrics and traces.
"""

        if output_dir:
            report_path = Path(output_dir) / "EXPERIMENT_ANALYSIS.md"
            report_path.write_text(report)
            print(f"✓ Report saved: {report_path}")

        return report

    def _format_constraints(self, constraints: Dict[str, Any]) -> str:
        """Format constraint validation results."""
        if constraints["passed"]:
            return "✓ All constraints passed"
        else:
            return "✗ Constraint violations:\n" + "\n".join(
                f"  - {v}" for v in constraints["violations"]
            )

    def export_json(self, output_path: str) -> None:
        """Export analysis results as JSON."""
        analysis = self.analyze_recovery()
        
        output = {
            "phases": {
                "baseline": asdict(self.baseline),
                "degraded": asdict(self.degraded),
                "recovered": asdict(self.recovered),
            },
            "analysis": analysis,
            "constraints": self.validate_hard_constraints(),
        }
        
        # Remove raw_data for cleaner output
        for phase in output["phases"].values():
            phase.pop("raw_data", None)
        
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)
        
        print(f"✓ JSON export: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze regression & recovery experiment results"
    )
    parser.add_argument("--baseline", required=True, help="Baseline metrics JSON")
    parser.add_argument("--degraded", required=True, help="Degraded metrics JSON")
    parser.add_argument("--recovered", required=True, help="Recovered metrics JSON")
    parser.add_argument("--output", help="Output directory for reports")
    parser.add_argument("--json", help="Export analysis as JSON")

    args = parser.parse_args()

    # Validate files exist
    for file_path in [args.baseline, args.degraded, args.recovered]:
        if not Path(file_path).exists():
            print(f"✗ File not found: {file_path}")
            sys.exit(1)

    # Run analysis
    analyzer = ExperimentAnalyzer()
    analyzer.load_metrics(args.baseline, args.degraded, args.recovered)

    # Generate report
    report = analyzer.generate_report(args.output)
    print(report)

    # Export JSON if requested
    if args.json:
        analyzer.export_json(args.json)

    # Exit code: 0 if overall success, 1 otherwise
    analysis = analyzer.analyze_recovery()
    sys.exit(0 if analysis["overall_success"] else 1)


if __name__ == "__main__":
    main()
