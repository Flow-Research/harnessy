import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import {
  EMPTY_LOCK,
  LOCK_VERSION,
  readRegistryLock,
  writeRegistryLock,
  upsertSkillEntry,
} from "../lib/registry/lockfile.mjs";

const tmpFile = async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "harnessy-lockfile-"));
  return path.join(dir, "skill-registry.lock.json");
};

test("EMPTY_LOCK has the expected shape", () => {
  assert.equal(EMPTY_LOCK.version, LOCK_VERSION);
  assert.equal(EMPTY_LOCK.namespace, "flow");
  assert.deepEqual(EMPTY_LOCK.skills, {});
});

test("readRegistryLock returns EMPTY_LOCK when file does not exist", async () => {
  const file = await tmpFile();
  const lock = await readRegistryLock(file);
  assert.deepEqual(lock, EMPTY_LOCK);
});

test("readRegistryLock returns parsed contents when file exists", async () => {
  const file = await tmpFile();
  await fs.writeFile(
    file,
    JSON.stringify({
      version: LOCK_VERSION,
      namespace: "flow",
      skills: { foo: { version: "1.0.0", sha: "abc", remote: "r", registry: "artifacts" } },
    }),
  );
  const lock = await readRegistryLock(file);
  assert.equal(lock.skills.foo.version, "1.0.0");
});

test("readRegistryLock throws on invalid JSON", async () => {
  const file = await tmpFile();
  await fs.writeFile(file, "{not json");
  await assert.rejects(() => readRegistryLock(file), /skill-registry.lock.json/);
});

test("upsertSkillEntry adds a new skill without mutating input", () => {
  const before = structuredClone(EMPTY_LOCK);
  const after = upsertSkillEntry(EMPTY_LOCK, "issue-flow", {
    version: "0.8.1",
    sha: "deadbeef",
    remote: "https://artifacts.example/issue-flow.git",
    registry: "artifacts",
    publishedAt: "2026-04-25T10:00:00.000Z",
  });
  assert.deepEqual(EMPTY_LOCK, before, "input must not be mutated");
  assert.equal(after.skills["issue-flow"].sha, "deadbeef");
});

test("upsertSkillEntry replaces an existing skill entry", () => {
  const initial = upsertSkillEntry(EMPTY_LOCK, "foo", {
    version: "1.0.0", sha: "old", remote: "r", registry: "artifacts", publishedAt: "t1",
  });
  const updated = upsertSkillEntry(initial, "foo", {
    version: "1.0.1", sha: "new", remote: "r", registry: "artifacts", publishedAt: "t2",
  });
  assert.equal(updated.skills.foo.sha, "new");
  assert.equal(updated.skills.foo.version, "1.0.1");
});

test("upsertSkillEntry preserves unrelated entries", () => {
  let lock = upsertSkillEntry(EMPTY_LOCK, "foo", {
    version: "1.0.0", sha: "f", remote: "r", registry: "artifacts", publishedAt: "t",
  });
  lock = upsertSkillEntry(lock, "bar", {
    version: "2.0.0", sha: "b", remote: "r", registry: "artifacts", publishedAt: "t",
  });
  assert.equal(lock.skills.foo.sha, "f");
  assert.equal(lock.skills.bar.sha, "b");
});

test("upsertSkillEntry rejects entries missing required fields", () => {
  for (const missing of ["version", "sha", "remote", "registry"]) {
    const entry = {
      version: "1.0.0", sha: "s", remote: "r", registry: "artifacts", publishedAt: "t",
    };
    delete entry[missing];
    assert.throws(
      () => upsertSkillEntry(EMPTY_LOCK, "foo", entry),
      new RegExp(missing),
      `expected throw when "${missing}" is missing`,
    );
  }
});

test("writeRegistryLock produces sorted-key JSON with trailing newline", async () => {
  const file = await tmpFile();
  let lock = upsertSkillEntry(EMPTY_LOCK, "zeta", {
    version: "1.0.0", sha: "z", remote: "r", registry: "artifacts", publishedAt: "t",
  });
  lock = upsertSkillEntry(lock, "alpha", {
    version: "1.0.0", sha: "a", remote: "r", registry: "artifacts", publishedAt: "t",
  });
  await writeRegistryLock(file, lock);
  const raw = await fs.readFile(file, "utf8");
  assert.ok(raw.endsWith("\n"), "must end with newline");
  const alphaIdx = raw.indexOf("\"alpha\"");
  const zetaIdx = raw.indexOf("\"zeta\"");
  assert.ok(alphaIdx > -1 && zetaIdx > -1 && alphaIdx < zetaIdx, "skill keys must be sorted");
});

test("write then read round-trips losslessly", async () => {
  const file = await tmpFile();
  const lock = upsertSkillEntry(EMPTY_LOCK, "issue-flow", {
    version: "0.8.1",
    sha: "abc123",
    remote: "https://artifacts.example/issue-flow.git",
    registry: "artifacts",
    publishedAt: "2026-04-25T10:00:00.000Z",
  });
  await writeRegistryLock(file, lock);
  const reloaded = await readRegistryLock(file);
  assert.deepEqual(reloaded, lock);
});
