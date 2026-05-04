import fs from "node:fs/promises";
import path from "node:path";

import { pathExists, readFileSafe, parseSimpleYaml } from "../utils.mjs";
import { Registry } from "./registry.mjs";

export class LocalRegistry extends Registry {
  constructor(flowInstallRoot) {
    super();
    this.skillsRoot = path.join(flowInstallRoot, "skills");
    this._cache = null;
  }

  async _scan() {
    if (this._cache) return this._cache;
    if (!(await pathExists(this.skillsRoot))) {
      this._cache = new Map();
      return this._cache;
    }

    const entries = await fs.readdir(this.skillsRoot, { withFileTypes: true });
    const map = new Map();

    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      if (entry.name.startsWith("_")) continue;
      const skillDir = path.join(this.skillsRoot, entry.name);
      const skillMd = path.join(skillDir, "SKILL.md");
      if (!(await pathExists(skillMd))) continue;

      const manifestContent = await readFileSafe(path.join(skillDir, "manifest.yaml"));
      const manifest = manifestContent ? parseSimpleYaml(manifestContent) : {};

      map.set(entry.name, {
        name: entry.name,
        version: manifest.version || "0.0.0",
        manifest,
        sourceDir: skillDir,
      });
    }

    this._cache = map;
    return map;
  }

  async list() {
    const map = await this._scan();
    return Array.from(map.values()).map(({ name, version, manifest }) => ({
      name,
      version,
      manifest,
    }));
  }

  async fetch(name, _version) {
    const map = await this._scan();
    const entry = map.get(name);
    if (!entry) throw new Error(`Skill not found in local registry: ${name}`);
    return { dir: entry.sourceDir, manifest: entry.manifest };
  }
}
