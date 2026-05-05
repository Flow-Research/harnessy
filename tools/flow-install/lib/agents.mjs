import fs from "node:fs/promises";
import path from "node:path";
import {
  pathExists,
  readFileSafe,
  readJsonSafe,
  writeJson,
  copyDir,
  ensureDir,
  parseFrontmatter,
  GLOBAL_SKILLS_DIR,
  GLOBAL_CLAUDE_MARKETPLACE,
  GLOBAL_CLAUDE_SETTINGS,
  GLOBAL_CLAUDE_SKILLS_DIR,
  GLOBAL_OPENCODE_CONFIG,
  homeDir,
  log,
} from "./utils.mjs";
import { runCleanup, buildCleanupContext } from "./cleanup.mjs";

const FLOW_CLAUDE_PLUGIN_ID = "harnessy";
const GLOBAL_CLAUDE_KNOWN_MARKETPLACES = path.join(homeDir, ".claude", "plugins", "known_marketplaces.json");
const GLOBAL_CLAUDE_INSTALLED_PLUGINS = path.join(homeDir, ".claude", "plugins", "installed_plugins.json");
const GLOBAL_CLAUDE_PLUGIN_CACHE = path.join(homeDir, ".claude", "plugins", "cache", "harnessy");
const GLOBAL_CODEX_SKILLS_DIR = path.join(homeDir, ".codex", "skills", "harnessy");

export const AGENT_REGISTRY = [
  {
    id: "claude",
    componentKey: "claude",
    label: "Claude Code",
    cli: "claude",
    registerScript: "register-claude-skills.mjs",
  },
  {
    id: "opencode",
    componentKey: "opencode",
    label: "OpenCode",
    cli: "opencode",
    registerScript: "register-opencode-skills.mjs",
  },
  {
    id: "codex",
    componentKey: "codex",
    label: "Codex",
    cli: "codex",
    registerScript: "register-codex-skills.mjs",
  },
];

export const normalizePath = async (candidate) => {
  try {
    return await fs.realpath(candidate);
  } catch {
    return path.resolve(candidate);
  }
};

export const listSkillDirectories = async (skillsRoot = GLOBAL_SKILLS_DIR) => {
  const entries = await fs.readdir(skillsRoot, { withFileTypes: true }).catch(() => []);
  return entries
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
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
    skills.push({
      name: entry.name,
      description,
      skillDir,
      body: frontmatter?.body || skillMd,
    });
  }

  return skills.sort((a, b) => a.name.localeCompare(b.name));
};

const syncSkillDirectory = async (skills, targetDir, { dryRun = false } = {}) => {
  if (dryRun) return skills.length;

  await ensureDir(targetDir);
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

    await fs.symlink(skill.skillDir, targetPath, "dir").catch(async () => {
      await copyDir(skill.skillDir, targetPath);
    });
  }

  const existingEntries = await fs.readdir(targetDir, { withFileTypes: true }).catch(() => []);
  for (const entry of existingEntries) {
    if (!desired.has(entry.name)) {
      await fs.rm(path.join(targetDir, entry.name), { recursive: true, force: true });
    }
  }

  return skills.length;
};

const updateClaudeSettings = async (skills, { dryRun = false } = {}) => {
  if (dryRun) return;

  const existing = await readJsonSafe(GLOBAL_CLAUDE_SETTINGS) || {};

  if (!existing.extraKnownMarketplaces) existing.extraKnownMarketplaces = {};
  existing.extraKnownMarketplaces.harnessy = {
    source: { source: "directory", path: GLOBAL_CLAUDE_MARKETPLACE },
  };
  delete existing.extraKnownMarketplaces.duru_claude_plugins;

  if (!existing.enabledPlugins) existing.enabledPlugins = {};
  existing.enabledPlugins[`${FLOW_CLAUDE_PLUGIN_ID}@harnessy`] = true;
  delete existing.enabledPlugins["flow-skills@harnessy"];
  for (const skill of skills) delete existing.enabledPlugins[`${skill.name}@harnessy`];

  await writeJson(GLOBAL_CLAUDE_SETTINGS, existing);
};

const updateClaudeKnownMarketplaces = async ({ dryRun = false } = {}) => {
  if (dryRun) return;

  const known = await readJsonSafe(GLOBAL_CLAUDE_KNOWN_MARKETPLACES) || {};
  known.harnessy = {
    source: { source: "directory", path: GLOBAL_CLAUDE_MARKETPLACE },
    installLocation: GLOBAL_CLAUDE_MARKETPLACE,
    lastUpdated: new Date().toISOString(),
  };
  await ensureDir(path.dirname(GLOBAL_CLAUDE_KNOWN_MARKETPLACES));
  await writeJson(GLOBAL_CLAUDE_KNOWN_MARKETPLACES, known);
};

const cleanupClaudeInstalledPlugins = async ({ dryRun = false } = {}) => {
  if (dryRun) return;

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
    const staleEntries = cacheEntries.filter((entry) => entry.isDirectory() && entry.name !== FLOW_CLAUDE_PLUGIN_ID);
    for (const entry of staleEntries) {
      await fs.rm(path.join(GLOBAL_CLAUDE_PLUGIN_CACHE, entry.name), { recursive: true, force: true });
    }
  }
};

