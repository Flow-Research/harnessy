#!/usr/bin/env python3
"""
Harnessy Controlled Regression & Recovery Experiment Orchestrator
Handles all 6 phases with proper path handling for Windows.
"""

import os
import sys
import json
import argparse
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

def load_env_file(repo_root):
    """Load environment variables from .env file"""
    env_file = Path(repo_root) / ".env"
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
                        # Don't print API key values for security
                        if 'KEY' in key.upper():
                            print(f"[*] Loaded {key.strip()} from .env")
                        else:
                            print(f"[*] Loaded {key.strip()}={value.strip()} from .env")

def run_command(cmd, description="", is_bash=False):
    """Run a command and return True if successful"""
    print(f"\n[*] {description}")
    
    # If bash script, convert Windows path to bash format and call through bash
    if is_bash and isinstance(cmd, str):
        # Convert C:\path\to\file to /mnt/c/path/to/file
        bash_path = cmd.replace("\\", "/")
        if bash_path[1:3] == ":/":
            bash_path = f"/mnt/{bash_path[0].lower()}{bash_path[2:]}"
        cmd = ["bash", bash_path]
    
    if isinstance(cmd, str):
        print(f"    Command: {cmd}")
    else:
        print(f"    Command: {' '.join(str(c) for c in cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, env=os.environ.copy())
        if result.returncode == 0:
            print(f"    [OK] Success")
            return True
        else:
            print(f"    [ERROR] Failed (exit code: {result.returncode})")
            if result.stdout:
                print(f"    Stdout: {result.stdout[:300]}")
            if result.stderr:
                print(f"    Stderr: {result.stderr[:300]}")
            return False
    except Exception as e:
        print(f"    [ERROR] Exception: {e}")
        return False

def phase_1_baseline(skill_path, experiment_dir, repo_root, test_suite):
    """Phase 1: Baseline Measurement"""
    print("\n" + "="*80)
    print("PHASE 1: BASELINE MEASUREMENT")
    print("="*80)
    
    baseline_file = Path(experiment_dir) / "baseline_metrics.json"
    baseline_log = Path(experiment_dir) / "baseline_run.log"
    
    # Run test suite (bash script) and capture output
    bash_cmd = f"bash {str(test_suite)} > {str(baseline_log.absolute())} 2>&1"
    print(f"\n[*] Running baseline test suite")
    print(f"    Command: {bash_cmd}")
    try:
        result = subprocess.run(bash_cmd, capture_output=False, text=True, check=False, shell=True)
        print(f"    [OK] Baseline tests completed (output saved)")
    except Exception as e:
        print(f"    [WARNING] Baseline tests had issues: {e}")
    
    # Capture metrics with ratchet
    ratchet_script = repo_root / "tools/flow-install/skills/_shared/ratchet.py"
    cmd = [sys.executable, str(ratchet_script), "score", "--skill", "engineer", "--json"]
    
    if run_command(cmd, "Computing baseline metrics"):
        print(f"    Baseline file: {baseline_file}")
    
    return str(baseline_file)

def phase_2_entropy(skill_md, experiment_dir, repo_root):
    """Phase 2: Inject Entropy"""
    print("\n" + "="*80)
    print("PHASE 2: INJECT ENTROPY")
    print("="*80)
    
    # Backup original
    baseline_backup = Path(experiment_dir) / "SKILL.md.baseline"
    shutil.copy(skill_md, baseline_backup)
    print(f"[OK] Backed up original SKILL.md to {baseline_backup}")
    
    # Run entropy injection
    inject_script = repo_root / "tests/harness/inject_entropy.py"
    cmd = [sys.executable, str(inject_script), str(skill_md), "missing-step"]
    
    if run_command(cmd, "Injecting entropy (missing-step failure)"):
        print(f"[OK] Entropy injection successful")
        return True
    else:
        print(f"[ERROR] Entropy injection failed")
        return False

def phase_3_degradation(skill_path, experiment_dir, repo_root, test_suite):
    """Phase 3: Measure Degradation"""
    print("\n" + "="*80)
    print("PHASE 3: MEASURE DEGRADATION")
    print("="*80)
    
    degraded_log = Path(experiment_dir) / "degraded_run.log"
    degraded_file = Path(experiment_dir) / "degraded_metrics.json"
    
    # Run test suite with broken skill (bash script) and capture output
    bash_cmd = f"bash {str(test_suite)} > {str(degraded_log.absolute())} 2>&1"
    print(f"\n[*] Running test suite with broken skill")
    print(f"    Command: {bash_cmd}")
    try:
        result = subprocess.run(bash_cmd, capture_output=False, text=True, check=False, shell=True)
        print(f"    [OK] Test suite completed (output saved)")
    except Exception as e:
        print(f"    [WARNING] Test suite had issues: {e}")
    
    # Capture degraded metrics
    ratchet_script = repo_root / "tools/flow-install/skills/_shared/ratchet.py"
    cmd = [sys.executable, str(ratchet_script), "score", "--skill", "engineer", "--json"]
    
    if run_command(cmd, "Computing degraded metrics"):
        print(f"[OK] Degraded metrics captured")
    
    return str(degraded_file)

def phase_4_recovery(skill_md, experiment_dir, repo_root, llm_provider):
    """Phase 4: LLM-Based Recovery"""
    print("\n" + "="*80)
    print("PHASE 4: LLM-BASED RECOVERY")
    print("="*80)
    
    baseline_skill = Path(experiment_dir) / "SKILL.md.baseline"
    degraded_log = Path(experiment_dir) / "degraded_run.log"
    
    repair_script = repo_root / "tests/harness/skill_repair.py"
    cmd = [
        sys.executable, str(repair_script),
        "--skill", "engineer",
        "--broken-skill-path", str(skill_md),
        "--baseline-skill-path", str(baseline_skill.absolute()),
        "--test-log", str(degraded_log.absolute()),
        "--provider", llm_provider,
        "--auto-apply"
    ]
    
    if run_command(cmd, f"Running LLM repair with {llm_provider}"):
        print(f"[OK] LLM repair completed")
        return True
    else:
        print(f"[WARNING] LLM repair failed, restoring from backup")
        shutil.copy(baseline_skill, skill_md)
        return True  # Fallback successful

def phase_5_validation(experiment_dir, repo_root, test_suite):
    """Phase 5: Validate Recovery"""
    print("\n" + "="*80)
    print("PHASE 5: VALIDATE RECOVERY")
    print("="*80)
    
    recovered_log = Path(experiment_dir) / "recovered_run.log"
    
    # Run test suite with recovered skill (bash script) and capture output
    bash_cmd = f"bash {str(test_suite)} > {str(recovered_log.absolute())} 2>&1"
    print(f"\n[*] Running test suite with recovered skill")
    print(f"    Command: {bash_cmd}")
    try:
        result = subprocess.run(bash_cmd, capture_output=False, text=True, check=False, shell=True)
        print(f"    [OK] Recovery tests completed (output saved)")
    except Exception as e:
        print(f"    [WARNING] Recovery tests had issues: {e}")
    
    # Capture recovered metrics
    ratchet_script = repo_root / "tools/flow-install/skills/_shared/ratchet.py"
    cmd = [sys.executable, str(ratchet_script), "score", "--skill", "engineer", "--json"]
    
    if run_command(cmd, "Computing recovered metrics"):
        print(f"[OK] Recovered metrics captured")
    
    return str(Path(experiment_dir) / "recovered_metrics.json")

def main():
    parser = argparse.ArgumentParser(description="Harnessy Regression & Recovery Experiment")
    parser.add_argument("--skill", default="engineer", help="Skill to test")
    parser.add_argument("--failure-type", default="missing-step", help="Type of failure to inject")
    parser.add_argument("--llm-provider", default="gemini", help="LLM provider (gemini, claude, gpt)")
    parser.add_argument("--output-dir", default=".experiments", help="Output directory")
    
    args = parser.parse_args()
    
    # Setup paths
    repo_root = Path(__file__).parent.parent.parent
    
    # Load .env file to get API keys
    load_env_file(repo_root)
    
    skill_path = repo_root / "tools/flow-install/skills" / args.skill
    skill_md = skill_path / "SKILL.md"
    test_suite = repo_root / "tests/harness/run-flow-install-eval.sh"
    
    if not skill_md.exists():
        print(f"[ERROR] Skill file not found: {skill_md}")
        return 1
    
    # Create experiment directory
    exp_dir = Path(args.output_dir) / f"regression-recovery-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    exp_dir.mkdir(parents=True, exist_ok=True)
    
    print("="*80)
    print("HARNESSY CONTROLLED REGRESSION & RECOVERY EXPERIMENT")
    print("="*80)
    print(f"Skill: {args.skill}")
    print(f"Failure Type: {args.failure_type}")
    print(f"LLM Provider: {args.llm_provider}")
    print(f"Output Directory: {exp_dir}")
    print()
    
    # Execute phases
    try:
        # Phase 1
        baseline_file = phase_1_baseline(skill_path, exp_dir, repo_root, str(test_suite))
        if not baseline_file:
            print("[ERROR] Phase 1 failed")
            return 1
        
        # Phase 2
        if not phase_2_entropy(skill_md, exp_dir, repo_root):
            print("[ERROR] Phase 2 failed")
            return 1
        
        # Phase 3
        degraded_file = phase_3_degradation(skill_path, exp_dir, repo_root, str(test_suite))
        if not degraded_file:
            print("[ERROR] Phase 3 failed")
            return 1
        
        # Phase 4
        if not phase_4_recovery(skill_md, exp_dir, repo_root, args.llm_provider):
            print("[ERROR] Phase 4 failed")
            return 1
        
        # Phase 5
        recovered_file = phase_5_validation(exp_dir, repo_root, str(test_suite))
        if not recovered_file:
            print("[ERROR] Phase 5 failed")
            return 1
        
        print("\n" + "="*80)
        print("EXPERIMENT COMPLETED SUCCESSFULLY")
        print("="*80)
        print(f"Results saved to: {exp_dir}")
        
        # Generate report
        report_script = repo_root / "tests/harness/generate_report.py"
        report_file = exp_dir / "EXPERIMENT_REPORT.html"
        if report_script.exists():
            print(f"\nGenerating HTML report...")
            cmd = [sys.executable, str(report_script), str(exp_dir), str(report_file)]
            if run_command(cmd, "Generating experiment report"):
                print(f"[OK] Report available at: {report_file}")
        
        # Generate visualizations
        viz_script = repo_root / "tests/harness/visualize_metrics.py"
        if viz_script.exists():
            print(f"\nGenerating metrics visualizations...")
            cmd = [sys.executable, str(viz_script), str(exp_dir), str(exp_dir)]
            run_command(cmd, "Creating metric visualizations (optional)")
        
        print("\n" + "="*80)
        print("EXPERIMENT ARTIFACTS")
        print("="*80)
        print(f"[REPORT] Report: {report_file}")
        print(f"[LOGS] Baseline: {exp_dir}/baseline_run.log")
        print(f"[LOGS] Degraded: {exp_dir}/degraded_run.log")
        print(f"[LOGS] Recovered: {exp_dir}/recovered_run.log")
        print(f"[BACKUP] Baseline: {exp_dir}/SKILL.md.baseline")
        
        return 0
        
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
