#!/usr/bin/env node

/**
 * flow-install — lifecycle script installation to ~/.scripts/
 *                plus optional repo-local lifecycle scripts for CI-safe project installs
 */

import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  readJsonSafe,
  writeJson,
  ensureDir,
  GLOBAL_SCRIPTS_DIR,
  log,
} from "./utils.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FLOW_SCRIPT_SOURCE_DIR = path.resolve(__dirname, "../../../scripts/flow");

const CANONICAL_FLOW_SCRIPTS = [
  "agents.mjs",
  "cleanup-stale-plugins.mjs",
  "register-claude-skills.mjs",
  "register-codex-skills.mjs",
  "register-opencode-skills.mjs",
  "register-skills.mjs",
  "sync-rules.mjs",
  "validate-skills.mjs",
  "verify-harness.mjs",
];

const EXTRA_SCRIPT_TEMPLATES = {
  "skills-root.mjs": generateSkillsRoot,
  "skills-root.config.json": generateSkillsRootConfig,
  "parse-frontmatter.mjs": generateParseFrontmatter,
};

const readCanonicalScript = async (filename) => {
  const sourcePath = path.join(FLOW_SCRIPT_SOURCE_DIR, filename);
  return fs.readFile(sourcePath, "utf8");
};

const writeScriptFiles = async (targetDir, filenames, { dryRun = false, labelPrefix = "" } = {}) => {
  await ensureDir(targetDir);

  for (const filename of filenames) {
    const targetPath = path.join(targetDir, filename);
    const content = await readCanonicalScript(filename);
    if (dryRun) {
      log.dryRun(`Would write ${labelPrefix}${filename}`);
      continue;
    }
    await fs.mkdir(path.dirname(targetPath), { recursive: true });
    await fs.writeFile(targetPath, content, "utf8");
    log.ok(`${labelPrefix}${filename}`);
  }
};

// ---------------------------------------------------------------------------
// Install scripts to ~/.scripts/
// ---------------------------------------------------------------------------

export const installScripts = async ({ dryRun = false } = {}) => {
  await writeScriptFiles(GLOBAL_SCRIPTS_DIR, CANONICAL_FLOW_SCRIPTS, {
    dryRun,
    labelPrefix: dryRun ? "" : "",
  });

  for (const [filename, generator] of Object.entries(EXTRA_SCRIPT_TEMPLATES)) {
    const targetPath = path.join(GLOBAL_SCRIPTS_DIR, filename);
    const content = generator();
    if (dryRun) {
      log.dryRun(`Would generate ${filename} in ~/.scripts/`);
    } else {
      await fs.writeFile(targetPath, content, "utf8");
      log.ok(`${filename} generated -> ~/.scripts/`);
    }
  }

  const pathEntries = (process.env.PATH || "").split(path.delimiter).filter(Boolean);
  if (!pathEntries.includes(GLOBAL_SCRIPTS_DIR)) {
    log.warn(`~/.scripts is not currently on PATH (${GLOBAL_SCRIPTS_DIR})`);
  }

  return { installed: CANONICAL_FLOW_SCRIPTS.length + Object.keys(EXTRA_SCRIPT_TEMPLATES).length };
};

export const installProjectScripts = async (projectRoot, { dryRun = false, scriptsDirRel = "scripts/flow" } = {}) => {
  const targetDir = path.join(projectRoot, scriptsDirRel);
  await writeScriptFiles(targetDir, CANONICAL_FLOW_SCRIPTS, {
    dryRun,
    labelPrefix: `${scriptsDirRel}/`,
  });
};

// ---------------------------------------------------------------------------
// Patch project package.json to reference scripts/flow
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
    "skills:register:opencode": `node ${scriptsDirRef}/register-opencode-skills.mjs`,
    "skills:register:codex": `node ${scriptsDirRef}/register-codex-skills.mjs`,
    "flow:cleanup": `node ${scriptsDirRef}/cleanup-stale-plugins.mjs`,
    "flow:sync": "bash ${HOME}/.cache/harnessy/install.sh --in-place || node ${HOME}/.cache/harnessy/tools/flow-install/index.mjs --yes",
    "flow:sync:force": "bash ${HOME}/.cache/harnessy/install.sh --in-place --force || node ${HOME}/.cache/harnessy/tools/flow-install/index.mjs --yes --force",
    "flow:sync:remote": "bash ${HOME}/.cache/harnessy/install.sh --in-place --refresh-source || node ${HOME}/.cache/harnessy/tools/flow-install/index.mjs --yes",
    "flow:sync:remote:force": "bash ${HOME}/.cache/harnessy/install.sh --in-place --refresh-source --force || node ${HOME}/.cache/harnessy/tools/flow-install/index.mjs --yes --force",
    "harness:verify": `node ${scriptsDirRef}/verify-harness.mjs`,
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
