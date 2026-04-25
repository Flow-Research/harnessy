import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

import { ArtifactsRegistry } from "../lib/registry/registry-artifacts.mjs";
import {
  EMPTY_LOCK,
  upsertSkillEntry,
  writeRegistryLock,
} from "../lib/registry/lockfile.mjs";

const execFileAsync = promisify(execFile);

const GIT_ENV = {
  GIT_AUTHOR_NAME: "Test", GIT_AUTHOR_EMAIL: "t@test",
  GIT_COMMITTER_NAME: "Test", GIT_COMMITTER_EMAIL: "t@test",
  GIT_TERMINAL_PROMPT: "0",
};

const tmp = (label) => fs.mkdtemp(path.join(os.tmpdir(), `harnessy-art-${label}-`));

// Build a bare remote that holds a published "skill repo" at v1.0.0; return
// the URL git can clone from and the SHA of the tag commit.
const seedRemote = async ({ name = "issue-flow", version = "1.0.0", manifestExtras = {} } = {}) => {
  const work = await tmp("work");
  const remote = await tmp("remote");
  await execFileAsync("git", ["init", "--bare", remote]);

  await fs.writeFile(path.join(work, "SKILL.md"), `# ${name}\n`);
  const manifestLines = [`name: ${name}`, `version: ${version}`];
  for (const [k, v] of Object.entries(manifestExtras)) manifestLines.push(`${k}: ${v}`);
  await fs.writeFile(path.join(work, "manifest.yaml"), manifestLines.join("\n") + "\n");

  const run = (args) => execFileAsync("git", ["-C", work, ...args], {
    env: { ...process.env, ...GIT_ENV },
  });
  await run(["init", "--initial-branch=main"]);
  await run(["add", "-A"]);
  await run(["commit", "-m", `publish: ${name}@${version}`]);
  await run(["tag", `v${version}`]);
  await run(["push", remote, "HEAD:refs/heads/main"]);
  await run(["push", remote, `refs/tags/v${version}`]);
  const { stdout } = await run(["rev-parse", "HEAD"]);
  return { remote, sha: stdout.trim(), workTree: work };
};

const writeLock = async (lockfilePath, entries) => {
  let lock = structuredClone(EMPTY_LOCK);
  for (const [name, entry] of Object.entries(entries)) {
    lock = upsertSkillEntry(lock, name, entry);
  }
  await writeRegistryLock(lockfilePath, lock);
};

// ── Phase 4A: list() ────────────────────────────────────────────────────────

test("ArtifactsRegistry.list() returns [] when lockfile is missing", async () => {
  const lockfilePath = path.join(await tmp("lock"), "skill-registry.lock.json");
  const cacheDir = await tmp("cache");
  const reg = new ArtifactsRegistry({ lockfilePath, cacheDir });
  assert.deepEqual(await reg.list(), []);
});

test("ArtifactsRegistry.list() returns name+version for artifacts-backed entries", async () => {
  const lockfilePath = path.join(await tmp("lock"), "skill-registry.lock.json");
  const cacheDir = await tmp("cache");
  await writeLock(lockfilePath, {
    "issue-flow": { version: "0.8.1", sha: "a".repeat(40), remote: "r1", registry: "artifacts", publishedAt: "t" },
    "qa": { version: "1.2.0", sha: "b".repeat(40), remote: "r2", registry: "artifacts", publishedAt: "t" },
  });
  const reg = new ArtifactsRegistry({ lockfilePath, cacheDir });
  const list = await reg.list();
  const byName = Object.fromEntries(list.map((s) => [s.name, s]));
  assert.equal(byName["issue-flow"].version, "0.8.1");
  assert.equal(byName.qa.version, "1.2.0");
  assert.equal(list.length, 2);
});

test("ArtifactsRegistry.list() filters out entries whose registry is not 'artifacts'", async () => {
  const lockfilePath = path.join(await tmp("lock"), "skill-registry.lock.json");
  const cacheDir = await tmp("cache");
  await writeLock(lockfilePath, {
    "remote-skill": { version: "1.0.0", sha: "a".repeat(40), remote: "r", registry: "artifacts", publishedAt: "t" },
    "local-skill":  { version: "1.0.0", sha: "b".repeat(40), remote: "r", registry: "local", publishedAt: "t" },
  });
  const reg = new ArtifactsRegistry({ lockfilePath, cacheDir });
  const names = (await reg.list()).map((s) => s.name);
  assert.deepEqual(names, ["remote-skill"]);
});

// ── Phase 4B: fetch() ───────────────────────────────────────────────────────