export const registerClaudeSkills = async (skills, { dryRun = false } = {}) => {
  if (skills.length === 0) {
    log.warn("No skills with description frontmatter found.");
    return 0;
  }

  if (dryRun) {
    log.dryRun(`Would register ${skills.length} skills with Claude Code`);
    return skills.length;
  }

  await syncSkillDirectory(skills, GLOBAL_CLAUDE_SKILLS_DIR, { dryRun });

  const marketplaceDir = path.join(GLOBAL_CLAUDE_MARKETPLACE, ".claude-plugin");
  const pluginRoot = path.join(GLOBAL_CLAUDE_MARKETPLACE, FLOW_CLAUDE_PLUGIN_ID);
  const pluginManifestDir = path.join(pluginRoot, ".claude-plugin");
  const pluginSkillsDir = path.join(pluginRoot, "skills");
  await ensureDir(marketplaceDir);
  await ensureDir(pluginManifestDir);
  await ensureDir(pluginSkillsDir);

  await syncSkillDirectory(skills, pluginSkillsDir, { dryRun });

  await writeJson(path.join(pluginManifestDir, "plugin.json"), {
    name: FLOW_CLAUDE_PLUGIN_ID,
    version: "1.0.0",
    description: "Harnessy skills bundle",
  });

  await writeJson(path.join(marketplaceDir, "marketplace.json"), {
    name: "harnessy",
    owner: {
      name: "Harnessy",
    },
    plugins: [
      {
        name: FLOW_CLAUDE_PLUGIN_ID,
        description: "Harnessy skills bundle",
        version: "1.0.0",
        category: "productivity",
        source: `./${FLOW_CLAUDE_PLUGIN_ID}`,
      },
    ],
  });

  await updateClaudeSettings(skills, { dryRun });
  await updateClaudeKnownMarketplaces({ dryRun });
  await cleanupClaudeInstalledPlugins({ dryRun });

  const cleanupCtx = buildCleanupContext(skills, { dryRun, log });
  await runCleanup(cleanupCtx);

  log.ok(`Registered ${skills.length} skills with Claude Code`);
  return skills.length;
};

export const registerOpenCodeSkills = async (skillsRoot = GLOBAL_SKILLS_DIR, { dryRun = false } = {}) => {
  const config = await readJsonSafe(GLOBAL_OPENCODE_CONFIG);
  if (!config) {
    if (!dryRun) log.skip("No OpenCode config found at ~/.config/opencode/opencode.json");
    return 0;
  }

  if (!config.skills) config.skills = {};
  if (!Array.isArray(config.skills.paths)) config.skills.paths = [];

  const normalizedPaths = [];
  for (const existingPath of config.skills.paths) {
    const normalized = await normalizePath(existingPath);
    if (!normalizedPaths.includes(normalized)) normalizedPaths.push(normalized);
  }

  const normalizedSkillsRoot = await normalizePath(skillsRoot);
  if (!normalizedPaths.includes(normalizedSkillsRoot)) {
    if (dryRun) {
      log.dryRun(`Would add ${normalizedSkillsRoot} to OpenCode skills.paths`);
    } else {
      normalizedPaths.push(normalizedSkillsRoot);
    }
  }

  if (!dryRun) {
    config.skills.paths = normalizedPaths;
    await writeJson(GLOBAL_OPENCODE_CONFIG, config);
    log.ok(`OpenCode skills.paths updated (${normalizedPaths.length} path(s))`);
  }

  return normalizedPaths.length;
};

export const registerCodexSkills = async (skills, { dryRun = false } = {}) => {
  if (skills.length === 0) {
    if (!dryRun) log.warn("No skills with description frontmatter found for Codex.");
    return 0;
  }

  if (dryRun) {
    log.dryRun(`Would register ${skills.length} skills with Codex`);
    return skills.length;
  }

  await syncSkillDirectory(skills, GLOBAL_CODEX_SKILLS_DIR, { dryRun });
  log.ok(`Registered ${skills.length} skills with Codex`);
  return skills.length;
};

export const registerAllAgentSkills = async (skillsRoot = GLOBAL_SKILLS_DIR, { dryRun = false } = {}) => {
  const skills = await listActiveSkills(skillsRoot);
  const claudeCount = await registerClaudeSkills(skills, { dryRun });
  const opencodePathCount = await registerOpenCodeSkills(skillsRoot, { dryRun });
  const codexCount = await registerCodexSkills(skills, { dryRun });

  return {
    skills,
    claudeCount,
    opencodePathCount,
    codexCount,
  };
};

export const AGENT_PATHS = {
  claude: {
    skillsDir: GLOBAL_CLAUDE_SKILLS_DIR,
    marketplace: path.join(GLOBAL_CLAUDE_MARKETPLACE, ".claude-plugin", "marketplace.json"),
    settings: GLOBAL_CLAUDE_SETTINGS,
  },
  opencode: {
    config: GLOBAL_OPENCODE_CONFIG,
  },
  codex: {
    skillsDir: GLOBAL_CODEX_SKILLS_DIR,
  },
};
