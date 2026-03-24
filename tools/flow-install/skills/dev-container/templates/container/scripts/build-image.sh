#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC_PATH="${1:-${ROOT_DIR}/specs/dev-baseline.json}"
IMAGE_TAG_OVERRIDE="${2:-}"

if [[ ! -f "$SPEC_PATH" ]]; then
  echo "Missing spec file: $SPEC_PATH" >&2
  exit 1
fi

read_spec() {
  python3 - "$SPEC_PATH" "$1" <<'PY'
import json
import sys

spec_path, field = sys.argv[1], sys.argv[2]
with open(spec_path, 'r', encoding='utf8') as handle:
    spec = json.load(handle)

build = spec.get('build', {})
user = spec.get('user', {})
if field == 'features':
    print(','.join(build.get('feature_packs', [])))
elif field == 'tag':
    print(build.get('image_tag', 'dev-container:latest'))
elif field == 'base_image':
    print(build.get('base_image', 'debian:bookworm-slim'))
elif field == 'package_manager':
    print(build.get('package_manager', 'apt'))
elif field == 'user':
    print(user.get('name', 'dev'))
elif field == 'uid':
    print(user.get('uid', 1000))
elif field == 'gid':
    print(user.get('gid', 1000))
elif field == 'enable_sudo':
    print(str(user.get('enable_sudo', True)).lower())
PY
}

FEATURE_PACKS="$(read_spec features)"
IMAGE_TAG="${IMAGE_TAG_OVERRIDE:-$(read_spec tag)}"
BASE_IMAGE="$(read_spec base_image)"
PACKAGE_MANAGER="$(read_spec package_manager)"
DEV_USERNAME="$(read_spec user)"
DEV_UID="$(read_spec uid)"
DEV_GID="$(read_spec gid)"
ENABLE_SUDO="$(read_spec enable_sudo)"

docker build \
  -f "${ROOT_DIR}/Dockerfile" \
  --build-arg BASE_IMAGE="$BASE_IMAGE" \
  --build-arg PACKAGE_MANAGER="$PACKAGE_MANAGER" \
  --build-arg FEATURE_PACKS="$FEATURE_PACKS" \
  --build-arg DEV_USERNAME="$DEV_USERNAME" \
  --build-arg DEV_UID="$DEV_UID" \
  --build-arg DEV_GID="$DEV_GID" \
  --build-arg ENABLE_SUDO="$ENABLE_SUDO" \
  -t "$IMAGE_TAG" \
  "$ROOT_DIR"

echo "$IMAGE_TAG"
