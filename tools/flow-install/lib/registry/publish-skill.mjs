import fs from "node:fs/promises";
import path from "node:path";

import {
  EMPTY_LOCK,
  readRegistryLock,
  upsertSkillEntry,
  writeRegistryLock,
} from "./lockfile.mjs";
import { computeContentManifest } from "./content-manifest.mjs";

// RECONCILE: how Cloudflare Artifacts authenticates git pushes. The
// x-access-token user pattern matches GitHub/GitLab conventions and is the
// safest default; if Artifacts wants a different scheme, narrow this helper
// once we have the docs in front of us.
export const authedPushUrl = (remote, token) => {
  if (!/^https?:\/\//.test(remote)) return remote;
  const url = new URL(remote);
  url.username = "x-access-token";
  url.password = token;
  return url.toString();
};

const dirExists = async (p) => {
  try {
    const stat = await fs.stat(p);
    return stat.isDirectory();
  } catch {
    return false;
  }
};

export const publishSkill = async ({
  name,
  version,
  skillsRoot,
  lockfilePath,
  workerClient,
  git,
  now = () => new Date(),
}) => {
  const skillDir = path.join(skillsRoot, name);
  if (!(await dirExists(skillDir))) {
    throw new Error(`Skill directory not found: ${skillDir} (skill "${name}")`);
  }

  const { remote, writeToken } = await workerClient.createSkill(name);
  const pushUrl = authedPushUrl(remote, writeToken);
  const { sha } = await git.publish({ skillDir, name, version, pushUrl });
  const { files, treeHash } = await computeContentManifest(skillDir);

  // Record the published entry on the Worker (KV-backed lockfile that
  // consumers fetch). Done before the local lockfile write so a Worker failure
  // leaves no half-state.
  await workerClient.recordPublish(name, { version, sha, remote, treeHash, files });

  const existing = await readRegistryLock(lockfilePath);
  const base = existing.version ? existing : structuredClone(EMPTY_LOCK);
  const entry = {
    version,
    sha,
    remote,
    registry: "artifacts",
    publishedAt: now().toISOString(),
    treeHash,
    files,
  };
  const updated = upsertSkillEntry(base, name, entry);
  await writeRegistryLock(lockfilePath, updated);

  return { name, ...entry };
};
