#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

cd "$ROOT_DIR"

python3 -m py_compile "tools/flow-install/skills/_shared/attribute.py"
python3 -m py_compile "tools/flow-install/skills/_shared/attribute_validate.py"
PYTHONPATH="tools/flow-install/skills/_shared" python3 -m pytest \
  "tools/flow-install/tests/test_attribute.py" \
  "tools/flow-install/tests/test_attribute_validate.py" \
  --cov=attribute \
  --cov=attribute_validate \
  --cov-report=term-missing
