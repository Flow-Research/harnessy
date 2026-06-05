#!/usr/bin/env bash
set -euo pipefail

if [ -n "${BUILD_E2E_SPEC_ROOT:-}" ]; then
  printf '%s\n' "${BUILD_E2E_SPEC_ROOT}"
  exit 0
fi

if [ -f "./.jarvis/context/profiles/ci.json" ]; then
  PROFILE_SPEC_ROOT="$(python3 - <<'PY'
import json
from pathlib import Path

profile = Path('.jarvis/context/profiles/ci.json')
try:
    data = json.loads(profile.read_text())
except Exception:
    data = {}

project = data.get('project', {})
value = project.get('specRoot', '') if isinstance(project, dict) else ''
if isinstance(value, str):
    print(value)
else:
    print('')
PY
)"
  if [ -n "${PROFILE_SPEC_ROOT}" ]; then
    printf '%s\n' "${PROFILE_SPEC_ROOT}"
    exit 0
  fi
fi

if [ -f "./.flow/delivery-profile.json" ]; then
  PROFILE_SPEC_ROOT="$(python3 - <<'PY'
import json
from pathlib import Path

profile = Path('.flow/delivery-profile.json')
try:
    data = json.loads(profile.read_text())
except Exception:
    data = {}

value = data.get('specRoot', '')
if isinstance(value, str):
    print(value)
else:
    print('')
PY
)"
  if [ -n "${PROFILE_SPEC_ROOT}" ]; then
    printf '%s\n' "${PROFILE_SPEC_ROOT}"
    exit 0
  fi
fi

if [ -d "./.jarvis/context/specs" ]; then
  printf '%s\n' "./.jarvis/context/specs"
  exit 0
fi

if [ -d "./specs" ]; then
  printf '%s\n' "./specs"
  exit 0
fi

printf '%s\n' "./specs"
