import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { publishSkill, authedPushUrl } from "../lib/registry/publish-skill.mjs";
import { readRegistryLock } from "../lib/registry/lockfile.mjs";

const setup = async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "harnessy-publish-"));
  const skillsRoot = path.join(root, "skills");
  await fs.mkdir(path.join(skillsRoot, "issue-flow"), { recursive: true });
  await fs.writeFile(path.join(skillsRoot, "issue-flow", "SKILL.md"), "# issue-flow\n");
  const lockfilePath = path.join(root, "skill-registry.lock.json");
  return { root, skillsRoot, lockfilePath };
};

const okWorker = () => ({
  calls: { createSkill: [], recordPublish: [] },
  createSkill(name) {
    this.calls.createSkill.push(name);
    return Promise.resolve({
      name,
      remote: `https://artifacts.example/${name}.git`,
      writeToken: "wt",
      ttl: 3600,
    });
  },
  recordPublish(name, entry) {
    this.calls.recordPublish.push({ name, entry });
    return Promise.resolve({ name, ok: true });
  },
});

const okGit = (sha = "a".repeat(40)) => ({
  calls: { publish: [] },
  publish(args) {
    this.calls.publish.push(args);
    return Promise.resolve({ sha, tag: `v${args.version}` });
  },
});

test("authedPushUrl injects token as basic-auth user", () => {
  const url = authedPushUrl("https://artifacts.example/foo.git", "secret-token");
  assert.equal(url, "https://x-access-token:secret-token@artifacts.example/foo.git");
});

test("authedPushUrl handles non-https remotes by passing them through unchanged", () => {
  // RECONCILE: if Artifacts uses a different auth scheme this helper changes;
  // we want the caller-visible behavior to be deterministic and unsurprising.
  const url = authedPushUrl("git@artifacts.example:foo.git", "tok");
  assert.equal(url, "git@artifacts.example:foo.git");
});

test("publishSkill happy path writes the lockfile entry with sha + remote", async () => {
  const { skillsRoot, lockfilePath } = await setup();
  const worker = okWorker();
  const git = okGit("deadbeef".padEnd(40, "0"));
  const now = () => new Date("2026-04-25T10:00:00.000Z");

  const result = await publishSkill({
    name: "issue-flow",
    version: "0.8.1",
    skillsRoot,
    lockfilePath,
    workerClient: worker,
    git,
    now,
  });

  assert.deepEqual(worker.calls.createSkill, ["issue-flow"]);
  assert.equal(git.calls.publish.length, 1);
  assert.equal(git.calls.publish[0].name, "issue-flow");
  assert.equal(git.calls.publish[0].version, "0.8.1");
  assert.equal(git.calls.publish[0].pushUrl, "https://x-access-token:wt@artifacts.example/issue-flow.git");

  const lock = await readRegistryLock(lockfilePath);
  const entry = lock.skills["issue-flow"];
  assert.equal(entry.version, "0.8.1");
  assert.equal(entry.sha, "deadbeef".padEnd(40, "0"));
  assert.equal(entry.remote, "https://artifacts.example/issue-flow.git");
  assert.equal(entry.registry, "artifacts");
  assert.equal(entry.publishedAt, "2026-04-25T10:00:00.000Z");
  assert.equal(result.sha, "deadbeef".padEnd(40, "0"));
});

test("publishSkill throws when the skill directory is missing", async () => {
  const { skillsRoot, lockfilePath } = await setup();
  const worker = okWorker();
  const git = okGit();
  await assert.rejects(
    () => publishSkill({
      name: "does-not-exist",
      version: "1.0.0",
      skillsRoot,
      lockfilePath,
      workerClient: worker,
      git,
    }),
    /does-not-exist/,
  );
  assert.equal(worker.calls.createSkill.length, 0, "worker must not be called");
  assert.equal(git.calls.publish.length, 0, "git must not be called");
});

test("publishSkill leaves the lockfile untouched if the worker call fails", async () => {
  const { skillsRoot, lockfilePath } = await setup();
  const worker = {
    calls: { createSkill: [] },
    createSkill: () => Promise.reject(new Error("worker 401")),
  };
  const git = okGit();

  await assert.rejects(
    () => publishSkill({
      name: "issue-flow", version: "1.0.0",
      skillsRoot, lockfilePath, workerClient: worker, git,
    }),
    /worker 401/,
  );

  assert.equal(git.calls.publish.length, 0, "git must not be called when worker fails");
  await assert.rejects(() => fs.access(lockfilePath), /ENOENT/, "lockfile must not be created");
});

