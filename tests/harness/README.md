# Harnessy Install Evaluation

This directory contains the executable evaluation harness for Harnessy installation.

## Verification Track

Run the combined verification track:

```bash
bash tests/harness/run-verification-track.sh
```

Optional heavier modes:

```bash
bash tests/harness/run-verification-track.sh --with-llm --with-goal-agent-e2e
bash tests/harness/run-verification-track.sh --with-remote-bootstrap
```

Platform strategy:

- macOS: use `run-flow-install-eval.sh` via `run-verification-track.sh`
- Linux: use `run-ci-verify.sh` and `run-remote-install-docker.sh`
- Windows: WSL-supported only for now; run the same Bash entrypoints inside WSL

## Local evaluation

Run the fixture-based acceptance checks in an isolated temp HOME:

```bash
bash tests/harness/run-flow-install-eval.sh
```

This validates:

- Jarvis CLI installation in an isolated user home
- OpenCode CLI installation in an isolated user home
- Claude CLI installation in an isolated user home
- Codex skill registration in an isolated user home
- Harnessy install into a base fixture repo
- rerun behavior against the same fixture
- local project skill registration and parity
- local project Codex registration parity
- custom install path support for AGENTS, context, skills, and scripts
- OpenCode can execute a Harnessy core slash skill
- Claude can execute a Harnessy core slash skill
- OpenCode can execute a project-local installed skill
- Claude can execute a project-local installed slash skill
- goal-agent command is installed and available in isolated HOME
- goal-agent deterministic verification passes (setup, guard, approve, learn, meta-goal bootstrap)

Optional real worker-driven goal-agent E2E:

```bash
FLOW_EVAL_LLM_TESTS=1 FLOW_EVAL_GOAL_AGENT_E2E=1 bash tests/harness/run-flow-install-eval.sh
```

That additionally runs `/goal-agent run ...` through `claude -p` and verifies the worker-created artifact.

Optional heavier mode:

```bash
FLOW_EVAL_FULL_COMMUNITY=1 bash tests/harness/run-flow-install-eval.sh
```

That installs and verifies the full community skill inventory in the isolated HOME before running `harness:verify`.

## Remote-install docker evaluation

Run a clean-room bootstrap using `curl ... install.sh` inside Docker:

```bash
bash tests/harness/run-remote-install-docker.sh
```

How it works:

- scaffolds an external `dev-container` bundle under `~/containers/harnessy/install-eval`
- builds a container image from that bundle
- snapshots the current working tree into a temporary git repo
- serves the snapshot over a local HTTP server so the bootstrap path uses `curl`
- points `FLOW_REPO_URL` at the git snapshot for remote-style cloning
- runs `jarvis --help` and `pnpm harness:verify` inside the container
- runs deterministic goal-agent verification inside the container
- installs `opencode` and `claude` inside the container
- verifies Codex directory registration for both Harnessy core and community skills
- verifies OpenCode can execute both a Harnessy core skill and a community skill
- verifies Claude can execute both a Harnessy core slash skill and a community slash skill

Optional real worker-driven goal-agent E2E in the clean-room container:

```bash
FLOW_REMOTE_EVAL_GOAL_AGENT_E2E=1 bash tests/harness/run-remote-install-docker.sh
```

Optional heavier mode:

```bash
FLOW_REMOTE_EVAL_FULL_COMMUNITY=1 bash tests/harness/run-remote-install-docker.sh
```

That additionally installs the full community skill set in the container before re-running `harness:verify`.

## Notes

- The remote docker evaluator does not require pushing this repo to GitHub.
- OpenCode loadability is verified by actual slash execution.
- Claude slash execution is verified through `claude -p "/skill-name"` after registration.
- Codex is currently verified through directory-based skill registration under `~/.codex/skills/harnessy/`, while OpenCode and Claude have execution-level checks in the harness lanes.
- Goal-agent deterministic checks are always part of the harness lanes.
- Goal-agent real worker-driven E2E is opt-in because it requires authenticated Claude execution.
- True hosted remote-install validation against GitHub should still be run before release.
