#!/usr/bin/env node

/**
 * flow-install — lifecycle script installation to ~/.scripts/
 *                plus optional repo-local lifecycle scripts for CI-safe project installs
 */

import fs from "node:fs/promises";
import path from "node:path";
import {
  pathExists,
  readJsonSafe,
  writeJson,
  ensureDir,
  GLOBAL_SCRIPTS_DIR,
  log,
} from "./utils.mjs";

// ---------------------------------------------------------------------------
// Scripts to install globally
// ---------------------------------------------------------------------------

const SCRIPT_TEMPLATES = {
  "register-skills.mjs": generateRegisterSkills,
  "validate-skills.mjs": generateValidateSkills,
  "register-claude-skills.mjs": generateRegisterClaudeSkills,
  "sync-rules.mjs": generateSyncRules,
  "skills-root.mjs": generateSkillsRoot,
  "skills-root.config.json": generateSkillsRootConfig,
  "parse-frontmatter.mjs": generateParseFrontmatter,
};

// ---------------------------------------------------------------------------
// Install scripts to ~/.scripts/
// ---------------------------------------------------------------------------

export const installScripts = async (flowInstallRoot, { dryRun = false } = {}) => {
  await ensureDir(GLOBAL_SCRIPTS_DIR);

  const existingScriptsDir = path.join(flowInstallRoot, "..", "..", "scripts");
  let installed = 0;

  for (const [filename, generator] of Object.entries(SCRIPT_TEMPLATES)) {
    const targetPath = path.join(GLOBAL_SCRIPTS_DIR, filename);

    // Try to copy from the existing Flow Network scripts/ first
    const existingPath = path.join(existingScriptsDir, filename);
    if (await pathExists(existingPath)) {
      if (dryRun) {
        log.dryRun(`Would install ${filename} to ~/.scripts/`);
      } else {
        await fs.copyFile(existingPath, targetPath);
        log.ok(`${filename} -> ~/.scripts/`);
      }
      installed++;
      continue;
    }

    // Fall back to generating the script
    const content = generator();
    if (dryRun) {
      log.dryRun(`Would generate ${filename} in ~/.scripts/`);
    } else {
      await fs.writeFile(targetPath, content, "utf8");
      log.ok(`${filename} generated -> ~/.scripts/`);
    }
    installed++;
  }

  return { installed };
};

export const installProjectScripts = async (projectRoot, { dryRun = false, scriptsDirRel = "scripts/flow" } = {}) => {
  const targetDir = path.join(projectRoot, scriptsDirRel);
  await ensureDir(targetDir);

  const projectTemplates = {
    "register-skills.mjs": generateRegisterSkills,
    "validate-skills.mjs": generateValidateSkills,
    "register-claude-skills.mjs": generateRegisterClaudeSkills,
    "sync-rules.mjs": generateSyncRules,
  };

  for (const [filename, generator] of Object.entries(projectTemplates)) {
    const targetPath = path.join(targetDir, filename);
    const content = generator();
    if (dryRun) {
      log.dryRun(`Would write ${path.join(scriptsDirRel, filename)}`);
    } else {
      await fs.mkdir(path.dirname(targetPath), { recursive: true });
      await fs.writeFile(targetPath, content, "utf8");
      log.ok(`${path.join(scriptsDirRel, filename)}`);
    }
  }
};

// ---------------------------------------------------------------------------
// Patch project package.json to reference ~/.scripts/
// ---------------------------------------------------------------------------

export const patchPackageJson = async (projectRoot, { dryRun = false, scriptsDirRel = "scripts/flow" } = {}) => {
  const pkgPath = path.join(projectRoot, "package.json");
  const pkg = await readJsonSafe(pkgPath);
  if (!pkg) {
    log.warn("No package.json found. Skipping script patching.");
    return;
  }

  if (!pkg.scripts) pkg.scripts = {};

  const scriptsDirRef = scriptsDirRel.replace(/\\/g, "/").replace(/\/$/, "");

  const desired = {
    "skills:validate": `node ${scriptsDirRef}/validate-skills.mjs`,
    "skills:register": `node ${scriptsDirRef}/register-skills.mjs`,
    "skills:register:claude": `node ${scriptsDirRef}/register-claude-skills.mjs`,
    "postinstall": `node ${scriptsDirRef}/sync-rules.mjs`,
  };

  let changed = false;
  for (const [name, command] of Object.entries(desired)) {
    if (pkg.scripts[name] === command) continue;

    if (dryRun) {
      if (pkg.scripts[name]) {
        log.dryRun(`Would update script "${name}": ${pkg.scripts[name]} -> ${command}`);
      } else {
        log.dryRun(`Would add script "${name}": ${command}`);
      }
    } else {
      pkg.scripts[name] = command;
    }
    changed = true;
  }

  if (changed && !dryRun) {
    await writeJson(pkgPath, pkg);
    log.ok("package.json scripts updated");
  } else if (!changed) {
    log.skip("package.json scripts already current");
  }
};

// ---------------------------------------------------------------------------
// Script generators (fallback if Flow Network scripts/ not available)
// ---------------------------------------------------------------------------

