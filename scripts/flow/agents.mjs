#!/usr/bin/env node

import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

const HOME = os.homedir();

export const resolveHome = (p) => p.startsWith("~/") ? path.join(HOME, p.slice(2)) : p;
export const resolveGlobalSkillsDir = () => {
  const configured = (process.env.AGENTS_SKILLS_ROOT || "").trim();
  return configured ? path.resolve(resolveHome(configured)) : path.join(HOME, ".agents", "skills");
};

export const GLOBAL_SKILLS_DIR = resolveGlobalSkillsDir();
export const GLOBAL_CLAUDE_MARKETPLACE = path.join(HOME, ".agents", "claude-marketplace");
export const GLOBAL_CLAUDE_SKILLS_DIR = path.join(HOME, ".claude", "skills");
export const GLOBAL_CLAUDE_SETTINGS = path.join(HOME, ".claude", "settings.json");
export const GLOBAL_CLAUDE_INSTALLED_PLUGINS = path.join(HOME, ".claude", "plugins", "installed_plugins.json");
export const GLOBAL_CLAUDE_PLUGIN_CACHE = path.join(HOME, ".claude", "plugins", "cache", "harnessy");
export const GLOBAL_OPENCODE_CONFIG = path.join(HOME, ".config", "opencode", "opencode.json");
export const GLOBAL_CODEX_SKILLS_DIR = path.join(HOME, ".codex", "skills", "harnessy");
export const AGENT_REGISTRY = [
  { id: "claude", componentKey: "claude", label: "Claude Code", cli: "claude", registerScript: "register-claude-skills.mjs" },
  { id: "opencode", componentKey: "opencode", label: "OpenCode", cli: "opencode", registerScript: "register-opencode-skills.mjs" },
  { id: "codex", componentKey: "codex", label: "Codex", cli: "codex", registerScript: "register-codex-skills.mjs" },
];

const FLOW_CLAUDE_PLUGIN_ID = "harnessy";
const GLOBAL_CLAUDE_KNOWN_MARKETPLACES = path.join(HOME, ".claude", "plugins", "known_marketplaces.json");

export const pathExists = async (p) => {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
};

export const readFileSafe = async (p) => {
  try {
    return await fs.readFile(p, "utf8");
  } catch (e) {
    if (e.code === "ENOENT") return null;
    throw e;
  }
};

export const readJsonSafe = async (p) => {
  const raw = await readFileSafe(p);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
};

export const writeJson = async (p, data) => {
  await fs.mkdir(path.dirname(p), { recursive: true });
  await fs.writeFile(p, JSON.stringify(data, null, 2) + "\n", "utf8");
};

export const parseSimpleYaml = (content) => {
  const data = {};
  if (!content) return data;
  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const idx = trimmed.indexOf(":");
    if (idx === -1) continue;
    let value = trimmed.slice(idx + 1).trim();
    if ((value.startsWith("\"") && value.endsWith("\"")) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    data[trimmed.slice(0, idx).trim()] = value;
  }
  return data;
};

export const parseFrontmatter = (content) => {
  if (!content || !content.startsWith("---")) return null;
  const endIdx = content.indexOf("\n---", 3);
  if (endIdx === -1) return null;
  return { data: parseSimpleYaml(content.slice(4, endIdx)), body: content.slice(endIdx + 4).trim() };
};

export const normalizePath = async (candidate) => {
  try {
    return await fs.realpath(candidate);
  } catch {
    return path.resolve(candidate);
  }
};

const copyDir = async (src, dest) => {
  await fs.mkdir(dest, { recursive: true });
  for (const entry of await fs.readdir(src, { withFileTypes: true })) {
    const s = path.join(src, entry.name);
    const d = path.join(dest, entry.name);
    if (entry.isDirectory()) await copyDir(s, d);
    else await fs.copyFile(s, d);
  }
};

