import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import readline from "node:readline";
import { getSkillsRootConfig } from "./skills-root.mjs";
import { parseFrontmatter } from "./parse-frontmatter.mjs";

const projectRoot = process.cwd();
const args = process.argv.slice(2);
const yesAll = args.includes("--yes-all");

// ---------------------------------------------------------------------------
// Interactive helpers (same pattern as setup-local.mjs)
// ---------------------------------------------------------------------------

let rl;

const getRL = () => {
  if (!rl) {
    rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  }
  return rl;
};

const confirm = async (question, defaultYes = true) => {
  if (yesAll) return defaultYes;
  const hint = defaultYes ? "[Y/n]" : "[y/N]";
  return new Promise((resolve) => {
    getRL().question(`${question} ${hint}: `, (answer) => {
      const a = (answer.trim() || (defaultYes ? "y" : "n")).toLowerCase();
      resolve(a.startsWith("y"));
    });
  });
};

const closeRL = () => {
  if (rl) {
    rl.close();
    rl = null;
  }
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const pathExists = async (target) => {
  try {
    await fs.access(target);
    return true;
  } catch {
    return false;
  }
};

const collectSkillsFromRoot = async (skillsRoot) => {
  const entries = await fs.readdir(skillsRoot, { withFileTypes: true }).catch(() => []);
  const skills = [];

  for (const entry of entries) {
    if (!entry.isDirectory()) continue;

    const skillDir = path.join(skillsRoot, entry.name);
    const skillMdPath = path.join(skillDir, "SKILL.md");
    const raw = await fs.readFile(skillMdPath, "utf8").catch(() => null);
    if (!raw) continue;

    const { data, body } = parseFrontmatter(raw);
    const name = data.name || entry.name;
    const description = data.description || "";

    if (!description) {
      console.warn(`  ⚠ Skipping ${entry.name}: no description in SKILL.md frontmatter`);
      continue;
    }

    skills.push({ name, dirName: entry.name, description, body, skillDir, data });
  }

  return skills;
};

// ---------------------------------------------------------------------------
// Per-skill plugin generation
// ---------------------------------------------------------------------------

const ensurePluginJson = async (skill) => {
  const metaDir = path.join(skill.skillDir, ".claude-plugin");
  await fs.mkdir(metaDir, { recursive: true });

  const pluginJson = {
    name: skill.dirName,
    version: "1.0.0",
    description: skill.description,
  };

  await fs.writeFile(
    path.join(metaDir, "plugin.json"),
    JSON.stringify(pluginJson, null, 2) + "\n",
    "utf8"
  );
};

const ensureCommandFile = async (skill) => {
  const commandsDir = path.join(skill.skillDir, "commands");
  if (await pathExists(commandsDir)) return; // already has commands

  await fs.mkdir(commandsDir, { recursive: true });

  const commandContent = `---\ndescription: ${JSON.stringify(skill.description)}\n---\n\n${skill.body}`;
  await fs.writeFile(
    path.join(commandsDir, `${skill.dirName}.md`),
    commandContent,
    "utf8"
  );
};

// ---------------------------------------------------------------------------
// Marketplace generation
// ---------------------------------------------------------------------------

const generateMarketplaceJson = async (marketplaceDir, skills) => {
  const metaDir = path.join(marketplaceDir, ".claude-plugin");
  await fs.mkdir(metaDir, { recursive: true });

  const marketplace = {
    $schema: "https://anthropic.com/claude-code/marketplace.schema.json",
    name: "flow_network",
    description: "Flow Network skills collection — community and project skills",
    owner: { name: "Flow Network" },
    plugins: skills.map((s) => ({
      name: s.dirName,
      description: s.description.slice(0, 120),
      version: "1.0.0",
      source: `../skills/${s.dirName}`,
      category: "productivity",
    })),
  };

  await fs.writeFile(
    path.join(metaDir, "marketplace.json"),
    JSON.stringify(marketplace, null, 2) + "\n",
    "utf8"
  );
};

// ---------------------------------------------------------------------------
// Settings update
// ---------------------------------------------------------------------------

const updateClaudeSettings = async (marketplacePath, skills) => {
  const settingsPath = path.join(os.homedir(), ".claude", "settings.json");
  let settings = {};

  const raw = await fs.readFile(settingsPath, "utf8").catch(() => null);
  if (raw) {
    try {
      settings = JSON.parse(raw);
    } catch {
      console.warn("  ⚠ Could not parse ~/.claude/settings.json — creating fresh merge.");
    }
  }

  // Marketplace registration
  if (!settings.extraKnownMarketplaces) {
    settings.extraKnownMarketplaces = {};
  }

  settings.extraKnownMarketplaces.flow_network = {
    source: {
      source: "directory",
      path: marketplacePath,
    },
  };

  // Deprecate duru_claude_plugins
  delete settings.extraKnownMarketplaces.duru_claude_plugins;

  // Plugin enablement
  if (!settings.enabledPlugins) {
    settings.enabledPlugins = {};
  }

  // Remove old entries
  delete settings.enabledPlugins["flow-skills@flow_network"];
  const keysToRemove = Object.keys(settings.enabledPlugins).filter(
    (k) => k.endsWith("@duru_claude_plugins")
  );
  for (const key of keysToRemove) {
    delete settings.enabledPlugins[key];
  }

  // Enable each skill
  for (const skill of skills) {
    settings.enabledPlugins[`${skill.dirName}@flow_network`] = true;
  }

  await fs.mkdir(path.dirname(settingsPath), { recursive: true });
  await fs.writeFile(settingsPath, JSON.stringify(settings, null, 2) + "\n", "utf8");
};

// ---------------------------------------------------------------------------
// Cleanup old structure
// ---------------------------------------------------------------------------

const cleanupOldStructure = async (marketplaceDir) => {
  // Remove old flow-skills monolithic plugin if it exists
  const oldPluginDir = path.join(marketplaceDir, "flow-skills");
  if (await pathExists(oldPluginDir)) {
    await fs.rm(oldPluginDir, { recursive: true });
    console.log("  Removed old flow-skills monolithic plugin");
  }
};

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

export const registerClaudeSkills = async () => {
  console.log("\n=== Claude Code skill registration ===\n");

  const wantClaude = await confirm("Register skills for Claude Code?");
  if (!wantClaude) {
    console.log("  Skipped Claude Code registration.\n");
    closeRL();
    return;
  }

  const skillsRootConfig = await getSkillsRootConfig(projectRoot);
  const skillsRoot = skillsRootConfig.skillsRoot;
  const agentsDir = path.dirname(skillsRoot);
  const marketplaceDir = path.join(agentsDir, "claude-marketplace");

  // Cleanup old structure
  await cleanupOldStructure(marketplaceDir);

  // Collect all skills
  console.log(`  Scanning ${skillsRoot} ...`);
  const skills = await collectSkillsFromRoot(skillsRoot);

  if (skills.length === 0) {
    console.log("  No skills with valid SKILL.md found. Nothing to register.\n");
    closeRL();
    return;
  }

  console.log(`  Found ${skills.length} skills with valid metadata`);

  // Generate per-skill plugin structure
  let commandsGenerated = 0;
  for (const skill of skills) {
    await ensurePluginJson(skill);

    const commandsDir = path.join(skill.skillDir, "commands");
    const hadCommands = await pathExists(commandsDir);
    await ensureCommandFile(skill);
    if (!hadCommands) commandsGenerated++;
  }

  console.log(`  Generated .claude-plugin/plugin.json for ${skills.length} skills`);
  console.log(`  Auto-generated commands/ for ${commandsGenerated} skills (${skills.length - commandsGenerated} already had commands)`);

  // Generate marketplace.json
  await generateMarketplaceJson(marketplaceDir, skills);
  console.log(`  Created marketplace.json at ${marketplaceDir}/.claude-plugin/`);

  // Update Claude settings
  await updateClaudeSettings(marketplaceDir, skills);
  console.log(`  Updated ~/.claude/settings.json (${skills.length} plugins enabled, duru_claude_plugins deprecated)`);

  console.log(`\n  ✓ Registered ${skills.length} skills for Claude Code\n`);
  closeRL();
};

// Run directly if this is the entry point
const isDirectRun = !process.argv[1] || process.argv[1].endsWith("register-claude-skills.mjs");
if (isDirectRun) {
  registerClaudeSkills().catch((error) => {
    console.error("Failed to register Claude Code skills:", error);
    closeRL();
    process.exitCode = 1;
  });
}
