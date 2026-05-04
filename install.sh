#!/usr/bin/env bash
set -euo pipefail

FLOW_REPO_URL="${FLOW_REPO_URL:-https://github.com/Flow-Research/harnessy.git}"
FLOW_INSTALL_DIR="${FLOW_INSTALL_DIR:-$HOME/harnessy}"
FLOW_CACHE_DIR="${FLOW_CACHE_DIR:-$HOME/.cache/harnessy}"
FLOW_NONINTERACTIVE="${FLOW_NONINTERACTIVE:-0}"
FLOW_SKIP_SUBPROJECTS="${FLOW_SKIP_SUBPROJECTS:-0}"

# Phase 6D: cloud bootstrap mode. When --from-cloud is set, install.sh skips
# all source-clone logic and runs the bootstrap CLI against a published
# Cloudflare Workers registry instead.
FLOW_FROM_CLOUD="${FLOW_FROM_CLOUD:-0}"
HARNESSY_WORKER_URL="${HARNESSY_WORKER_URL:-}"
HARNESSY_DEFAULT_WORKER_URL="${HARNESSY_DEFAULT_WORKER_URL:-https://harnessy-skill-registry.workers.dev}"
FLOW_BOOTSTRAP_RAW_URL="${FLOW_BOOTSTRAP_RAW_URL:-https://raw.githubusercontent.com/Flow-Research/harnessy/main/tools/flow-install/scripts/bootstrap.mjs}"

SCRIPT_SOURCE="${BASH_SOURCE[0]-$0}"
SCRIPT_DIR="$(cd -- "$(dirname -- "$SCRIPT_SOURCE")" && pwd)"
LOCAL_SOURCE=0
INSTALL_MODE="bootstrap"
TARGET_ROOT=""
INSTALL_COMMUNITY="auto"
FLOW_RECONFIGURE="${FLOW_RECONFIGURE:-0}"
FLOW_FORCE_SYNC="${FLOW_FORCE_SYNC:-0}"
FLOW_REFRESH_SOURCE="${FLOW_REFRESH_SOURCE:-0}"

if [[ -d "$SCRIPT_DIR/tools/flow-install" && -d "$SCRIPT_DIR/jarvis-cli" ]]; then
  LOCAL_SOURCE=1
fi

log() {
  printf '%s\n' "$1"
}

need_command() {
  command -v "$1" >/dev/null 2>&1
}

path_has_entry() {
  local needle="$1"
  local entry
  IFS=':' read -r -a path_entries <<<"${PATH:-}"
  for entry in "${path_entries[@]}"; do
    [[ "$entry" == "$needle" ]] && return 0
  done
  return 1
}

local_commands_dir() {
  if [[ -n "${XDG_BIN_HOME:-}" ]]; then
    printf '%s' "$XDG_BIN_HOME"
  else
    printf '%s' "$HOME/.local/bin"
  fi
}

usage() {
  cat <<'EOF'
Harnessy installer

Usage:
  ./install.sh [--here] [--target PATH] [--yes] [--reconfigure] [--refresh-source] [--no-community] [--community]
  ./install.sh --from-cloud [--worker-url URL]

Modes:
  default           Bootstrap a full Harnessy workspace locally
  --here            Install Harnessy into the current repository in-place
  --target PATH     Install Harnessy into the specified repository in-place
  --from-cloud      Install skills only, fetched directly from the published
                    cloud registry. No source repo clone, no Cloudflare login,
                    no maintainer privileges. Skills land in ~/.agents/skills/.

Flags:
  --yes             Non-interactive mode
  --force           Force-sync all skills (bypass version check)
  --refresh-source  Pull latest changes into the cached Harnessy source before install
  --reconfigure     Ask for install destinations again even if saved in lockfile
  --no-community    Skip community skill installation
  --community       Force community skill installation
  --worker-url URL  Override the default Worker URL for --from-cloud
                    (env: HARNESSY_WORKER_URL)
  --help            Show this help
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --here)
        INSTALL_MODE="in-place"
        TARGET_ROOT="$(pwd)"
        ;;
      --target)
        if [[ $# -lt 2 ]]; then
          log "[error] --target requires a path"
          exit 1
        fi
        INSTALL_MODE="in-place"
        TARGET_ROOT="$2"
        shift
        ;;
      --from-cloud)
        FLOW_FROM_CLOUD=1
        ;;
      --worker-url)
        if [[ $# -lt 2 ]]; then
          log "[error] --worker-url requires a URL"
          exit 1
        fi
        HARNESSY_WORKER_URL="$2"
        shift
        ;;
      --yes)
        FLOW_NONINTERACTIVE=1
        ;;
      --force)
        FLOW_FORCE_SYNC=1
        ;;
      --refresh-source)
        FLOW_REFRESH_SOURCE=1
        ;;
      --reconfigure)
        FLOW_RECONFIGURE=1
        ;;
      --no-community)
        INSTALL_COMMUNITY="0"
        ;;
      --community)
        INSTALL_COMMUNITY="1"
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      *)
        log "[error] Unknown argument: $1"
        usage
        exit 1
        ;;
    esac
    shift
  done

  if [[ "$INSTALL_MODE" == "in-place" ]]; then
    TARGET_ROOT="$(cd "$TARGET_ROOT" && pwd)"
  fi
  if [[ "$INSTALL_COMMUNITY" == "auto" ]]; then
    INSTALL_COMMUNITY="1"
  fi
}

