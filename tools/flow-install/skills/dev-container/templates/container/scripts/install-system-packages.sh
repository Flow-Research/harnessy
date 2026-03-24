#!/usr/bin/env bash
set -euo pipefail

ROOT="${DEVCONTAINER_ROOT:-/opt/devcontainer}"
PACKAGE_MANAGER="${1:-${PACKAGE_MANAGER:-}}"
FEATURE_PACKS_INPUT="${2:-${FEATURE_PACKS:-}}"

if [[ -z "$PACKAGE_MANAGER" ]]; then
  echo "PACKAGE_MANAGER is required" >&2
  exit 1
fi

exec "${ROOT}/scripts/installers/${PACKAGE_MANAGER}.sh" "$FEATURE_PACKS_INPUT"