const syncSkillDirectory = async (skills, targetDir) => {
  await fs.mkdir(targetDir, { recursive: true });
  const desired = new Map(skills.map((skill) => [skill.name, skill.skillDir]));

  for (const skill of skills) {
    const targetPath = path.join(targetDir, skill.name);
    try {
      const existing = await fs.lstat(targetPath);
      if (existing.isSymbolicLink()) {
        const existingTarget = await fs.readlink(targetPath);
        const resolvedExisting = path.resolve(path.dirname(targetPath), existingTarget);
        if (resolvedExisting === skill.skillDir) continue;
      }
      await fs.rm(targetPath, { recursive: true, force: true });
    } catch {}

    try {
      await fs.symlink(skill.skillDir, targetPath, "dir");
    } catch {
      await fs.cp(skill.skillDir, targetPath, { recursive: true });
    }
  }

  const existingEntries = await fs.readdir(targetDir, { withFileTypes: true }).catch(() => []);
  for (const entry of existingEntries) {
    if (!desired.has(entry.name)) {
      await fs.rm(path.join(targetDir, entry.name), { recursive: true, force: true });
    }
  }
};

export const listActiveSkills = async (skillsRoot = GLOBAL_SKILLS_DIR) => {
  const entries = await fs.readdir(skillsRoot, { withFileTypes: true }).catch(() => []);
  const skills = [];

  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const skillDir = path.join(skillsRoot, entry.name);
    const skillMd = await readFileSafe(path.join(skillDir, "SKILL.md"));
    if (!skillMd) continue;
    const frontmatter = parseFrontmatter(skillMd);
    const description = frontmatter?.data?.description || "";
    if (!description) continue;
    skills.push({ name: entry.name, description, skillDir, body: frontmatter?.body || skillMd });
  }

  return skills.sort((a, b) => a.name.localeCompare(b.name));
};

