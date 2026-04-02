#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${1:-$(pwd)}"
SOURCE_ROOT="${FLOW_HARNESS_SOURCE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
GOAL_AGENT_E2E="${GOAL_AGENT_E2E:-0}"

pass() { echo "PASS goal-agent: $*"; }
fail() { echo "FAIL goal-agent: $*" >&2; exit 1; }

assert_file() {
  local file="$1"
  [[ -f "$file" ]] || fail "missing file $file"
}

assert_dir() {
  local dir="$1"
  [[ -d "$dir" ]] || fail "missing directory $dir"
}

json_field() {
  local file="$1"
  local expr="$2"
  python3 - "$file" "$expr" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
expr = sys.argv[2].split('.')
value = data
for part in expr:
    value = value[part]
print(value)
PY
}

main() {
  cd "$TARGET_DIR"

  command -v goal-agent >/dev/null 2>&1 || fail "goal-agent command is not available on PATH"
  pass "goal-agent command available"

  local templates_dir="$HOME/.agents/skills/goal-agent/templates"
  if [[ ! -d "$templates_dir" && -d "$SOURCE_ROOT/tools/flow-install/skills/goal-agent/templates" ]]; then
    templates_dir="$SOURCE_ROOT/tools/flow-install/skills/goal-agent/templates"
  fi

  local trivial_goal="$templates_dir/test-trivial-goal.md"
  [[ -f "$trivial_goal" ]] || fail "missing trivial goal template"

  local setup_json
  setup_json="$(mktemp /tmp/goal-agent-setup-XXXXXX)"
  goal-agent run "$trivial_goal" --setup-only > "$setup_json"
  local run_id state_dir
  run_id="$(json_field "$setup_json" run_id)"
  state_dir="$(json_field "$setup_json" state_dir)"
  assert_file "$state_dir/identity.json"
  assert_file "$state_dir/runtime-policy.json"
  assert_file "$state_dir/state.json"
  assert_file "$state_dir/prepared-goal.md"
  pass "setup-only writes identity, runtime policy, state, and prepared goal"

  if goal-agent guard "$run_id" --tool Write --target src/app.ts >/dev/null 2>&1; then
    fail "runtime policy unexpectedly allowed orchestrator write to application file"
  fi
  goal-agent guard "$run_id" --tool Write --target ".goal-agent/$run_id/current-prompt.md" >/dev/null
  pass "runtime policy blocks app writes and allows state writes"

  local auto_goal="$TARGET_DIR/.harness-goal-agent-auto-verify.md"
  cat > "$auto_goal" <<'EOF'
# Goal: Auto verify harness check

## Objective

Create `demo.py` and mention JWT in the output.

## Constraints

- Auto verify: true

## Verification

### Commands

```bash
test -f demo.py
```
EOF

  local auto_json
  auto_json="$(mktemp /tmp/goal-agent-auto-XXXXXX)"
  goal-agent run "$auto_goal" --setup-only > "$auto_json"
  local auto_run auto_state_dir
  auto_run="$(json_field "$auto_json" run_id)"
  auto_state_dir="$(json_field "$auto_json" state_dir)"
  goal-agent approve "$auto_run" --approve-all >/dev/null
  grep -q "Approved Auto Verification" "$auto_state_dir/prepared-goal.md" || fail "prepared-goal.md missing approved auto verification section"
  pass "auto verification approval persists to run state"

  local chain_goal="$TARGET_DIR/.harness-goal-chain.meta.yaml"
  cat > "$chain_goal" <<'EOF'
title: "Harness goal chain"
objective: "Verify chain setup"
sub_goals:
  - id: first
    goal_file: first.md
    depends_on: []
  - id: second
    goal_file: second.md
    depends_on:
      - goal: first
constraints:
  max_total_budget_usd: 12
  allow_parallel_goals: false
EOF

  local chain_json
  chain_json="$(mktemp /tmp/goal-agent-chain-XXXXXX)"
  goal-agent run "$chain_goal" --setup-only > "$chain_json"
  local chain_state_dir
  chain_state_dir="$(json_field "$chain_json" state_dir)"
  assert_file "$chain_state_dir/artifact-registry.json"
  assert_dir "$chain_state_dir/prepared-goals"
  pass "meta-goal setup writes chain state artifacts"

  python3 - "$state_dir/state.json" <<'PY'
import json, sys
path = sys.argv[1]
state = json.load(open(path))
state["phases"] = [{"name": "Phase 1", "status": "completed", "iterations": 1, "prompt_pattern": "task-with-context"}]
state["cumulative_spend_usd"] = 1.25
json.dump(state, open(path, "w"), indent=2)
open(path, "a").write("\n")
PY
  goal-agent record-outcome "$run_id" --strategy default >/dev/null
  goal-agent learn >/dev/null
  assert_file ".goal-agent/.learning/registry.json"
  pass "learning registry generated from recorded outcome"

  if [[ "$GOAL_AGENT_E2E" == "1" ]]; then
    command -v claude >/dev/null 2>&1 || fail "GOAL_AGENT_E2E=1 requires claude on PATH"
    rm -f greeting.txt
    local output_file
    output_file="$(mktemp /tmp/goal-agent-e2e-XXXXXX)"
    claude -p "/goal-agent run $trivial_goal" > "$output_file"
    grep -q "Hello from goal-agent!" greeting.txt || fail "worker-driven goal-agent run did not create greeting.txt"
    pass "real worker-driven end-to-end goal-agent run created greeting.txt"
  fi
}

main "$@"
