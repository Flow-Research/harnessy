import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import {
  Registry,
  REGISTRY_NAMESPACE,
  formatRef,
  parseRef,
} from "../lib/registry/registry.mjs";
import { LocalRegistry } from "../lib/registry/registry-local.mjs";

const makeFixture = async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "harnessy-registry-"));
  const skillsDir = path.join(root, "skills");
  await fs.mkdir(skillsDir, { recursive: true });

  const writeSkill = async (name, version, withManifest = true) => {
    const dir = path.join(skillsDir, name);
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(path.join(dir, "SKILL.md"), `# ${name}\n`);
    if (withManifest) {
      await fs.writeFile(path.join(dir, "manifest.yaml"), `name: ${name}\nversion: ${version}\n`);
    }
  };

  await writeSkill("alpha", "1.2.3");
  await writeSkill("beta", "0.0.1");
  await writeSkill("no-manifest", "0.0.0", false);

  // Underscore-prefixed dir: must be filtered out of registry listings.
  const sharedDir = path.join(skillsDir, "_shared");
  await fs.mkdir(sharedDir, { recursive: true });
  await fs.writeFile(path.join(sharedDir, "SKILL.md"), "# shared\n");

  // Directory without SKILL.md: must be skipped.
  await fs.mkdir(path.join(skillsDir, "not-a-skill"), { recursive: true });

  return { root, skillsDir };
};

test("formatRef + parseRef round-trip with namespace constant", () => {
  const ref = formatRef("issue-flow", "0.8.1");
  assert.equal(ref, "flow/issue-flow@0.8.1");
  const parsed = parseRef(ref);
  assert.deepEqual(parsed, { namespace: REGISTRY_NAMESPACE, name: "issue-flow", version: "0.8.1" });
});

test("parseRef rejects malformed refs", () => {
  assert.throws(() => parseRef("not-a-ref"), /Invalid skill ref/);
  assert.throws(() => parseRef("flow/foo"), /Invalid skill ref/);
  assert.throws(() => parseRef("@1.0.0"), /Invalid skill ref/);
});

test("Registry base class throws on unimplemented methods", async () => {
  const r = new Registry();
  await assert.rejects(() => r.list(), /not implemented/);
  await assert.rejects(() => r.fetch("x", "1"), /not implemented/);
});

test("LocalRegistry.list() enumerates skills with SKILL.md and skips others", async () => {
  const { root } = await makeFixture();
  const reg = new LocalRegistry(root);
  const list = await reg.list();
  const names = list.map((s) => s.name).sort();
  assert.deepEqual(names, ["alpha", "beta", "no-manifest"]);
  assert.ok(!names.includes("_shared"), "underscore-prefixed dirs must be filtered");
  assert.ok(!names.includes("not-a-skill"), "dirs without SKILL.md must be skipped");
});

test("LocalRegistry uses manifest version, falls back to 0.0.0 when missing", async () => {
  const { root } = await makeFixture();
  const reg = new LocalRegistry(root);
  const list = await reg.list();
  const byName = Object.fromEntries(list.map((s) => [s.name, s]));
  assert.equal(byName.alpha.version, "1.2.3");
  assert.equal(byName.beta.version, "0.0.1");
  assert.equal(byName["no-manifest"].version, "0.0.0");
});

test("LocalRegistry.fetch() returns the skill source dir for a known skill", async () => {
  const { root, skillsDir } = await makeFixture();
  const reg = new LocalRegistry(root);
  const result = await reg.fetch("alpha", "1.2.3");
  assert.equal(path.normalize(result.dir), path.normalize(path.join(skillsDir, "alpha")));
});

test("LocalRegistry.fetch() also returns the parsed manifest", async () => {
  const { root } = await makeFixture();
  const reg = new LocalRegistry(root);
  const result = await reg.fetch("alpha", "1.2.3");
  assert.equal(result.manifest.name, "alpha");
  assert.equal(result.manifest.version, "1.2.3");
});

test("LocalRegistry.fetch() throws for unknown skill", async () => {
  const { root } = await makeFixture();
  const reg = new LocalRegistry(root);
  await assert.rejects(() => reg.fetch("does-not-exist", "1.0.0"), /not found/);
});

test("LocalRegistry returns empty list when skills dir missing", async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "harnessy-registry-empty-"));
  const reg = new LocalRegistry(root);
  const list = await reg.list();
  assert.deepEqual(list, []);
});