function generateRegisterSkills() {
  return `#!/usr/bin/env node
/**
 * Register project-local skills from .agents/skills/ to ~/.agents/skills/
 * Auto-generated by flow-install. Do not edit manually.
 */
import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";

const GLOBAL_SKILLS_DIR = path.join(os.homedir(), ".agents", "skills");
const projectRoot = process.cwd();
const projectSkillsRoot = path.join(projectRoot, ".agents", "skills");

const pathExists = async (p) => { try { await fs.access(p); return true; } catch { return false; } };
const copyDir = async (src, dest) => {
  await fs.mkdir(dest, { recursive: true });
  for (const entry of await fs.readdir(src, { withFileTypes: true })) {
    const s = path.join(src, entry.name), d = path.join(dest, entry.name);
    entry.isDirectory() ? await copyDir(s, d) : await fs.copyFile(s, d);
  }
};

const run = async () => {
  await fs.mkdir(GLOBAL_SKILLS_DIR, { recursive: true });
  if (!(await pathExists(projectSkillsRoot))) { console.log("No .agents/skills/ found. Nothing to register."); return; }
  const entries = await fs.readdir(projectSkillsRoot, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const skillDir = path.join(projectSkillsRoot, entry.name);
    if (!(await pathExists(path.join(skillDir, "SKILL.md")))) continue;
    const target = path.join(GLOBAL_SKILLS_DIR, entry.name);
    if (await pathExists(target)) await fs.rm(target, { recursive: true });
    await copyDir(skillDir, target);
    console.log("  OK " + entry.name);
  }
  console.log("Skills registered to " + GLOBAL_SKILLS_DIR);
};

run().catch((e) => { console.error("Registration failed:", e); process.exitCode = 1; });
`;
}

function generateValidateSkills() {
  return `#!/usr/bin/env node
/**
 * Validate project-local skills in .agents/skills/.
 * Auto-generated by flow-install.
 */
import fs from "node:fs/promises";
import path from "node:path";

const projectRoot = process.cwd();
const skillsRoot = path.join(projectRoot, ".agents", "skills");
const required = ["name","type","version","owner","status","blast_radius","description","permissions","data_categories","egress","invoke","location"];

const run = async () => {
  const errors = [];
  let entries;
  try { entries = await fs.readdir(skillsRoot, { withFileTypes: true }); } catch { console.log("No .agents/skills/ found."); return; }
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const mPath = path.join(skillsRoot, entry.name, "manifest.yaml");
    let content; try { content = await fs.readFile(mPath, "utf8"); } catch { errors.push("Missing manifest.yaml in " + entry.name); continue; }
    const data = {};
    for (const line of content.split("\\n")) {
      const i = line.indexOf(":"); if (i === -1) continue;
      data[line.slice(0, i).trim()] = line.slice(i + 1).trim();
    }
    for (const f of required) { if (!data[f]) errors.push(entry.name + ": missing " + f); }
  }
  if (errors.length) { console.error("Validation failed:\\n" + errors.map(e => "- " + e).join("\\n")); process.exitCode = 1; }
  else console.log("Skill validation passed.");
};

run().catch((e) => { console.error(e); process.exitCode = 1; });
`;
}

function generateRegisterClaudeSkills() {
  return `#!/usr/bin/env node
/**
 * Register Claude Code skills from ~/.agents/skills/.
 * Auto-generated by flow-install.
 */
console.log("Claude skill registration is handled by flow-install. Run: npx flow-install --skills");
`;
}

function generateSyncRules() {
  return `#!/usr/bin/env node
/**
 * Postinstall: ensure ~/.agents/skills/ exists.
 * Auto-generated by flow-install.
 */
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

const dir = path.join(os.homedir(), ".agents", "skills");
await fs.mkdir(dir, { recursive: true }).catch(() => {});
`;
}

function generateSkillsRoot() {
  return `import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

const defaultConfig = { placeholder: "\${AGENTS_SKILLS_ROOT}", envVar: "AGENTS_SKILLS_ROOT", defaultRelativeToHome: ".agents/skills" };

export const getSkillsRootConfig = async (projectRoot) => {
  const configPath = path.join(os.homedir(), ".scripts", "skills-root.config.json");
  let config = defaultConfig;
  try { config = { ...defaultConfig, ...JSON.parse(await fs.readFile(configPath, "utf8")) }; } catch {}
  const envValue = process.env[config.envVar];
  const skillsRoot = envValue?.trim() || path.join(os.homedir(), config.defaultRelativeToHome);
  return { ...config, skillsRoot };
};
`;
}

function generateSkillsRootConfig() {
  return JSON.stringify({
    placeholder: "${AGENTS_SKILLS_ROOT}",
    envVar: "AGENTS_SKILLS_ROOT",
    defaultRelativeToHome: ".agents/skills",
  }, null, 2) + "\n";
}

function generateParseFrontmatter() {
  return `/**
 * Simple YAML frontmatter parser.
 * Auto-generated by flow-install.
 */
export const parseFrontmatter = (content) => {
  if (!content?.startsWith("---")) return null;
  const end = content.indexOf("\\n---", 3);
  if (end === -1) return null;
  const fm = content.slice(4, end);
  const body = content.slice(end + 4).trim();
  const data = {};
  for (const line of fm.split("\\n")) {
    const i = line.indexOf(":"); if (i === -1) continue;
    let val = line.slice(i+1).trim();
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) val = val.slice(1,-1);
    data[line.slice(0,i).trim()] = val;
  }
  return { data, body };
};
`;
}