test("publishSkill leaves the lockfile untouched if git.publish fails", async () => {
  const { skillsRoot, lockfilePath } = await setup();
  const worker = okWorker();
  const git = {
    calls: { publish: [] },
    publish: () => Promise.reject(new Error("git push denied")),
  };

  await assert.rejects(
    () => publishSkill({
      name: "issue-flow", version: "1.0.0",
      skillsRoot, lockfilePath, workerClient: worker, git,
    }),
    /git push denied/,
  );

  await assert.rejects(() => fs.access(lockfilePath), /ENOENT/, "lockfile must not be created");
});

test("publishSkill calls workerClient.recordPublish with the published entry after git push", async () => {
  const { skillsRoot, lockfilePath } = await setup();
  const worker = okWorker();
  const git = okGit("e".repeat(40));

  await publishSkill({
    name: "issue-flow", version: "0.8.1",
    skillsRoot, lockfilePath, workerClient: worker, git,
    now: () => new Date("2026-04-25T11:00:00.000Z"),
  });

  assert.equal(worker.calls.recordPublish.length, 1);
  const recorded = worker.calls.recordPublish[0];
  assert.equal(recorded.name, "issue-flow");
  assert.equal(recorded.entry.version, "0.8.1");
  assert.equal(recorded.entry.sha, "e".repeat(40));
  assert.equal(recorded.entry.remote, "https://artifacts.example/issue-flow.git");
  assert.match(recorded.entry.treeHash, /^[0-9a-f]{64}$/);
  assert.ok(Array.isArray(recorded.entry.files));
});

test("publishSkill leaves the lockfile untouched if recordPublish fails", async () => {
  const { skillsRoot, lockfilePath } = await setup();
  const worker = {
    calls: { createSkill: [], recordPublish: [] },
    createSkill: (name) => Promise.resolve({ name, remote: "r", writeToken: "wt", ttl: 1 }),
    recordPublish: () => Promise.reject(new Error("kv put failed")),
  };
  const git = okGit();

  await assert.rejects(
    () => publishSkill({
      name: "issue-flow", version: "1.0.0",
      skillsRoot, lockfilePath, workerClient: worker, git,
    }),
    /kv put failed/,
  );
  await assert.rejects(() => fs.access(lockfilePath), /ENOENT/);
});

test("publishSkill records treeHash + files manifest in the lockfile entry", async () => {
  const { skillsRoot, lockfilePath } = await setup();
  // setup() creates issue-flow with a SKILL.md file already; add a manifest.yaml
  // so we have two files to manifest.
  await fs.writeFile(
    path.join(skillsRoot, "issue-flow", "manifest.yaml"),
    "name: issue-flow\nversion: 0.8.1\n",
  );

  const worker = okWorker();
  const git = okGit("c".repeat(40));

  await publishSkill({
    name: "issue-flow",
    version: "0.8.1",
    skillsRoot,
    lockfilePath,
    workerClient: worker,
    git,
    now: () => new Date("2026-04-25T11:00:00.000Z"),
  });

  const lock = await readRegistryLock(lockfilePath);
  const entry = lock.skills["issue-flow"];
  assert.match(entry.treeHash, /^[0-9a-f]{64}$/, "treeHash must be a sha-256 hex");
  assert.ok(Array.isArray(entry.files), "files must be an array");
  const paths = entry.files.map((f) => f.path).sort();
  assert.deepEqual(paths, ["SKILL.md", "manifest.yaml"]);
  for (const f of entry.files) {
    assert.match(f.sha256, /^[0-9a-f]{64}$/);
  }
});

test("publishSkill preserves other skills' entries when upserting", async () => {
  const { skillsRoot, lockfilePath } = await setup();
  await fs.mkdir(path.join(skillsRoot, "qa"), { recursive: true });
  await fs.writeFile(path.join(skillsRoot, "qa", "SKILL.md"), "# qa\n");

  await publishSkill({
    name: "qa", version: "1.0.0",
    skillsRoot, lockfilePath, workerClient: okWorker(), git: okGit("aaa".padEnd(40, "0")),
    now: () => new Date("2026-04-25T09:00:00.000Z"),
  });

  await publishSkill({
    name: "issue-flow", version: "0.8.1",
    skillsRoot, lockfilePath, workerClient: okWorker(), git: okGit("bbb".padEnd(40, "0")),
    now: () => new Date("2026-04-25T10:00:00.000Z"),
  });

  const lock = await readRegistryLock(lockfilePath);
  assert.equal(lock.skills.qa.sha, "aaa".padEnd(40, "0"));
  assert.equal(lock.skills["issue-flow"].sha, "bbb".padEnd(40, "0"));
});
