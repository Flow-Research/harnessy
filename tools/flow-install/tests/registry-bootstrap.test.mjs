import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { bootstrapInstall } from "../lib/registry/bootstrap.mjs";

const tmp = (label) => fs.mkdtemp(path.join(os.tmpdir(), `harnessy-boot-${label}-`));

const seedRemoteLockfile = {
  version: 1,
  namespace: "flow",
  skills: {
    "issue-flow": {
      version: "0.8.1",
      sha: "a".repeat(40),
      remote: "https://artifacts.example/issue-flow.git",
      treeHash: "b".repeat(64),
      files: [{ path: "SKILL.md", sha256: "c".repeat(64) }],
      registry: "artifacts",
      publishedAt: "2026-04-25T10:00:00.000Z",
    },
    "qa": {
      version: "1.0.0",
      sha: "d".repeat(40),
      remote: "https://artifacts.example/qa.git",
      treeHash: "e".repeat(64),
      files: [{ path: "SKILL.md", sha256: "f".repeat(64) }],
      registry: "artifacts",
      publishedAt: "2026-04-25T11:00:00.000Z",
    },
  },
};

const okFetch = (lockfile = seedRemoteLockfile) => {
  const calls = [];
  const fn = async (url) => {
    calls.push(String(url));
    return new Response(JSON.stringify(lockfile), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };
  fn.calls = calls;
  return fn;
};

test("bootstrapInstall fetches remote lockfile and writes it to disk", async () => {
  const root = await tmp("root");
  const lockfilePath = path.join(root, "skill-registry.lock.json");
  const fetchImpl = okFetch();
  const installer = { calls: [], install: async (registry) => { installer.calls.push(registry); } };

  const result = await bootstrapInstall({
    workerUrl: "https://w.example",
    lockfilePath,
    cacheDir: path.join(root, "cache"),
    fetchImpl,
    installer,
  });

  assert.equal(fetchImpl.calls[0], "https://w.example/lockfile");
  const onDisk = JSON.parse(await fs.readFile(lockfilePath, "utf8"));
  assert.equal(onDisk.skills["issue-flow"].version, "0.8.1");
  assert.equal(result.skillCount, 2);
});

test("bootstrapInstall strips trailing slash from workerUrl", async () => {
  const root = await tmp("trail");
  const fetchImpl = okFetch();
  await bootstrapInstall({
    workerUrl: "https://w.example/",
    lockfilePath: path.join(root, "lock.json"),
    cacheDir: path.join(root, "cache"),
    fetchImpl,
    installer: { install: async () => {} },
  });
  assert.equal(fetchImpl.calls[0], "https://w.example/lockfile");
});

test("bootstrapInstall hands an ArtifactsRegistry to the installer", async () => {
  const root = await tmp("reg");
  const captured = [];
  await bootstrapInstall({
    workerUrl: "https://w.example",
    lockfilePath: path.join(root, "lock.json"),
    cacheDir: path.join(root, "cache"),
    fetchImpl: okFetch(),
    installer: {
      install: async (registry) => { captured.push(registry); },
    },
  });
  assert.equal(captured.length, 1);
  // Duck-type check: the registry must expose list() and fetch().
  assert.equal(typeof captured[0].list, "function");
  assert.equal(typeof captured[0].fetch, "function");
  const list = await captured[0].list();
  assert.equal(list.length, 2);
});

test("bootstrapInstall throws when lockfile fetch returns non-200", async () => {
  const root = await tmp("err");
  const lockfilePath = path.join(root, "lock.json");
  const fetchImpl = async () => new Response("upstream broken", { status: 502 });
  await assert.rejects(
    () => bootstrapInstall({
      workerUrl: "https://w.example",
      lockfilePath,
      cacheDir: path.join(root, "cache"),
      fetchImpl,
      installer: { install: async () => {} },
    }),
    /502|fetch lockfile/i,
  );
  await assert.rejects(() => fs.access(lockfilePath), /ENOENT/, "lockfile must not be written on failure");
});

test("bootstrapInstall throws when lockfile body is not valid JSON", async () => {
  const root = await tmp("badjson");
  const fetchImpl = async () => new Response("not json{", { status: 200 });
  await assert.rejects(
    () => bootstrapInstall({
      workerUrl: "https://w.example",
      lockfilePath: path.join(root, "lock.json"),
      cacheDir: path.join(root, "cache"),
      fetchImpl,
      installer: { install: async () => {} },
    }),
    /JSON|parse/i,
  );
});

test("bootstrapInstall does not call installer if fetch fails", async () => {
  const root = await tmp("noinstall");
  const calls = [];
  const fetchImpl = async () => new Response("fail", { status: 500 });
  await assert.rejects(
    () => bootstrapInstall({
      workerUrl: "https://w.example",
      lockfilePath: path.join(root, "lock.json"),
      cacheDir: path.join(root, "cache"),
      fetchImpl,
      installer: { install: async (r) => calls.push(r) },
    }),
  );
  assert.deepEqual(calls, []);
});
