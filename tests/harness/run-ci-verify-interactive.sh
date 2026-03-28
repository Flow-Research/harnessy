#!/usr/bin/env bash
set -euo pipefail

# Run Docker harness verification and keep the container alive for manual inspection.
#
# Usage (from repo root):
#   bash tests/harness/run-ci-verify-interactive.sh
#
# After verification completes (pass or fail), you'll be dropped into a bash shell
# inside the container. Explore freely:
#   ls ~/.agents/skills/
#   cat flow-install.lock.json
#   node scripts/flow/verify-harness.mjs
#   python3 ~/.agents/skills/_shared/run_metrics.py compute --skill issue-flow
#   exit  (stops and removes container)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
IMAGE_NAME="harnessy-verify"
CONTAINER_NAME="harnessy-verify-interactive"

echo "=== Building Docker image ==="
docker build -t "$IMAGE_NAME" "$SCRIPT_DIR"

# Remove any leftover container from a previous run
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

echo ""
echo "=== Running harness verification ==="
echo ""

# Run verification, capture exit code but don't exit on failure
docker run \
    --name "$CONTAINER_NAME" \
    -v "$REPO_ROOT:/source/harnessy:ro" \
    -e SKIP_COMMUNITY=1 \
    -it \
    "$IMAGE_NAME" \
    bash -c '
        echo "--- Running automated verification ---"
        echo ""
        /source/harnessy/tests/harness/run-ci-verify.sh
        RESULT=$?
        echo ""
        if [ $RESULT -eq 0 ]; then
            echo "=== VERIFICATION PASSED ==="
        else
            echo "=== VERIFICATION FAILED ($RESULT issues) ==="
        fi
        echo ""
        echo "Dropping into interactive shell. Explore freely:"
        echo "  ls ~/.agents/skills/"
        echo "  cat flow-install.lock.json"
        echo "  node scripts/flow/verify-harness.mjs"
        echo "  python3 ~/.agents/skills/_shared/run_metrics.py compute --skill issue-flow"
        echo "  exit  (stops container)"
        echo ""
        exec bash
    '

# Cleanup after exit
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
echo "Container removed."
