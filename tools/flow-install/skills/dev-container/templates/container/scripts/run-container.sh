#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC_PATH="${1:-${ROOT_DIR}/specs/dev-baseline.json}"
SOURCE_DIR="${2:-}"

if [[ ! -f "$SPEC_PATH" ]]; then
  echo "Missing spec file: $SPEC_PATH" >&2
  exit 1
fi

IMAGE_TAG="$(python3 - "$SPEC_PATH" <<'PY'
import json
import sys

with open(sys.argv[1], 'r', encoding='utf8') as handle:
    spec = json.load(handle)
print(spec.get('build', {}).get('image_tag', 'dev-container:latest'))
PY
)"

DOCKER_ARGS=(--rm --init -it -w /workspace)

if [[ -n "$SOURCE_DIR" ]]; then
  SOURCE_DIR="$(cd "$SOURCE_DIR" && pwd)"
  DOCKER_ARGS+=( -v "${SOURCE_DIR}:/workspace" )
fi

docker run "${DOCKER_ARGS[@]}" \
  "$IMAGE_TAG" \
  bash
