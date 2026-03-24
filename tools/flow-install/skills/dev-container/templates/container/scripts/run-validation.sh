#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC_PATH="${1:-${ROOT_DIR}/specs/dev-baseline.json}"
SOURCE_DIR="${2:-}"
BUILD_FIRST="${BUILD_FIRST:-1}"

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

SPEC_IN_IMAGE="$(python3 - "$ROOT_DIR" "$SPEC_PATH" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
spec = Path(sys.argv[2]).resolve()
print(Path('/opt/devcontainer') / spec.relative_to(root))
PY
)"

if [[ "$BUILD_FIRST" == "1" ]]; then
  "${ROOT_DIR}/scripts/build-image.sh" "$SPEC_PATH" "$IMAGE_TAG" >/dev/null
fi

DOCKER_ARGS=(--rm --init -w /workspace)

if [[ -n "$SOURCE_DIR" ]]; then
  SOURCE_DIR="$(cd "$SOURCE_DIR" && pwd)"
  DOCKER_ARGS+=( -v "${SOURCE_DIR}:/workspace" )
fi

docker run "${DOCKER_ARGS[@]}" \
  "$IMAGE_TAG" \
  python3 /opt/devcontainer/scripts/validate-container.py --spec "$SPEC_IN_IMAGE" --json
