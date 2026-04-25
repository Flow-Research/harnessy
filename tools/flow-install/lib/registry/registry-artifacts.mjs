import fs from "node:fs/promises";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

import { Registry } from "./registry.mjs";
import { readRegistryLock } from "./lockfile.mjs";

const execFileAsync = promisify(execFile);

const runGit = async (args, env, cwd) => {
  try {
    return await execFileAsync("git", cwd ? ["-C", cwd, ...args] : args, {
      env: { ...process.env, ...env },
    });
  } catch (error) {
    const stderr = error?.stderr?.toString?.().trim() || "";
    const detail = stderr || error.message;
    const wrapped = new Error(`git ${args[0]} failed: ${detail}`);
    wrapped.cause = error;
    throw wrapped;
  }
};

// RECONCILE: how Cloudflare Artifacts authenticates git fetches. Mirrors the
// publish-side helper; verify against current Cloudflare docs at deploy time.
export const authedFetchUrl = (remote, token) => {
  if (!token || !/^https?:\/\//.test(remote)) return remote;
  const url = new URL(remote);
  url.username = "x-access-token";
  url.password = token;
  return url.toString();
};

const dirExistsNonEmpty = async (p) => {
  try {
    const entries = await fs.readdir(p);
    return entries.length > 0;
  } catch {
    return false;
  }
};

const parseManifestYaml = (raw) => {
  // Minimal YAML for our manifest shape (key: value per line). Mirrors the
  // tolerant parser used by LocalRegistry.
  const out = {};
  for (const line of raw.split(/\r?\n/)) {
    const m = /^([A-Za-z0-9_]+):\s*(.*)$/.exec(line);
    if (!m) continue;
    out[m[1]] = m[2].replace(/^["']|["']$/g, "").trim();
  }
  return out;
};

export class ArtifactsRegistry extends Registry {
  constructor({ lockfilePath, cacheDir, token, gitEnv = {} } = {}) {
    super();
    if (!lockfilePath) throw new Error("ArtifactsRegistry requires lockfilePath");
    if (!cacheDir) throw new Error("ArtifactsRegistry requires cacheDir");
    this.lockfilePath = lockfilePath;
    this.cacheDir = cacheDir;
    this.token = token;
    this.gitEnv = gitEnv;
  }

  async _entry(name) {
    const lock = await readRegistryLock(this.lockfilePath);
    return lock.skills?.[name];
  }

  async list() {
    const lock = await readRegistryLock(this.lockfilePath);
    const skills = lock.skills || {};
    return Object.entries(skills)
      .filter(([, entry]) => entry.registry === "artifacts")
      .map(([name, entry]) => ({ name, version: entry.version }));
  }

  async fetch(name, version) {
    const entry = await this._entry(name);
    if (!entry) throw new Error(`Skill not found in registry lockfile: ${name}`);
    if (entry.registry !== "artifacts") {
      throw new Error(`Skill "${name}" registry is "${entry.registry}", not "artifacts"`);
    }
    if (entry.version !== version) {
      throw new Error(
        `Skill "${name}" lockfile version is ${entry.version}, requested ${version}`,
      );
    }

    const cachePath = path.join(this.cacheDir, name, entry.sha);

    if (await dirExistsNonEmpty(cachePath)) {
      const manifestRaw = await fs.readFile(path.join(cachePath, "manifest.yaml"), "utf8")
        .catch(() => "");
      return { dir: cachePath, sha: entry.sha, manifest: parseManifestYaml(manifestRaw) };
    }

    await fs.mkdir(path.dirname(cachePath), { recursive: true });
    const cloneUrl = authedFetchUrl(entry.remote, this.token);

    try {
      await runGit(
        ["clone", "--depth", "1", "--branch", `v${version}`, cloneUrl, cachePath],
        this.gitEnv,
      );
    } catch (cloneError) {
      await fs.rm(cachePath, { recursive: true, force: true });
      throw cloneError;
    }

    const { stdout } = await runGit(["rev-parse", "HEAD"], this.gitEnv, cachePath);
    const actualSha = stdout.trim();
    if (actualSha !== entry.sha) {
      await fs.rm(cachePath, { recursive: true, force: true });
      throw new Error(
        `SHA mismatch for ${name}@${version}: lockfile has ${entry.sha.slice(0, 7)}, ` +
        `clone HEAD is ${actualSha.slice(0, 7)}`,
      );
    }

    const manifestRaw = await fs.readFile(path.join(cachePath, "manifest.yaml"), "utf8")
      .catch(() => "");
    return { dir: cachePath, sha: entry.sha, manifest: parseManifestYaml(manifestRaw) };
  }
}
