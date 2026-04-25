import fs from "node:fs/promises";
import path from "node:path";

import { readRegistryLock } from "./lockfile.mjs";
import { verifySkillContents } from "./content-manifest.mjs";

const dirExists = async (p) => {
  try {
    const stat = await fs.stat(p);
    return stat.isDirectory();
  } catch {
    return false;
  }
};

export const verifySkills = async ({ lockfilePath, installedRoot }) => {
  if (!lockfilePath) throw new Error("verifySkills requires lockfilePath");
  if (!installedRoot) throw new Error("verifySkills requires installedRoot");

  const lock = await readRegistryLock(lockfilePath);
  const skills = lock.skills || {};
  const results = [];

  for (const [name, entry] of Object.entries(skills)) {
    if (entry.registry !== "artifacts") continue;

    const installedDir = path.join(installedRoot, name);
    if (!(await dirExists(installedDir))) {
      results.push({ name, version: entry.version, ok: false, reason: "not_installed" });
      continue;
    }

    if (!entry.treeHash || !Array.isArray(entry.files)) {
      results.push({ name, version: entry.version, ok: false, reason: "no_manifest" });
      continue;
    }

    const verdict = await verifySkillContents(installedDir, {
      treeHash: entry.treeHash,
      files: entry.files,
    });
    results.push({
      name,
      version: entry.version,
      ok: verdict.ok,
      treeHash: verdict.treeHash,
      mismatches: verdict.mismatches,
    });
  }

  return results;
};