run_from_cloud() {
  if ! need_command node; then
    log "[error] node is required for --from-cloud installs. Install Node 18+ and rerun."
    exit 1
  fi

  local worker_url="${HARNESSY_WORKER_URL:-$HARNESSY_DEFAULT_WORKER_URL}"
  if [[ -z "$worker_url" ]]; then
    log "[error] No Worker URL configured. Set --worker-url or HARNESSY_WORKER_URL."
    exit 1
  fi

  log "[info] Cloud bootstrap mode"
  log "  worker: $worker_url"

  local bootstrap_path
  if [[ "$LOCAL_SOURCE" -eq 1 ]]; then
    bootstrap_path="$SCRIPT_DIR/tools/flow-install/scripts/bootstrap.mjs"
    log "  using local bootstrap script: $bootstrap_path"
  else
    if ! need_command curl; then
      log "[error] curl is required to fetch the bootstrap script in cloud mode."
      exit 1
    fi
    mkdir -p "$FLOW_CACHE_DIR"
    bootstrap_path="$FLOW_CACHE_DIR/bootstrap.mjs"
    log "  fetching bootstrap script: $FLOW_BOOTSTRAP_RAW_URL"
    curl -fsSL "$FLOW_BOOTSTRAP_RAW_URL" -o "$bootstrap_path"
  fi

  HARNESSY_WORKER_URL="$worker_url" node "$bootstrap_path" --worker-url "$worker_url"

  log ""
  log "Cloud install complete."
  log "  Skills: $HOME/.agents/skills"
  log "  Lockfile: $FLOW_CACHE_DIR/skill-registry.lock.json"
  log ""
  log "To verify integrity later: node <path-to-bootstrap.mjs> --dry-run --worker-url \"$worker_url\""
}

install_uv() {
  if need_command uv; then
    log "[ok] uv already installed"
    return
  fi

  log "[info] Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
}

ensure_node_and_pnpm() {
  if ! need_command node; then
    log "[error] node is required for Harnessy installation. Install Node 18+ and rerun."
    exit 1
  fi

  if need_command pnpm; then
    log "[ok] pnpm already installed"
    return
  fi

  if need_command corepack; then
    log "[info] Enabling pnpm via corepack..."
    corepack enable pnpm >/dev/null 2>&1 || true
    corepack prepare pnpm@9.15.4 --activate >/dev/null 2>&1 || true
  fi

  if ! need_command pnpm; then
    log "[error] pnpm is required for Harnessy installation. Install pnpm and rerun."
    exit 1
  fi
}

resolve_flow_source() {
  if [[ "$LOCAL_SOURCE" -eq 1 ]]; then
    FLOW_ROOT="$SCRIPT_DIR"
    local source_root cache_root
    source_root="$(cd "$FLOW_ROOT" && pwd)"
    cache_root="$FLOW_CACHE_DIR"
    if [[ -d "$cache_root" ]]; then
      cache_root="$(cd "$cache_root" && pwd)"
    fi

    if [[ "$FLOW_REFRESH_SOURCE" == "1" && -d "$FLOW_ROOT/.git" && "$source_root" == "$cache_root" ]]; then
      log "[info] Refreshing cached Harnessy checkout at $FLOW_ROOT"
      git -C "$FLOW_ROOT" pull --ff-only
    fi

    log "[ok] Using local Harnessy checkout: $FLOW_ROOT"
    return
  fi

  if [[ "$INSTALL_MODE" == "in-place" ]]; then
    FLOW_ROOT="$FLOW_CACHE_DIR"
  else
    FLOW_ROOT="$FLOW_INSTALL_DIR"
  fi

  if [[ -d "$FLOW_ROOT/.git" ]]; then
    log "[info] Updating existing Harnessy checkout at $FLOW_ROOT"
    git -C "$FLOW_ROOT" pull --ff-only
  else
    mkdir -p "$(dirname "$FLOW_ROOT")"
    log "[info] Cloning Harnessy into $FLOW_ROOT"
    git clone "$FLOW_REPO_URL" "$FLOW_ROOT"
  fi
}