export const registerClaudeSkills = async (skills) => {
  await syncSkillDirectory(skills, GLOBAL_CLAUDE_SKILLS_DIR);

  const pluginRoot = path.join(GLOBAL_CLAUDE_MARKETPLACE, FLOW_CLAUDE_PLUGIN_ID);
  const pluginManifestDir = path.join(pluginRoot, ".claude-plugin");
  const pluginSkillsDir = path.join(pluginRoot, "skills");
  await fs.mkdir(path.join(GLOBAL_CLAUDE_MARKETPLACE, ".claude-plugin"), { recursive: true });
  await fs.mkdir(pluginManifestDir, { recursive: true });
  await fs.mkdir(pluginSkillsDir, { recursive: true });
  await syncSkillDirectory(skills, pluginSkillsDir);

  await writeJson(path.join(pluginManifestDir, "plugin.json"), {
    name: FLOW_CLAUDE_PLUGIN_ID,
    version: "1.0.0",
    description: "Harnessy skills bundle",
  });

  await writeJson(path.join(GLOBAL_CLAUDE_MARKETPLACE, ".claude-plugin", "marketplace.json"), {
    name: "harnessy",
    owner: { name: "Harnessy" },
    plugins: [{
      name: FLOW_CLAUDE_PLUGIN_ID,
      description: "Harnessy skills bundle",
      version: "1.0.0",
      category: "productivity",
      source: `./${FLOW_CLAUDE_PLUGIN_ID}`,
    }],
  });

  const settings = (await readJsonSafe(GLOBAL_CLAUDE_SETTINGS)) || {};
  if (!settings.extraKnownMarketplaces) settings.extraKnownMarketplaces = {};
  settings.extraKnownMarketplaces.harnessy = {
    source: { source: "directory", path: GLOBAL_CLAUDE_MARKETPLACE },
  };
  delete settings.extraKnownMarketplaces.duru_claude_plugins;
  if (!settings.enabledPlugins) settings.enabledPlugins = {};
  settings.enabledPlugins[`${FLOW_CLAUDE_PLUGIN_ID}@harnessy`] = true;
  delete settings.enabledPlugins["flow-skills@harnessy"];
  for (const skill of skills) delete settings.enabledPlugins[`${skill.name}@harnessy`];
  await writeJson(GLOBAL_CLAUDE_SETTINGS, settings);

  const known = (await readJsonSafe(GLOBAL_CLAUDE_KNOWN_MARKETPLACES)) || {};
  known.harnessy = {
    source: { source: "directory", path: GLOBAL_CLAUDE_MARKETPLACE },
    installLocation: GLOBAL_CLAUDE_MARKETPLACE,
    lastUpdated: new Date().toISOString(),
  };
  await writeJson(GLOBAL_CLAUDE_KNOWN_MARKETPLACES, known);

  const installed = await readJsonSafe(GLOBAL_CLAUDE_INSTALLED_PLUGINS);
  if (installed?.plugins) {
    const bundledKey = `${FLOW_CLAUDE_PLUGIN_ID}@harnessy`;
    const staleKeys = Object.keys(installed.plugins).filter((key) => key.endsWith("@harnessy") && key !== bundledKey);
    if (staleKeys.length > 0) {
      for (const key of staleKeys) delete installed.plugins[key];
      await writeJson(GLOBAL_CLAUDE_INSTALLED_PLUGINS, installed);
    }
  }

  if (await pathExists(GLOBAL_CLAUDE_PLUGIN_CACHE)) {
    const cacheEntries = await fs.readdir(GLOBAL_CLAUDE_PLUGIN_CACHE, { withFileTypes: true });
    for (const entry of cacheEntries.filter((item) => item.isDirectory() && item.name !== FLOW_CLAUDE_PLUGIN_ID)) {
      await fs.rm(path.join(GLOBAL_CLAUDE_PLUGIN_CACHE, entry.name), { recursive: true, force: true });
    }
  }

  const oldMarketplaceSkills = path.join(GLOBAL_CLAUDE_MARKETPLACE, "skills");
  if (await pathExists(oldMarketplaceSkills)) {
    await fs.rm(oldMarketplaceSkills, { recursive: true, force: true });
  }

  for (const skill of skills) {
    const perSkillPluginDir = path.join(skill.skillDir, ".claude-plugin");
    if (await pathExists(perSkillPluginDir)) await fs.rm(perSkillPluginDir, { recursive: true, force: true });
  }

  return skills.length;
};

export const registerOpenCodeSkills = async (skillsRoot = GLOBAL_SKILLS_DIR) => {
  const config = (await readJsonSafe(GLOBAL_OPENCODE_CONFIG)) || { $schema: "https://opencode.ai/config.json" };
  if (!config.skills) config.skills = {};
  if (!Array.isArray(config.skills.paths)) config.skills.paths = [];
  const normalizedPaths = [];
  for (const existingPath of config.skills.paths) {
    const normalized = await normalizePath(existingPath);
    if (!normalizedPaths.includes(normalized)) normalizedPaths.push(normalized);
  }
  const normalizedSkillsRoot = await normalizePath(skillsRoot);
  if (!normalizedPaths.includes(normalizedSkillsRoot)) normalizedPaths.push(normalizedSkillsRoot);
  config.skills.paths = normalizedPaths;
  await writeJson(GLOBAL_OPENCODE_CONFIG, config);
  return normalizedPaths.length;
};

export const registerCodexSkills = async (skills) => {
  await syncSkillDirectory(skills, GLOBAL_CODEX_SKILLS_DIR);
  return skills.length;
};

export const registerAllAgentSkills = async (skillsRoot = GLOBAL_SKILLS_DIR) => {
  const skills = await listActiveSkills(skillsRoot);
  const claudeCount = await registerClaudeSkills(skills);
  const opencodePathCount = await registerOpenCodeSkills(skillsRoot);
  const codexCount = await registerCodexSkills(skills);
  return { skills, claudeCount, opencodePathCount, codexCount };
};
