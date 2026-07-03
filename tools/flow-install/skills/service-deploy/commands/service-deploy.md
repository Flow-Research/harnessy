---
description: CI/profile-driven service deployment with Hostinger as the first provider adapter
argument-hint: "plan|check|configure|targets|ssh-setup|package|deploy|status|logs|rollback [--env <name>] [--json] [--dry-run] [--local-override]"
---

# Service Deploy Command

Use the installed `harness-deploy` command as the deterministic execution surface.

## Profile Inputs

Default lookup:

- CI profile: `.jarvis/context/profiles/ci.json`
- Deploy profile: `.jarvis/context/profiles/deploy.json`
- QA profile: value from CI profile, otherwise `.jarvis/context/profiles/qa.json`

## Commands

### `harness-deploy plan`

Read profiles and report:

- project and release policy
- selected environment
- app package targets
- runtime mode per app
- provider and adapter
- required gates
- evidence root

No provider calls are made.

### `harness-deploy check`

Validate profiles and run configured gate commands when present. Required gate
failure blocks deployment. Use this before package or deploy.

### `harness-deploy configure`

Create or validate a gitignored provider-local env file. For Hostinger, this
uses the active deploy profile target and writes:

```text
.jarvis/context/profiles/local/hostinger.env
```

The command never prints token values. It uses, in order:

- existing values from the local env file
- `HOSTINGER_API_TOKEN` or `HAPI_API_TOKEN` from the current shell
- an interactive hidden prompt, unless `--no-prompt` is set

The file is created with mode `0600`. General Harnessy install should not ask
for provider secrets; provider setup should be run explicitly when a deployment
capability needs it.

### `harness-deploy targets`

Load the local provider env file and list Hostinger VPS candidates using:

```bash
HAPI_API_TOKEN=$HOSTINGER_API_TOKEN hapi vps vm list --format json
```

This is a read-only discovery command. Use it to select or cache
`HOSTINGER_VPS_ID` after the API token is configured.

When exactly one VPS is returned, cache it in the local env file:

```bash
harness-deploy targets --write-selection
```

When multiple VPS instances exist, choose explicitly:

```bash
harness-deploy targets --target-id <id> --write-selection
```

### `harness-deploy ssh-setup`

For `systemd` and generic VPS process runtimes, Hostinger API handles discovery
but SSH performs the actual release installation. This command:

- reads the local Hostinger env file
- verifies the selected VPS target
- checks whether key-based root SSH works
- creates/attaches the local SSH public key through Hostinger's public-key API
  if needed
- verifies SSH again

Default public key path is `~/.ssh/id_rsa.pub`; override with:

```bash
harness-deploy ssh-setup --ssh-public-key ~/.ssh/id_ed25519.pub
```

For non-interactive deploys, prefer a dedicated gitignored deploy key:

```bash
harness-deploy ssh-setup --generate-ssh-key
```

This creates `.jarvis/context/profiles/local/hostinger_deploy_key` when needed,
writes `HOSTINGER_SSH_KEY` into the local Hostinger env file, installs the
matching public key on the deploy user, and makes later `ssh`/`scp` calls use
that key with `IdentitiesOnly=yes`.

For reusable VPS deployments, Harnessy uses a host-level deploy user. The
default is `harnessy-deploy`; app runtime users remain app-specific system users
such as `econ-sim`.

If Hostinger account-level key attachment does not enable key login on an
existing VPS, add `HOSTINGER_BOOTSTRAP_ROOT_PASSWORD` to the same gitignored
local env file. `ssh-setup` will use root once through `expect` to create the
deploy user, install the public key, and grant deployment sudo. Later deploys
use key-only SSH through `HOSTINGER_SSH_USER`.

### `harness-deploy package`

Create a tarball package under the deployment evidence root and write:

- `manifest.json`
- `package.sha256`

Packages must exclude `.env`, `.git`, `node_modules`, caches, and secret candidates.

## Runtime Modes

Deployment runtime is configurable per app in `.jarvis/context/profiles/deploy.json`.
Docker Compose is supported, but it is not mandatory.

Supported `runtime.mode` values:

- `docker-compose` — package and deploy a Compose project on a VPS/container host
- `systemd` — install or restart a long-running service on a VPS, usually behind NGINX/Caddy
- `static` — deploy static build output
- `node` or `node-managed` — deploy Node services or managed Node hosting targets
- `process` — generic long-running process supervised by the target platform
- `auto` — defer final runtime selection to the adapter/profile

Example Streamlit/systemd app:

```json
{
  "id": "econ-sim",
  "type": "python",
  "root": ".",
  "package": "auto",
  "runtime": {
    "mode": "systemd",
    "serviceName": "econ-sim",
    "workingDirectory": "/opt/econ-sim/current",
    "startCommand": "uv run streamlit run src/econ_sim/app.py --server.address 127.0.0.1 --server.port 8501",
    "port": 8501,
    "healthcheckPath": "/_stcore/health",
    "reverseProxy": "nginx"
  }
}
```

Example Docker Compose app:

```json
{
  "id": "econ-sim",
  "type": "python",
  "root": ".",
  "package": "auto",
  "runtime": {
    "mode": "docker-compose",
    "composeFile": "docker-compose.yml",
    "serviceName": "econ-sim",
    "healthcheckPath": "/_stcore/health"
  }
}
```

### `harness-deploy deploy`

Default behavior is safe:

- `--dry-run` records planned provider action only
- provider mode `mock` records a mock deployment for tests and fixtures
- live Hostinger `systemd` execution uses Hostinger API for target discovery and
  SSH/SCP for release installation, service restart, NGINX reload, and smoke
  checks
- runtime mode is read from the deploy profile, so local/process/systemd and
  Docker Compose deployments can share the same gate/package/evidence flow

Local execution requires `--local-override` when the CI profile requires it.

For Streamlit-style services, success requires both HTTP health and WebSocket
upgrade smoke checks. A reverse proxy can serve `/_stcore/health` and the HTML
page while still breaking the app if `/_stcore/stream` is rejected. Preserve the
full browser host, including nonstandard ports, with headers such as:

```nginx
proxy_set_header Host $http_host;
proxy_set_header X-Forwarded-Host $http_host;
```

### `harness-deploy status` and `harness-deploy logs`

Read stored evidence and summarize the latest or selected `--run-id`.

### `harness-deploy rollback`

Record rollback intent. Provider-native rollback may be added later; v1 rollback
is evidence-first and supports redeploying a previous package artifact when that
target is recorded.

## Hostinger Adapter V1

Hostinger is normalized behind Harnessy policy. Prefer scoped MCP tools:

- `hostinger-hosting-mcp` for managed static/Node targets
- `hostinger-vps-mcp` for VPS targets, including Docker Compose and systemd/process deployments

Do not expose billing, purchase, destructive delete, destructive backup restore,
or DNS mutation actions in v1.
