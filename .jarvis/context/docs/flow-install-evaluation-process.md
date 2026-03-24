# Flow Install Evaluation Process

## Goal

Prove that Flow installation works end to end across local fixture installs and remote-style bootstrap installs, with evidence for Jarvis, scripts, context, AGENTS wiring, Flow skills, and community-skill parity across OpenCode and Claude.

## Exercise Summary

This evaluation exercise is now backed by executable harnesses and has been run successfully in both:

- isolated fixture-based installs
- remote-style Docker bootstrap installs using `curl ... install.sh`

The exercise also surfaced and fixed multiple harness defects:

1. custom install destinations were not fully respected by generated scripts or verification
2. AGENTS creation failed for nested custom paths because parent directories were not created
3. `install.sh` ran community-skill installation from the wrong working directory during bootstrap
4. Claude marketplace output was not loadable because the generated marketplace schema and source paths were wrong
5. Claude marketplace registration needed a real `known_marketplaces.json` entry plus a `skills/` subtree for installable plugin sources

## Evaluation Layers

### 1. Fixture-based acceptance

Run:

```bash
bash tests/harness/run-flow-install-eval.sh
```

Optional heavier mode:

```bash
FLOW_EVAL_FULL_COMMUNITY=1 bash tests/harness/run-flow-install-eval.sh
```

This validates:

- isolated-home Jarvis install
- isolated-home OpenCode CLI install
- isolated-home Claude CLI install
- base repo install
- rerun behavior
- project-local skill registration
- custom install-path support for AGENTS, context, skills, and scripts
- OpenCode can load a Flow core skill
- Claude can execute a Flow core slash skill
- OpenCode can load a project-local installed skill
- Claude can execute a project-local installed slash skill

### 2. Remote-style docker bootstrap

Run:

```bash
bash tests/harness/run-remote-install-docker.sh
```

This validates:

- `curl ... install.sh` bootstrap path inside Docker
- clone/install from a git snapshot of the current working tree
- Jarvis installation inside the container
- OpenCode CLI installation inside the container
- Claude CLI installation inside the container
- Flow install completion inside the container
- `pnpm harness:verify` after bootstrap
- community-skill install and parity checks through OpenCode/Claude registration artifacts
- OpenCode can load a Flow core skill inside the container
- OpenCode can load a community skill inside the container
- Claude can execute a Flow core slash skill inside the container
- Claude can execute a community slash skill inside the container

## Acceptance Criteria

The install is only considered acceptable when all of the following are true:

1. `install.sh` completes in non-interactive mode
2. `jarvis` is installed and executable
3. lifecycle scripts are installed in the target repo
4. context scaffold and memory scopes exist
5. `AGENTS.md` points to the installed context AGENTS file
6. `pnpm harness:verify` passes
7. Flow core skills are globally discoverable
8. project-local skills are discoverable when present
9. custom install destinations still pass verification
10. community-skill inventory can be installed and registered into Claude/OpenCode parity checks

## Verification Semantics

The current evaluation treats “can load a skill” as:

- **OpenCode:** successfully resolving and running the slash command so the run emits a task tool call
- **Claude:** successfully executing `claude -p "/skill-name"` after skill registration

Important nuance:

- OpenCode skill loading is validated by actual slash execution.
- Claude skill loading is validated by actual slash execution through `claude -p`.

## Current Executables

- `tests/harness/run-flow-install-eval.sh`
- `tests/harness/run-remote-install-docker.sh`

## Current Status

### Cleared

- [x] Jarvis installs in isolated environments
- [x] Flow installs into fresh fixture repos
- [x] Flow rerun behavior remains acceptable for `harness:verify`
- [x] project-local skill registration works
- [x] custom AGENTS/context/skills/scripts paths are supported and verifiable
- [x] remote-style Docker bootstrap via `install.sh` works
- [x] community-skill install works during bootstrap
- [x] OpenCode parity works for Flow core and community skills
- [x] Claude plugin parity works for Flow core and community skills
- [x] OpenCode CLI can load installed skills in evaluation runs
- [x] Claude CLI can load installed plugins in evaluation runs

### Remaining caveats

- [ ] true published GitHub bootstrap validation still needs a release-stage run against the public repo URL.

## Release Gate Recommendation

Before publishing a new Flow harness release:

1. Run `bash tests/harness/run-flow-install-eval.sh`
2. Run `bash tests/harness/run-remote-install-docker.sh`
3. If community changes are involved, rerun with full community coverage enabled
4. Review any warnings for PATH or managed-block drift before release

## Commands

```bash
pnpm harness:verify
pnpm harness:eval
pnpm harness:eval:remote
FLOW_EVAL_FULL_COMMUNITY=1 bash tests/harness/run-flow-install-eval.sh
FLOW_REMOTE_EVAL_FULL_COMMUNITY=1 bash tests/harness/run-remote-install-docker.sh
```