test("ArtifactsRegistry.fetch() throws when skill is not in the lockfile", async () => {
  const lockfilePath = path.join(await tmp("lock"), "skill-registry.lock.json");
  const cacheDir = await tmp("cache");
  await writeLock(lockfilePath, {});
  const reg = new ArtifactsRegistry({ lockfilePath, cacheDir });
  await assert.rejects(() => reg.fetch("nope", "1.0.0"), /nope/);
});

test("ArtifactsRegistry.fetch() throws when version mismatches the lockfile", async () => {
  const lockfilePath = path.join(await tmp("lock"), "skill-registry.lock.json");
  const cacheDir = await tmp("cache");
  await writeLock(lockfilePath, {
    foo: { version: "1.0.0", sha: "a".repeat(40), remote: "r", registry: "artifacts", publishedAt: "t" },
  });
  const reg = new ArtifactsRegistry({ lockfilePath, cacheDir });
  await assert.rejects(() => reg.fetch("foo", "9.9.9"), /9\.9\.9/);
});

test("ArtifactsRegistry.fetch() clones from remote, verifies SHA, returns dir + manifest", async () => {
  const { remote, sha } = await seedRemote({
    name: "issue-flow",
    version: "0.8.1",
    manifestExtras: { python_packages: "requests" },
  });
  const lockfilePath = path.join(await tmp("lock"), "skill-registry.lock.json");
  const cacheDir = await tmp("cache");
  await writeLock(lockfilePath, {
    "issue-flow": { version: "0.8.1", sha, remote, registry: "artifacts", publishedAt: "t" },
  });

  const reg = new ArtifactsRegistry({ lockfilePath, cacheDir, gitEnv: GIT_ENV });
  const result = await reg.fetch("issue-flow", "0.8.1");

  assert.equal(result.sha, sha);
  assert.ok(result.dir.includes("issue-flow"), "cache dir should be content-addressed by name");
  assert.ok(result.dir.includes(sha), "cache dir should be content-addressed by sha");

  const skillMd = await fs.readFile(path.join(result.dir, "SKILL.md"), "utf8");
  assert.match(skillMd, /issue-flow/);
  assert.equal(result.manifest.name, "issue-flow");
  assert.equal(result.manifest.version, "0.8.1");
  assert.equal(result.manifest.python_packages, "requests");
});

test("ArtifactsRegistry.fetch() is a cache hit on second call (no network needed)", async () => {
  const { remote, sha } = await seedRemote({ name: "qa", version: "1.0.0" });
  const lockfilePath = path.join(await tmp("lock"), "skill-registry.lock.json");
  const cacheDir = await tmp("cache");
  await writeLock(lockfilePath, {
    qa: { version: "1.0.0", sha, remote, registry: "artifacts", publishedAt: "t" },
  });

  const reg = new ArtifactsRegistry({ lockfilePath, cacheDir, gitEnv: GIT_ENV });
  const first = await reg.fetch("qa", "1.0.0");

  // Nuke the remote so a real clone would fail. If fetch still succeeds, we
  // proved the second call hit the cache.
  await fs.rm(remote, { recursive: true, force: true });

  const second = await reg.fetch("qa", "1.0.0");
  assert.equal(second.dir, first.dir);
  assert.equal(second.sha, sha);
});

test("ArtifactsRegistry.fetch() throws and cleans up when SHA mismatches lockfile", async () => {
  const { remote, sha } = await seedRemote({ name: "drift", version: "1.0.0" });
  const lockfilePath = path.join(await tmp("lock"), "skill-registry.lock.json");
  const cacheDir = await tmp("cache");
  const wrongSha = "f".repeat(40);
  await writeLock(lockfilePath, {
    drift: { version: "1.0.0", sha: wrongSha, remote, registry: "artifacts", publishedAt: "t" },
  });

  const reg = new ArtifactsRegistry({ lockfilePath, cacheDir, gitEnv: GIT_ENV });
  await assert.rejects(
    () => reg.fetch("drift", "1.0.0"),
    (err) => /sha/i.test(err.message) && err.message.includes(wrongSha.slice(0, 7)),
  );

  // Cache dir for the bad SHA must be removed so retries don't see stale state.
  const badCachePath = path.join(cacheDir, "drift", wrongSha);
  await assert.rejects(() => fs.access(badCachePath), /ENOENT/);
});

test("ArtifactsRegistry.fetch() refuses entries whose registry is not 'artifacts'", async () => {
  const lockfilePath = path.join(await tmp("lock"), "skill-registry.lock.json");
  const cacheDir = await tmp("cache");
  await writeLock(lockfilePath, {
    "local-only": { version: "1.0.0", sha: "a".repeat(40), remote: "r", registry: "local", publishedAt: "t" },
  });
  const reg = new ArtifactsRegistry({ lockfilePath, cacheDir });
  await assert.rejects(() => reg.fetch("local-only", "1.0.0"), /artifacts/);
});
