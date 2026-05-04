import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { computeContentManifest, verifySkillContents } from "../lib/registry/content-manifest.mjs";

const tmp = (label) => fs.mkdtemp(path.join(os.tmpdir(), `harnessy-cm-${label}-`));

test("empty dir yields empty file list and a deterministic treeHash", async () => {
  const a = await tmp("empty1");
  const b = await tmp("empty2");
  const ma = await computeContentManifest(a);
  const mb = await computeContentManifest(b);
  assert.deepEqual(ma.files, []);
  assert.equal(ma.treeHash, mb.treeHash);
  assert.match(ma.treeHash, /^[0-9a-f]{64}$/);
});

test("single file yields one entry with content sha-256", async () => {
  const dir = await tmp("single");
  await fs.writeFile(path.join(dir, "SKILL.md"), "hello\n");
  const m = await computeContentManifest(dir);
  assert.equal(m.files.length, 1);
  assert.equal(m.files[0].path, "SKILL.md");
  // sha256("hello\n") is well-known
  assert.equal(m.files[0].sha256, "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03");
});

test("two writes of the same content produce the same treeHash (mtime-independent)", async () => {
  const dir = await tmp("mtime");
  await fs.writeFile(path.join(dir, "SKILL.md"), "hello\n");
  const before = await computeContentManifest(dir);
  await new Promise((r) => setTimeout(r, 5));
  await fs.writeFile(path.join(dir, "SKILL.md"), "hello\n");
  const after = await computeContentManifest(dir);
  assert.equal(before.treeHash, after.treeHash);
});

test("files are sorted by path deterministically", async () => {
  const dir = await tmp("sort");
  await fs.writeFile(path.join(dir, "z.md"), "z");
  await fs.writeFile(path.join(dir, "a.md"), "a");
  await fs.writeFile(path.join(dir, "m.md"), "m");
  const m = await computeContentManifest(dir);
  assert.deepEqual(m.files.map((f) => f.path), ["a.md", "m.md", "z.md"]);
});

test("nested directories are walked recursively", async () => {
  const dir = await tmp("nested");
  await fs.mkdir(path.join(dir, "scripts"), { recursive: true });
  await fs.writeFile(path.join(dir, "SKILL.md"), "x");
  await fs.writeFile(path.join(dir, "scripts", "go.sh"), "y");
  const m = await computeContentManifest(dir);
  assert.deepEqual(m.files.map((f) => f.path), ["SKILL.md", "scripts/go.sh"]);
});

test("paths use forward slashes regardless of host OS", async () => {
  const dir = await tmp("paths");
  await fs.mkdir(path.join(dir, "a", "b"), { recursive: true });
  await fs.writeFile(path.join(dir, "a", "b", "c.md"), "c");
  const m = await computeContentManifest(dir);
  assert.equal(m.files[0].path, "a/b/c.md");
});

test(".git/ is ignored by default", async () => {
  const dir = await tmp("git");
  await fs.writeFile(path.join(dir, "SKILL.md"), "x");
  await fs.mkdir(path.join(dir, ".git"), { recursive: true });
  await fs.writeFile(path.join(dir, ".git", "HEAD"), "ref: refs/heads/main\n");
  const m = await computeContentManifest(dir);
  assert.deepEqual(m.files.map((f) => f.path), ["SKILL.md"]);
});

test("a single byte change shifts both file sha256 and the top-level treeHash", async () => {
  const dir = await tmp("tamper");
  await fs.writeFile(path.join(dir, "SKILL.md"), "hello\n");
  const before = await computeContentManifest(dir);
  await fs.writeFile(path.join(dir, "SKILL.md"), "HELLO\n");
  const after = await computeContentManifest(dir);
  assert.notEqual(before.treeHash, after.treeHash);
  assert.notEqual(before.files[0].sha256, after.files[0].sha256);
});

test("custom ignore patterns are honored (and replace defaults)", async () => {
  const dir = await tmp("custom");
  await fs.writeFile(path.join(dir, "SKILL.md"), "x");
  await fs.mkdir(path.join(dir, "node_modules"), { recursive: true });
  await fs.writeFile(path.join(dir, "node_modules", "junk.js"), "z");
  const m = await computeContentManifest(dir, { ignore: ["node_modules"] });
  assert.deepEqual(m.files.map((f) => f.path), ["SKILL.md"]);
});

// ── verifySkillContents ─────────────────────────────────────────────────────

const seedSkill = async () => {
  const dir = await tmp("verify");
  await fs.writeFile(path.join(dir, "SKILL.md"), "hello\n");
  await fs.writeFile(path.join(dir, "manifest.yaml"), "name: x\nversion: 1.0.0\n");
  return dir;
};

test("verifySkillContents returns ok when dir matches the expected manifest", async () => {
  const dir = await seedSkill();
  const expected = await computeContentManifest(dir);
  const result = await verifySkillContents(dir, expected);
  assert.equal(result.ok, true);
  assert.equal(result.treeHash, expected.treeHash);
  assert.deepEqual(result.mismatches, { added: [], removed: [], changed: [] });
});

test("verifySkillContents reports added files", async () => {
  const dir = await seedSkill();
  const expected = await computeContentManifest(dir);
  await fs.writeFile(path.join(dir, "extra.md"), "extra");
  const result = await verifySkillContents(dir, expected);
  assert.equal(result.ok, false);
  assert.deepEqual(result.mismatches.added, ["extra.md"]);
  assert.deepEqual(result.mismatches.removed, []);
  assert.deepEqual(result.mismatches.changed, []);
});

test("verifySkillContents reports removed files", async () => {
  const dir = await seedSkill();
  const expected = await computeContentManifest(dir);
  await fs.unlink(path.join(dir, "manifest.yaml"));
  const result = await verifySkillContents(dir, expected);
  assert.equal(result.ok, false);
  assert.deepEqual(result.mismatches.removed, ["manifest.yaml"]);
});

test("verifySkillContents reports changed files (single byte tamper)", async () => {
  const dir = await seedSkill();
  const expected = await computeContentManifest(dir);
  await fs.writeFile(path.join(dir, "SKILL.md"), "HELLO\n");
  const result = await verifySkillContents(dir, expected);
  assert.equal(result.ok, false);
  assert.deepEqual(result.mismatches.changed, ["SKILL.md"]);
});

test("verifySkillContents reports added + removed + changed in one pass", async () => {
  const dir = await seedSkill();
  const expected = await computeContentManifest(dir);
  await fs.writeFile(path.join(dir, "SKILL.md"), "tampered\n");
  await fs.unlink(path.join(dir, "manifest.yaml"));
  await fs.writeFile(path.join(dir, "new.md"), "new");
  const result = await verifySkillContents(dir, expected);
  assert.equal(result.ok, false);
  assert.deepEqual(result.mismatches.added, ["new.md"]);
  assert.deepEqual(result.mismatches.removed, ["manifest.yaml"]);
  assert.deepEqual(result.mismatches.changed, ["SKILL.md"]);
});

test("verifySkillContents throws when the expected manifest is incomplete", async () => {
  const dir = await seedSkill();
  await assert.rejects(() => verifySkillContents(dir, {}), /manifest/i);
  await assert.rejects(() => verifySkillContents(dir, { treeHash: "x" }), /files/i);
  await assert.rejects(() => verifySkillContents(dir, { files: [] }), /treeHash/i);
});
