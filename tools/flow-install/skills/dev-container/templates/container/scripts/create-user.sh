#!/usr/bin/env bash
set -euo pipefail

PACKAGE_MANAGER="${1:?package manager required}"
DEV_USERNAME="${2:?username required}"
DEV_UID="${3:?uid required}"
DEV_GID="${4:?gid required}"
ENABLE_SUDO="${5:-true}"

case "$PACKAGE_MANAGER" in
  apk)
    addgroup -S wheel || true
    addgroup -g "$DEV_GID" "$DEV_USERNAME"
    adduser -D -u "$DEV_UID" -G "$DEV_USERNAME" -s /bin/bash "$DEV_USERNAME"
    if [[ "$ENABLE_SUDO" == "true" ]]; then
      addgroup "$DEV_USERNAME" wheel
      mkdir -p /etc/sudoers.d
      printf '%%wheel ALL=(ALL) NOPASSWD: ALL\n' >/etc/sudoers.d/wheel
      chmod 0440 /etc/sudoers.d/wheel
    fi
    ;;
  apt)
    groupadd --gid "$DEV_GID" "$DEV_USERNAME"
    useradd --uid "$DEV_UID" --gid "$DEV_GID" --create-home --shell /bin/bash "$DEV_USERNAME"
    if [[ "$ENABLE_SUDO" == "true" ]]; then
      groupadd sudo || true
      usermod -aG sudo "$DEV_USERNAME"
      printf '%%sudo ALL=(ALL) NOPASSWD: ALL\n' >/etc/sudoers.d/devcontainer
      chmod 0440 /etc/sudoers.d/devcontainer
    fi
    ;;
  *)
    echo "Unsupported package manager for user creation: $PACKAGE_MANAGER" >&2
    exit 1
    ;;
esac
