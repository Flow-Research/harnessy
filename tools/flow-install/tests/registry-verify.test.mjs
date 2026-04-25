import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { verifySkills } from "../lib/registry/verify.mjs";
import { computeContentManifest } from "../lib/registry/content-manifest.mjs";
import {
  EMPTY_LOCK,
  upsertSkillEntry,
  writeRegistryLock,
} from "../lib/registry/lockfile.mjs";

const tmp = (label) => fs.mkdtemp(path.join(os.tmpdir(), `harnessy-vfy-${label}-`));

const setup = async () => {
  const root = await tmp("root");
  const installedRoot = path.join(root, "skills");
  const lockfilePath = path.join(root, "skill-registry.lock.json");
  await fs.mkdir(installedRoot, { recursive: true });
  return { installedRoot, lockfilePath };
};

const installSkill = async (installedRoot, name, files) => {
  const dir = path.join(installedRoot, name);
  await fs.mkdir(dir, { recursive: true });
  for (const [relPath, content] of Object.entries(files)) {
    const full = path.join(dir, relPath);
    await fs.mkdir(path.dirname(full), { recursive: true });
    await fs.writeFile(full, content);
  }
  return dir;
};

const writeLock = async (lockfilePath, entries) => {
  let lock = structuredClone(EMPTY_LOCK);
  for (const [name, entry] of Object.entries(entries)) {
    lock = upsertSkillEntry(lock, name, entry);
  }
  await writeRegistryLock(lockfilePath, lock);
};

test("verifySkills returns [] when the lockfile is empty", async () => {
  const { installedRoot, lockfilePath } = await setup();
  await writeLock(lockfilePath, {});
  const results = await verifySkills({ lockfilePath, installedRoot });
  assert.deepEqual(results, []);
});

test("verifySkills reports ok=true when an installed skill matches its manifest", async () => {
  const { installedRoot, lockfilePath } = await setup();
  const dir = await installSkill(installedRoot, "issue-flow", {
    "SKILL.md": "hello\n",
    "manifest.yaml": "name: issue-flow\nversion: 0.8.1\n",
  });
  const manifest = await computeContentManifest(dir);
  await writeLock(lockfilePath, {
    "issue-flow": {
      version: "0.8.1",
      sha: "a".repeat(40),
      remote: "r",
      registry: "artifacts",
      publishedAt: "t",
      treeHash: manifest.treeHash,
      files: manifest.files,
    },
  });

  const results = await verifySkills({ lockfilePath, installedRoot });
  assert.equal(results.length, 1);
  assert.equal(results[0].name, "issue-flow");
  assert.equal(results[0].ok, true);
});

test("verifySkills reports ok=false with mismatches when an installed file is tampered", async () => {
  const { installedRoot, lockfilePath } = await setup();
  const dir = await installSkill(installedRoot, "qa", {
    "SKILL.md": "original\n",
  });
  const manifest = await computeContentManifest(dir);
  await writeLock(lockfilePath, {
    qa: {
      version: "1.0.0", sha: "a".repeat(40), remote: "r", registry: "artifacts",
      publishedAt: "t", treeHash: manifest.treeHash, files: manifest.files,
    },
  });
  await fs.writeFile(path.join(dir, "SKILL.md"), "tampered\n");

  const [result] = await verifySkills({ lockfilePath, installedRoot });
  assert.equal(result.ok, false);
  assert.deepEqual(result.mismatches.changed, ["SKILL.md"]);
});

test("verifySkills reports reason=no_manifest for entries without treeHash/files", async () => {
  const { installedRoot, lockfilePath } = await setup();
  await installSkill(installedRoot, "old", { "SKILL.md": "x" });
  await writeLock(lockfilePath, {
    old: {
      version: "1.0.0", sha: "a".repeat(40), remote: "r", registry: "artifacts",
      publishedAt: "t",
      // No treeHash/files — simulates a Phase 3 entry recorded before
      // verification metadata was added.
    },
  });
  const [result] = await verifySkills({ lockfilePath, installedRoot });
  assert.equal(result.ok, false);
  assert.equal(result.reason, "no_manifest");
});

test("verifySkills reports reason=not_installed when the skill dir is missing", async () => {
  const { installedRoot, lockfilePath } = await setup();
  await writeLock(lockfilePath, {
    ghost: {
      version: "1.0.0", sha: "a".repeat(40), remote: "r", registry: "artifacts",
      publishedAt: "t", treeHash: "f".repeat(64), files: [],
    },
  });
  const [result] = await verifySkills({ lockfilePath, installedRoot });
  assert.equal(result.ok, false);
  assert.equal(result.reason, "not_installed");
});

test("verifySkills filters out non-artifacts entries", async () => {
  const { installedRoot, lockfilePath } = await setup();
  await writeLock(lockfilePath, {
    "local-skill": {
      version: "1.0.0", sha: "a".repeat(40), remote: "r", registry: "local",
      publishedAt: "t",
    },
  });
  const results = await verifySkills({ lockfilePath, installedRoot });
  assert.deepEqual(results, []);
});