install_jarvis() {
  log "[info] Installing Jarvis CLI into PATH"
  uv tool install --force "$FLOW_ROOT/jarvis-cli"
}

install_flow_framework() {
  local flow_args=()
  if [[ "$FLOW_NONINTERACTIVE" == "1" ]]; then
    flow_args+=(--yes)
  fi
  if [[ "$FLOW_RECONFIGURE" == "1" ]]; then
    flow_args+=(--reconfigure)
  fi
  if [[ "$FLOW_FORCE_SYNC" == "1" ]]; then
    flow_args+=(--force)
  fi

  # When running via curl | bash, stdin is the pipe not the terminal.
  # Redirect stdin from /dev/tty so interactive prompts work.
  local use_tty=0
  if [[ ! -t 0 ]] && [[ -e /dev/tty ]] && [[ "$FLOW_NONINTERACTIVE" != "1" ]]; then
    use_tty=1
  fi

  if [[ "$INSTALL_MODE" == "in-place" ]]; then
    log "[info] Installing Harnessy framework into target repo: $TARGET_ROOT"
    if [[ "$use_tty" == "1" ]]; then
      node "$FLOW_ROOT/tools/flow-install/index.mjs" "${flow_args[@]}" --target "$TARGET_ROOT" </dev/tty
    else
      node "$FLOW_ROOT/tools/flow-install/index.mjs" "${flow_args[@]}" --target "$TARGET_ROOT"
    fi
    return
  fi

  log "[info] Installing Harnessy framework into project root"
  (
    cd "$FLOW_ROOT"
    if [[ "$use_tty" == "1" ]]; then
      node tools/flow-install/index.mjs "${flow_args[@]}" </dev/tty
    else
      node tools/flow-install/index.mjs "${flow_args[@]}"
    fi
  )
}

install_community_skills() {
  if [[ "$INSTALL_COMMUNITY" != "1" ]]; then
    log "[skip] Skipping community skill installation"
    return
  fi

  local installer="$FLOW_ROOT/tools/flow-install/skills/community-skills-install/scripts/main.js"
  local install_context="$FLOW_ROOT"
  if [[ "$INSTALL_MODE" == "in-place" ]]; then
    install_context="$TARGET_ROOT"
  fi
  if [[ -f "$installer" ]]; then
    log "[info] Installing community skills"
    (
      cd "$install_context"
      node "$installer" --full
    )
  else
    log "[warn] Community skills installer not found at $installer"
  fi
}

clone_subprojects() {
  if [[ "$INSTALL_MODE" == "in-place" ]]; then
    log "[skip] In-place install selected; not cloning bundled sub-projects"
    return
  fi

  if [[ "$FLOW_SKIP_SUBPROJECTS" == "1" ]]; then
    log "[skip] Skipping bundled sub-project clone"
    return
  fi

  if [[ "$LOCAL_SOURCE" -eq 1 ]]; then
    log "[skip] Local checkout detected; not cloning sub-projects"
    return
  fi

  if [[ "$FLOW_NONINTERACTIVE" != "1" ]]; then
    log "[skip] No bundled sub-project repositories to clone"
    return
  fi

  log "[skip] No bundled sub-project repositories to clone"
}

print_summary() {
  local installed_root="$FLOW_ROOT"
  if [[ "$INSTALL_MODE" == "in-place" ]]; then
    installed_root="$TARGET_ROOT"
  fi

  log ""
  log "Harnessy installation complete"
  log "- Installer source: $FLOW_ROOT"
  log "- Install target: $installed_root"
  log "- Jarvis: $(command -v jarvis || printf 'not found')"
  log "- Shared skills: $HOME/.agents/skills"
  log "- Terminal command shims: $(local_commands_dir)"
  log "- Lifecycle scripts: $HOME/.scripts"
  if ! path_has_entry "$(local_commands_dir)"; then
    log "- PATH warning: add '$(local_commands_dir)' to your shell PATH for Harnessy-installed commands"
  fi
  log ""
  log "Next steps:"
  log "1. Review .jarvis/context/ and fill in project-specific context files"
  log "2. Run 'pnpm skills:register' or 'npm run skills:register' in any project with local .agents/skills/"
  log "3. Run 'jarvis status' to verify the CLI install"
}

main() {
  parse_args "$@"

  if [[ "$FLOW_FROM_CLOUD" == "1" ]]; then
    run_from_cloud
    return
  fi

  install_uv
  ensure_node_and_pnpm
  resolve_flow_source
  install_jarvis
  install_flow_framework
  install_community_skills
  clone_subprojects
  print_summary
}

main "$@"
