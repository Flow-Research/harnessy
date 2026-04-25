# Skill Registry Migration — Cloudflare Artifacts

Tracker for the work to move skill distribution from a single GitHub-cloned repo to a Cloudflare Artifacts–backed registry, where each skill is its own versioned Git repository.

Updated at the end of every phase.

## Why this exists

The end-state we want: someone who hears about Harnessy can run a single bootstrap command and have all the skills installed locally — without cloning this repo, without copying skill folders, without being a Harnessy maintainer. Skills live in the cloud; getting them is `curl | bash` simple.

That splits the problem into two roles:

| Role | What they do | Auth they need |
|---|---|---|
| **Publisher** (maintainer) | Pushes new skills + versions up to the registry | Bearer token, scoped writes |
| **Consumer** (anyone) | Pulls skills down to their machine | Public read — no Cloudflare account, no token |

Phases 1–5 built the publisher side and the verification primitives. The consumer side (the actual "easy install") is **Phase 6 — not yet implemented**. See [Honest status](#honest-status) below.

## Goals

- Each skill becomes an independently versioned Git repo, addressable by `flow/<name>@<semver>` and pinned by SHA.
- The installer resolves skills through a registry interface so backends are swappable (local now, Artifacts next, IPFS/git-over-libp2p later).
- Lockfile records the SHA every install pinned, so re-installs are byte-identical and verifiable across environments.
- A consumer can install a published skill set with no source-repo clone and no Cloudflare credentials.

## Conventions

| Thing | Value |
|---|---|
| Registry namespace | `flow` |
| Skill ref format | `flow/<name>@<semver>` (or `flow/<name>@<sha>` for pinning) |
| Per-skill backend selector | `registry: local \| artifacts` field in `harnessy.lock.json` |
| JS test runner | `node:test` (zero deps, Node 18+) |
| Python test runner | `pytest` (existing convention) |
| Working style | TDD — failing test first, then implementation |

## Phase status

| # | Phase | Status |
|---|---|---|
| 0 | External prereqs + naming locked | Done (external) |
| 1 | Registry abstraction (interface + local backend + artifacts stub) | Done |
| 2 | Management Worker (create-skill + mint-token endpoints) | Done |
| 3 | Publish flow (skill-publish wires through Worker, lockfile records SHA) | Done |
| 4 | Install/resolve flow (eager git clone now, ArtifactFS later) | Done |
| 5 | Verification + P2P story (lockfile-fidelity check, signed refs) | Done |
| 6 | Consumer install flow (public lockfile + bootstrap CLI) | **Pending — required for the original goal** |

## Honest status

What works today (verified by 85 tests, all green) — against **local file://-style remotes** with real git but a fake "registry":

1. `node tools/flow-install/scripts/publish-skill.mjs <name> --version X.Y.Z` provisions the repo, pushes the skill via real git, computes the content manifest, writes `skill-registry.lock.json`.
2. `new ArtifactsRegistry({lockfilePath, cacheDir})` resolves and clones any published skill, verifies SHA, returns the dir + manifest.
3. `node tools/flow-install/scripts/verify-skills.mjs` re-checks installed skills against their lockfile manifest.

What's blocked on **5 RECONCILE points** — assumptions about the Cloudflare Artifacts SDK that need real-world verification:

| # | Where | What to verify |
|---|---|---|
| 1 | `services/skill-registry/wrangler.toml` | `[[artifacts]]` stanza key + fields |
| 2 | `services/skill-registry/src/index.mjs` | `env.ARTIFACTS.create()` shape, idempotency |
| 3 | same | `repo.createToken(access, ttlSeconds)` signature |
| 4 | `tools/flow-install/lib/registry/publish-skill.mjs` | `authedPushUrl` auth scheme for git push |
| 5 | `tools/flow-install/lib/registry/registry-artifacts.mjs` | `authedFetchUrl` auth scheme for git clone |

All five fail loudly, none corrupt data, and all are localized to one or two functions. They surface immediately on `wrangler deploy` (#1) or first live publish (#2-5).

What's **deliberately deferred** (not blocking the original goal):

- ArtifactFS lazy mount — eager git clone is fine until the catalog is large.
- Lockfile-fidelity harness lane — primitives exist (`computeContentManifest`); wiring to `tests/harness/run-verification-track.sh` is small and additive.
- Slash skill update — `tools/flow-install/skills/skill-publish/SKILL.md` still describes the pre-Artifacts catalog workflow. Best updated after the CLI is proven against a real Worker.
- Default-flip — `installSkills` still defaults to `LocalRegistry`. Should wait until at least one skill has gone end-to-end against a real deployed Worker.

What's **missing for the consumer goal** (and why Phase 6 exists):

1. **No public lockfile distribution.** A fresh consumer has no way to discover what's published without cloning the publisher's repo.
2. **No public read access.** The Worker requires the bearer token for every endpoint, including token minting. A consumer shouldn't need a token at all.
3. **No bootstrap CLI.** Nothing exists today that says "given an empty machine, fetch the lockfile, fetch each skill, install to `~/.agents/skills/`."

Phase 6 closes those three gaps.

## Phase 0 — Prereqs (done)

External actions the user owns; not in this repo:

- Cloudflare account with Workers + Artifacts (beta) enabled.
- `wrangler` installed and `wrangler login` complete.
- API token scoped for Workers Scripts:Edit + Artifacts.

Naming locked:

- Namespace `flow`, ref `flow/<name>@<semver>`.
- Lockfile field `registry` per skill (default `local` until migrated).

## Phase 1 — Registry abstraction (done)

**Created:**
- `tools/flow-install/lib/registry/registry.mjs` — `Registry` base class, `REGISTRY_NAMESPACE`, `formatRef`, `parseRef`.
- `tools/flow-install/lib/registry/registry-local.mjs` — `LocalRegistry`, scans `tools/flow-install/skills/`, exposes `list()` and `fetch()`. Filters `_`-prefixed dirs (e.g. `_shared`).
- `tools/flow-install/lib/registry/registry-artifacts.mjs` — stub that throws "not implemented", so accidental selection fails loudly.

**Refactored:**
- `tools/flow-install/lib/skills.mjs` — `installSkills(flowInstallRoot, opts)` accepts an optional `registry` and defaults to `LocalRegistry(flowInstallRoot)`. Old private `collectSourceSkills` deleted.

**Tests:** `tools/flow-install/tests/registry.test.mjs` — covers `LocalRegistry.list()`, `fetch()` for known/unknown skills, `_`-prefix filtering, `formatRef`/`parseRef` round-trip, base-class throw behavior, artifacts-stub failure.

**Verification beyond tests:** dry-run installer enumerates all 45 skills through the new registry; `_shared/` still synced separately; no other steps regressed.

## Phase 2 — Management Worker (done)

**Created (under `services/skill-registry/`):**
- `wrangler.toml` — Worker config + `[[artifacts]]` binding stanza (RECONCILE marker — verify against current Cloudflare docs at deploy time).
- `package.json` — `dev`, `deploy`, `tail` scripts; sole dep `wrangler`.
- `src/index.mjs` — Worker. Bearer auth (constant-time), 2 endpoints, name validation `/^[a-z0-9][a-z0-9-]{0,62}$/`, TTL clamping (max 30d).
- `.dev.vars.example`, `.gitignore`.

**API:**
| Method | Path | Body | Returns |
|---|---|---|---|
| `POST` | `/skills/:name` | — | `{name, remote, writeToken, ttl}` |
| `POST` | `/skills/:name/tokens` | `{access, ttlSeconds?}` | `{token, access, ttl}` |

All requests require `Authorization: Bearer <PUBLISH_TOKEN>`.

**Tests:** `services/skill-registry/tests/worker.test.mjs` — auth (missing, malformed, wrong, right), name validation, idempotent create, token minting (read default, write override, TTL clamp, default fallback), 404 for unknown routes/methods, 500 path on binding error.

**RECONCILE points to verify before deploy:**
1. `[[artifacts]]` stanza key + fields in `wrangler.toml`.
2. `env.ARTIFACTS.create(name)` returning `{remote, token, repo}` and being idempotent (`src/index.mjs` `createOrGetRepo`).
3. `repo.createToken(access, ttlSeconds)` signature (`src/index.mjs` `mintToken`).

## Phase 3 — Publish flow (done)

Built four composable units, test-first throughout. Total Phase 3 tests: **31 (10 + 8 + 6 + 7) all green**, plus 23 carried over from Phase 1+2 = **54/54 across the registry suite**.

**Lockfile module** (`tools/flow-install/lib/registry/lockfile.mjs`)
Pure read/upsert/write over a new `skill-registry.lock.json` (separate from `harnessy.lock.json` to keep install config and publish records from mixing). Sorted-key output, trailing newline, required-field validation. 10 tests in `tests/registry-lockfile.test.mjs`.

**Worker HTTP client** (`tools/flow-install/lib/registry/worker-client.mjs`)
Wraps `POST /skills/:name` and `POST /skills/:name/tokens`. Bearer auth, baseUrl trailing-slash strip, client-side name validation, `WorkerError` carries status + body, handles non-JSON error responses. Constructor takes injectable `fetchImpl` for tests. 8 tests in `tests/registry-worker-client.test.mjs`.

**Git publish** (`tools/flow-install/lib/registry/git-publish.mjs`)
`publishSkillGit({skillDir, name, version, pushUrl, gitEnv})` — idempotent `git init`, `add -A`, `commit --allow-empty`, `tag v<version>` (fails on collision), then pushes branch + tag separately. Returns `{sha, tag}`. 6 integration tests in `tests/registry-git-publish.test.mjs` use real `git` against a temp `--bare` remote.

**Orchestrator + CLI** (`tools/flow-install/lib/registry/publish-skill.mjs` + `scripts/publish-skill.mjs`)
`publishSkill({name, version, skillsRoot, lockfilePath, workerClient, git, now})` — guards against missing skill dir, calls Worker, builds authed push URL via `authedPushUrl(remote, token)` (RECONCILE marker on auth scheme), runs git publish, then writes lockfile entry `{version, sha, remote, registry: "artifacts", publishedAt}`. Lockfile is only written after both Worker and git succeed (no half-state). CLI shell `scripts/publish-skill.mjs` constructs real deps from CLI args + env (`HARNESSY_WORKER_URL`, `HARNESSY_PUBLISH_TOKEN`). 7 tests in `tests/registry-publish-skill.test.mjs`.

**RECONCILE points added in Phase 3:**
4. `authedPushUrl()` in `publish-skill.mjs` assumes `https://x-access-token:<token>@host/path`-style basic-auth for git push to Artifacts. Confirm at deploy time.

**Not yet wired:** the markdown-driven slash skill at `tools/flow-install/skills/skill-publish/SKILL.md` still describes the original catalog-update workflow. Updating it to call `publish-skill.mjs` is a Phase 3 follow-up — left for after we know the Worker actually deploys.

## Phase 4 — Install/resolve flow (done)

Phase 4 tests: **9 new** (all in `tests/registry-artifacts.test.mjs`) plus 1 added to `registry.test.mjs` for the new `LocalRegistry.fetch()` manifest contract — **63/63 green** across the full registry suite.

**`ArtifactsRegistry` (replaces the Phase 1 stub) — `tools/flow-install/lib/registry/registry-artifacts.mjs`**

Constructor: `{lockfilePath, cacheDir, token?, gitEnv?}`

- `list()` reads `skill-registry.lock.json`, returns `[{name, version}]` for entries where `registry === "artifacts"` only. Local-backed entries are filtered out so a mixed-mode lockfile is safe.
- `fetch(name, version)` validates the lockfile entry, clones `git clone --depth 1 --branch v<version>` into `<cacheDir>/<name>/<sha>/`, verifies HEAD SHA matches the lockfile, returns `{dir, sha, manifest}`. Subsequent calls with the same SHA are a pure cache hit (no git ops, proven in tests by deleting the bare remote between calls). SHA mismatch throws and removes the bad cache dir.

**Auth helper** `authedFetchUrl(remote, token)` mirrors the Phase 3 `authedPushUrl` — `x-access-token` basic auth on https URLs, pass-through otherwise. RECONCILE point #5.

**Contract tightening (small, backward-compatible):**
- `Registry.fetch()` now returns `{dir, sha?, manifest?}`. `LocalRegistry.fetch()` updated to also return `manifest` (it already had it). `installSkills` in `lib/skills.mjs` prefers `fetched.manifest` and falls back to `summary.manifest` — so older registries keep working.
- Removed the obsolete "stub fails loudly" test from `registry.test.mjs` since the stubs are real now.

**Cache layout:** `<cacheDir>/<name>/<sha>/` — content-addressed, so multiple versions of the same skill coexist and version drift never serves stale content.

**RECONCILE points added in Phase 4:**
5. `authedFetchUrl()` — same caveat as Phase 3's `authedPushUrl`.

**Not done in this phase (deliberately deferred):**
- Wiring `ArtifactsRegistry` into `installSkills` as the *default* backend. Today the installer still uses `LocalRegistry` — switching the default should wait until at least one skill has been published through Phases 2+3 end-to-end.
- ArtifactFS lazy-mount mode. Eager `git clone` is sufficient until the skill catalog is large enough that latency matters.

## Phase 5 — Verification + P2P story (done)

Phase 5 tests: **22 new** (9 manifest + 6 verify + 6 verifySkillContents + 1 publish-records-manifest) — **85/85 green** across the full registry suite.

**Content manifest** (`tools/flow-install/lib/registry/content-manifest.mjs`)
`computeContentManifest(dir, {ignore?})` walks the dir, ignores `.git/` and `.DS_Store` by default, returns `{files: [{path, sha256}], treeHash}`. Paths use forward slashes regardless of OS. Hash is content-only — mtime drift never affects the result.

Canonical serialization: each file rendered as `<path>\t<sha256>\n`, lines joined in path-sorted order, then SHA-256'd to produce `treeHash`. Anyone with the same files reproduces the same hash byte-for-byte.

**Verification primitive** (same module)
`verifySkillContents(dir, expected)` compares an installed dir against an expected manifest, returns `{ok, treeHash, mismatches: {added, removed, changed}}`. Granular — tells you which files diverged, not just "something changed."

**Publish wires manifest into lockfile** (`publish-skill.mjs`)
`publishSkill` now computes the manifest of the skill dir before writing the lockfile entry and stores `treeHash` + `files` alongside `{version, sha, remote}`. `treeHash`/`files` are *optional* fields in the lockfile — Phase 3 entries that lack them still load.

**Verify orchestrator** (`tools/flow-install/lib/registry/verify.mjs`)
`verifySkills({lockfilePath, installedRoot})` walks the lockfile, verifies each artifacts-backed entry against `<installedRoot>/<name>/`, returns one record per skill with one of three outcomes:
- `{ok: true}` — installed dir matches the recorded manifest.
- `{ok: false, mismatches: {added, removed, changed}}` — drift detected.
- `{ok: false, reason: "no_manifest"}` — Phase 3 entry without manifest metadata; re-publish to populate.
- `{ok: false, reason: "not_installed"}` — lockfile knows about it, install dir missing.

Local-only entries are filtered out (no remote = nothing to verify against).

**CLI** (`tools/flow-install/scripts/verify-skills.mjs`)
Defaults to `~/.agents/skills/` and the local `skill-registry.lock.json`. `--json` for machine output, exits non-zero on any failure. `--help` works.

## P2P contract (the load-bearing claim)

What agents exchange over the P2P layer is not files. It's a tuple:

```
{ name, version, sha, treeHash }
```

- `sha` — the git commit SHA in the Artifacts repo. Pin point in the Merkle DAG.
- `treeHash` — the SHA-256 of the canonical content manifest. Independent of git.

Either one alone is enough to detect tampering. Both together let you verify without hitting the registry: any peer can recompute `treeHash` from local files, and any peer can fetch by `sha` to retrieve the canonical bytes. Trust derives from content, not from the host.

This is why `treeHash` is stored in the lockfile next to `sha` — it makes verification offline-capable, which is the whole point of building toward a P2P story.

## Open RECONCILE points (carried forward, not closed by Phase 5)

| # | Where | What to verify |
|---|---|---|
| 1 | `services/skill-registry/wrangler.toml` | `[[artifacts]]` stanza key + fields |
| 2 | `services/skill-registry/src/index.mjs` | `env.ARTIFACTS.create()` shape, idempotency |
| 3 | same | `repo.createToken(access, ttlSeconds)` signature |
| 4 | `tools/flow-install/lib/registry/publish-skill.mjs` | `authedPushUrl` auth scheme for git push |
| 5 | `tools/flow-install/lib/registry/registry-artifacts.mjs` | `authedFetchUrl` auth scheme for git clone |

These are all surfaced clearly in the code with `RECONCILE` comments and only need a quick pass once the Cloudflare Artifacts SDK lands publicly.

## Future work (not part of this migration)

- **Default-flip to artifacts backend** in `installSkills` once at least one skill has gone through publish → install end-to-end against a deployed Worker.
- **ArtifactFS lazy mount** — replace eager git clone with FUSE-backed on-demand fetch when the skill catalog grows enough that latency matters.
- **Lockfile-fidelity harness lane** — add a test row to `tests/harness/run-verification-track.sh` that does install → snapshot → wipe → re-install → byte-diff. The primitives for this (`computeContentManifest`) now exist.
- **Signed refs** — agents could sign `{name, sha, treeHash}` tuples with a key, letting peers verify provenance, not just content. Out of scope for this migration but the data model already supports it.
