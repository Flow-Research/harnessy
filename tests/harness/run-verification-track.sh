#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

WITH_LLM=0
WITH_GOAL_AGENT_E2E=0
WITH_REMOTE_BOOTSTRAP=0
SKIP_LOCAL=0
SKIP_CONTAINER=0

for arg in "$@"; do
  case "$arg" in
    --with-llm) WITH_LLM=1 ;;
    --with-goal-agent-e2e) WITH_GOAL_AGENT_E2E=1 ;;
    --with-remote-bootstrap) WITH_REMOTE_BOOTSTRAP=1 ;;
    --skip-local) SKIP_LOCAL=1 ;;
    --skip-container) SKIP_CONTAINER=1 ;;
    *) echo "Unknown flag: $arg" >&2; exit 1 ;;
  esac
done

echo "=== Flow Verification Track ==="
echo "Repo: $REPO_ROOT"
echo "Windows policy: WSL-supported"
echo "Local lane: $( [[ "$SKIP_LOCAL" == "1" ]] && echo skipped || echo enabled )"
echo "Container lane: $( [[ "$SKIP_CONTAINER" == "1" ]] && echo skipped || echo enabled )"
echo "LLM checks: $( [[ "$WITH_LLM" == "1" ]] && echo enabled || echo disabled )"
echo "Goal-agent real E2E: $( [[ "$WITH_GOAL_AGENT_E2E" == "1" ]] && echo enabled || echo disabled )"
echo "Remote bootstrap: $( [[ "$WITH_REMOTE_BOOTSTRAP" == "1" ]] && echo enabled || echo disabled )"

if [[ "$SKIP_LOCAL" != "1" ]]; then
  echo
  echo "--- Local isolated HOME evaluation ---"
  FLOW_EVAL_LLM_TESTS="$WITH_LLM" \
  FLOW_EVAL_GOAL_AGENT_E2E="$WITH_GOAL_AGENT_E2E" \
  bash "$SCRIPT_DIR/run-flow-install-eval.sh"
fi

if [[ "$SKIP_CONTAINER" != "1" ]]; then
  echo
  echo "--- Linux container install/sync verification ---"
  CI_FLAGS=()
  if [[ "$WITH_LLM" == "1" ]]; then
    CI_FLAGS+=(--with-claude --with-opencode)
  fi
  GOAL_AGENT_E2E="$WITH_GOAL_AGENT_E2E" \
  docker build -t harnessy-verify "$SCRIPT_DIR" >/dev/null
  DOCKER_CMD=(docker run --rm -v "$REPO_ROOT:/source/harnessy:ro" -e GOAL_AGENT_E2E="$WITH_GOAL_AGENT_E2E" harnessy-verify bash /source/harnessy/tests/harness/run-ci-verify.sh)
  if [[ ${#CI_FLAGS[@]} -gt 0 ]]; then
    DOCKER_CMD+=("${CI_FLAGS[@]}")
  fi
  "${DOCKER_CMD[@]}"
fi

if [[ "$WITH_REMOTE_BOOTSTRAP" == "1" ]]; then
  echo
  echo "--- Remote bootstrap docker evaluation ---"
  FLOW_REMOTE_EVAL_GOAL_AGENT_E2E="$WITH_GOAL_AGENT_E2E" \
  bash "$SCRIPT_DIR/run-remote-install-docker.sh"
fi

echo
echo "Verification track complete."
