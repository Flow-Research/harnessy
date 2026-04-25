import fs from "node:fs/promises";

import { REGISTRY_NAMESPACE } from "./registry.mjs";

export const LOCK_VERSION = 1;

export const EMPTY_LOCK = Object.freeze({
  version: LOCK_VERSION,
  namespace: REGISTRY_NAMESPACE,
  skills: Object.freeze({}),
});

const REQUIRED_FIELDS = ["version", "sha", "remote", "registry"];

export const readRegistryLock = async (filePath) => {
  let raw;
  try {
    raw = await fs.readFile(filePath, "utf8");
  } catch (error) {
    if (error.code === "ENOENT") return structuredClone(EMPTY_LOCK);
    throw error;
  }
  try {
    return JSON.parse(raw);
  } catch (error) {
    throw new Error(`Failed to parse skill-registry.lock.json at ${filePath}: ${error.message}`);
  }
};

export const upsertSkillEntry = (lock, name, entry) => {
  for (const field of REQUIRED_FIELDS) {
    if (entry[field] === undefined || entry[field] === null) {
      throw new Error(`Skill entry for "${name}" missing required field: ${field}`);
    }
  }
  return {
    ...lock,
    skills: {
      ...lock.skills,
      [name]: { ...entry },
    },
  };
};

const sortedStringify = (lock) => {
  const sortedSkills = Object.fromEntries(
    Object.keys(lock.skills).sort().map((k) => [k, lock.skills[k]]),
  );
  return JSON.stringify({ ...lock, skills: sortedSkills }, null, 2) + "\n";
};

export const writeRegistryLock = async (filePath, lock) => {
  await fs.writeFile(filePath, sortedStringify(lock), "utf8");
};
