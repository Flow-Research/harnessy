import fs from "node:fs/promises";
import path from "node:path";

import { ArtifactsRegistry } from "./registry-artifacts.mjs";

const stripTrailingSlash = (url) => String(url).replace(/\/+$/, "");

export const fetchPublicLockfile = async (workerUrl, fetchImpl) => {
  const url = `${stripTrailingSlash(workerUrl)}/lockfile`;
  const res = await fetchImpl(url, { method: "GET" });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Failed to fetch lockfile (${res.status}): ${text || res.statusText}`);
  }
  const raw = await res.text();
  try {
    return JSON.parse(raw);
  } catch (error) {
    throw new Error(`Failed to parse lockfile JSON: ${error.message}`);
  }
};

// Orchestrator. Pure plumbing — fetches the public lockfile, writes it to
// disk, hands an ArtifactsRegistry to the installer, returns a summary.
export const bootstrapInstall = async ({
  workerUrl,
  lockfilePath,
  cacheDir,
  token,
  fetchImpl = globalThis.fetch.bind(globalThis),
  installer,
}) => {
  if (!workerUrl) throw new Error("bootstrapInstall requires workerUrl");
  if (!lockfilePath) throw new Error("bootstrapInstall requires lockfilePath");
  if (!cacheDir) throw new Error("bootstrapInstall requires cacheDir");
  if (!installer || typeof installer.install !== "function") {
    throw new Error("bootstrapInstall requires installer with install(registry)");
  }

  const lockfile = await fetchPublicLockfile(workerUrl, fetchImpl);

  await fs.mkdir(path.dirname(lockfilePath), { recursive: true });
  await fs.writeFile(lockfilePath, JSON.stringify(lockfile, null, 2) + "\n", "utf8");

  const registry = new ArtifactsRegistry({ lockfilePath, cacheDir, token });
  await installer.install(registry);

  return { skillCount: Object.keys(lockfile.skills || {}).length };
};
