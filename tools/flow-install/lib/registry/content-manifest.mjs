import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";

// Canonical content manifest for a skill directory:
//   files: sorted [{path, sha256}], paths use forward slashes
//   treeHash: sha256 of "<path>\t<sha256>\n" lines, joined and sha-256'd
//
// Anyone with the same files can reproduce the treeHash byte-for-byte. This is
// what we record at publish time and re-check at verify time.

const DEFAULT_IGNORES = Object.freeze([".git", ".DS_Store"]);

const sha256Hex = (buf) => crypto.createHash("sha256").update(buf).digest("hex");

const isIgnored = (relPath, patterns) => {
  const segments = relPath.split("/");
  return segments.some((seg) => patterns.includes(seg));
};

const walk = async (root, current, files, patterns) => {
  const entries = await fs.readdir(current, { withFileTypes: true });
  for (const entry of entries) {
    const abs = path.join(current, entry.name);
    const rel = path.relative(root, abs).replace(/\\/g, "/");
    if (isIgnored(rel, patterns)) continue;
    if (entry.isDirectory()) {
      await walk(root, abs, files, patterns);
    } else if (entry.isFile()) {
      const content = await fs.readFile(abs);
      files.push({ path: rel, sha256: sha256Hex(content) });
    }
  }
};

export const computeContentManifest = async (dir, { ignore = DEFAULT_IGNORES } = {}) => {
  const files = [];
  await walk(dir, dir, files, ignore);
  files.sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));
  const canonical = files.map((f) => `${f.path}\t${f.sha256}`).join("\n") + (files.length ? "\n" : "");
  const treeHash = sha256Hex(canonical);
  return { files, treeHash };
};

export const verifySkillContents = async (dir, expected, opts = {}) => {
  if (!expected || typeof expected !== "object") {
    throw new Error("verifySkillContents requires an expected manifest");
  }
  if (!Array.isArray(expected.files)) {
    throw new Error("verifySkillContents expected manifest must include files[]");
  }
  if (typeof expected.treeHash !== "string") {
    throw new Error("verifySkillContents expected manifest must include treeHash");
  }

  const actual = await computeContentManifest(dir, opts);

  if (actual.treeHash === expected.treeHash) {
    return { ok: true, treeHash: actual.treeHash, mismatches: { added: [], removed: [], changed: [] } };
  }

  const expectedByPath = new Map(expected.files.map((f) => [f.path, f.sha256]));
  const actualByPath = new Map(actual.files.map((f) => [f.path, f.sha256]));

  const added = [];
  const removed = [];
  const changed = [];

  for (const [p, sha] of actualByPath) {
    if (!expectedByPath.has(p)) added.push(p);
    else if (expectedByPath.get(p) !== sha) changed.push(p);
  }
  for (const p of expectedByPath.keys()) {
    if (!actualByPath.has(p)) removed.push(p);
  }

  return {
    ok: false,
    treeHash: actual.treeHash,
    mismatches: { added: added.sort(), removed: removed.sort(), changed: changed.sort() },
  };
};
