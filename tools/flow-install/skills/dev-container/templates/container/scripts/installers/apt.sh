#!/usr/bin/env bash
set -euo pipefail

ROOT="${DEVCONTAINER_ROOT:-/opt/devcontainer}"
FEATURE_PACKS_INPUT="${1:-${FEATURE_PACKS:-}}"
TMP_PACKAGES="/tmp/devcontainer-apt-packages.txt"
TMP_PIP_PACKAGES="/tmp/devcontainer-pip-packages.txt"
TMP_NPM_PACKAGES="/tmp/devcontainer-npm-packages.txt"

collect_packages() {
  local file_path="$1"
  if [[ ! -f "$file_path" ]]; then
    return 0
  fi
  grep -Ev '^[[:space:]]*(#|$)' "$file_path" || true
}

collect_packages "${ROOT}/baseline/apt.txt" >"${TMP_PACKAGES}"
collect_packages "${ROOT}/baseline/pip.txt" >"${TMP_PIP_PACKAGES}"
collect_packages "${ROOT}/baseline/npm.txt" >"${TMP_NPM_PACKAGES}"

IFS=',' read -ra FEATURES <<<"${FEATURE_PACKS_INPUT}"
for feature in "${FEATURES[@]}"; do
  feature_name="$(printf '%s' "$feature" | xargs)"
  [[ -z "$feature_name" ]] && continue
  feature_file="${ROOT}/features/${feature_name}/apt.txt"
  if [[ ! -f "$feature_file" ]]; then
    echo "Unknown feature pack for apt: ${feature_name}" >&2
    exit 1
  fi
  collect_packages "$feature_file" >>"${TMP_PACKAGES}"
done

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends $(tr '\n' ' ' < <(sort -u "${TMP_PACKAGES}"))
rm -rf /var/lib/apt/lists/*

if command -v corepack >/dev/null 2>&1; then
  corepack enable || true
  corepack prepare pnpm@latest --activate || true
fi

if [[ -s "${TMP_PIP_PACKAGES}" ]]; then
  python3 -m pip install --break-system-packages --no-cache-dir $(tr '\n' ' ' < <(sort -u "${TMP_PIP_PACKAGES}"))
fi

if [[ -s "${TMP_NPM_PACKAGES}" ]]; then
  npm install -g $(tr '\n' ' ' < <(sort -u "${TMP_NPM_PACKAGES}"))
fi
