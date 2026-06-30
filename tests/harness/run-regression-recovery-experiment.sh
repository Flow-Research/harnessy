#!/usr/bin/env bash
###############################################################################
# Controlled Regression & Recovery Experiment Orchestrator
# 
# Thin wrapper around Python orchestrator (run_experiment.py) that provides
# bash script interface while delegating to robust Python implementation.
#
# Usage:
#   bash tests/harness/run-regression-recovery-experiment.sh [options]
#
# Options:
#   --skill SKILL_NAME           Target skill (default: engineer)
#   --injected-failure TYPE      Type: missing-step, corrupted-logic, incomplete-doc
#   --with-recovery BOOL         Enable auto-recovery (default: true)
#   --llm-provider PROVIDER      LLM: gemini (default), claude, gpt
#   --output-dir DIR             Output directory (default: .experiments)
#
# Returns: 0 on success, 1 on failure
###############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default values
SKILL_NAME="engineer"
FAILURE_TYPE="missing-step"
LLM_PROVIDER="gemini"
OUTPUT_DIR=".experiments"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skill) SKILL_NAME="$2"; shift 2 ;;
    --injected-failure) FAILURE_TYPE="$2"; shift 2 ;;
    --with-recovery) shift 2 ;; # Ignored, always enabled
    --llm-provider) LLM_PROVIDER="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# Verify Python orchestrator exists
if [[ ! -f "$REPO_ROOT/tests/harness/run_experiment.py" ]]; then
  echo "[ERROR] run_experiment.py not found at $REPO_ROOT/tests/harness/run_experiment.py" >&2
  exit 1
fi

# Find Python executable (prefer venv, fallback to system)
PYTHON_EXE=""
if [[ -f "$REPO_ROOT/.venv/Scripts/python" ]]; then
  PYTHON_EXE="$REPO_ROOT/.venv/Scripts/python"
elif [[ -f "$REPO_ROOT/.venv/Scripts/python.exe" ]]; then
  PYTHON_EXE="$REPO_ROOT/.venv/Scripts/python.exe"
elif command -v python3 &>/dev/null; then
  PYTHON_EXE="$(command -v python3)"
elif command -v python &>/dev/null; then
  PYTHON_EXE="$(command -v python)"
else
  echo "[ERROR] Python not found. Please ensure .venv is created." >&2
  exit 1
fi

# Run Python orchestrator with forwarded arguments
cd "$REPO_ROOT"
exec "$PYTHON_EXE" tests/harness/run_experiment.py \
  --skill "$SKILL_NAME" \
  --failure-type "$FAILURE_TYPE" \
  --llm-provider "$LLM_PROVIDER" \
  --output-dir "$OUTPUT_DIR"
