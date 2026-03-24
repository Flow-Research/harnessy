#!/usr/bin/env bash
set -euo pipefail

ROOT="${DEVCONTAINER_ROOT:-/opt/devcontainer}"
FEATURE_PACKS_INPUT="${1:-${FEATURE_PACKS:-}}"
TMP_PACKAGES="/tmp/devcontainer-apk-packages.txt"
TMP_PIP_PACKAGES="/tmp/devcontainer-pip-packages.txt"
TMP_NPM_PACKAGES="/tmp/devcontainer-npm-packages.txt"

collect_packages() {
  local file_path="$1"
  if [[ ! -f "$file_path" ]]; then
    return 0
  fi
  grep -Ev '^[[:space:]]*(#|$)' "$file_path" || true
}

collect_packages "${ROOT}/baseline/apk.txt" >"${TMP_PACKAGES}"
collect_packages "${ROOT}/baseline/pip.txt" >"${TMP_PIP_PACKAGES}"
collect_packages "${ROOT}/baseline/npm.txt" >"${TMP_NPM_PACKAGES}"

IFS=',' read -ra FEATURES <<<"${FEATURE_PACKS_INPUT}"
for feature in "${FEATURES[@]}"; do
  feature_name="$(printf '%s' "$feature" | xargs)"
  [[ -z "$feature_name" ]] && continue
  feature_file="${ROOT}/features/${feature_name}/apk.txt"
  if [[ ! -f "$feature_file" ]]; then
    echo "Unknown feature pack for apk: ${feature_name}" >&2
    exit 1
  fi
  collect_packages "$feature_file" >>"${TMP_PACKAGES}"
done

sort -u "${TMP_PACKAGES}" >"${TMP_PACKAGES}.sorted"
apk add --no-cache $(tr '\n' ' ' <"${TMP_PACKAGES}.sorted")

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
