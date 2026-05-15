#!/usr/bin/env node

/**
 * flow-install — skill installation to ~/.agents/skills/ + agent registration
 */

import fs from "node:fs/promises";
import path from "node:path";
import {
  pathExists,
  readFileSafe,
  readJsonSafe,
  copyDir,
  ensureDir,
  parseSimpleYaml,
  compareSemver,
  GLOBAL_SKILLS_DIR,
  GLOBAL_COMMANDS_DIR,
  homeDir,
  log,
} from "./utils.mjs";
import {
  registerAllAgentSkills as registerAllAgents,
  registerClaudeSkills as registerClaudeAgentSkills,
  registerOpenCodeSkills as registerOpenCodeAgentSkills,
  registerCodexSkills as registerCodexAgentSkills,
  listActiveSkills,
} from "./agents.mjs";
import { planSkillsRoot } from "./dependencies.mjs";

const RESERVED_SCRIPT_NAMES = new Set([
  "register-skills.mjs",
  "validate-skills.mjs",
  "register-claude-skills.mjs",
  "register-opencode-skills.mjs",
  "register-codex-skills.mjs",
  "verify-harness.mjs",
  "sync-rules.mjs",
  "skills-root.mjs",
  "skills-root.config.json",
  "parse-frontmatter.mjs",
]);

const installSkillExecutables = async (skillDir, { dryRun = false } = {}) => {
  const scriptsDir = path.join(skillDir, "scripts");
  if (!(await pathExists(scriptsDir))) return 0;

  await ensureDir(GLOBAL_COMMANDS_DIR);
  let installed = 0;
  const entries = await fs.readdir(scriptsDir, { withFileTypes: true });

  for (const entry of entries) {
    if (!entry.isFile()) continue;
    if (entry.name.endsWith(".md")) continue;
    if (path.extname(entry.name) !== "") continue;
    if (RESERVED_SCRIPT_NAMES.has(entry.name)) {
      log.warn(`Skipping command shim ${entry.name}; reserved by Harnessy lifecycle scripts`);
      continue;
    }

    const sourcePath = path.join(scriptsDir, entry.name);
    const targetPath = path.join(GLOBAL_COMMANDS_DIR, entry.name);

    if (!dryRun) {
      await fs.chmod(sourcePath, 0o755).catch(() => {});
    }

    if (dryRun) {
      log.dryRun(`Would link ${entry.name} -> ~/.local/bin/${entry.name}`);
      installed++;
      continue;
    }

    try {
      const existingStats = await fs.lstat(targetPath);
      if (existingStats.isSymbolicLink()) {
        const existingTarget = await fs.readlink(targetPath);
        const resolvedExisting = path.resolve(path.dirname(targetPath), existingTarget);
        if (resolvedExisting === sourcePath) {
          installed++;
          continue;
        }
      }
      log.warn(`Skipping command shim ${entry.name}; ~/.local/bin/${entry.name} already exists`);
      continue;
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }

    await fs.symlink(sourcePath, targetPath);
    log.ok(`command shim installed -> ~/.local/bin/${entry.name}`);
    installed++;
  }

  return installed;
};

// ---------------------------------------------------------------------------
// Collect skills from the flow-install skills/ source directory
// ---------------------------------------------------------------------------

const collectSourceSkills = async (flowInstallRoot) => {
  const skillsDir = path.join(flowInstallRoot, "skills");
  if (!(await pathExists(skillsDir))) return [];

  const entries = await fs.readdir(skillsDir, { withFileTypes: true });
  const skills = [];

  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const skillDir = path.join(skillsDir, entry.name);
    const skillMd = path.join(skillDir, "SKILL.md");
    const manifestPath = path.join(skillDir, "manifest.yaml");

    if (!(await pathExists(skillMd))) continue;

    const manifestContent = await readFileSafe(manifestPath);
    const manifest = manifestContent ? parseSimpleYaml(manifestContent) : {};

    skills.push({
      name: entry.name,
      version: manifest.version || "0.0.0",
      sourceDir: skillDir,
      manifest,
    });
  }

  return skills;
};

// ---------------------------------------------------------------------------
// Install skills to ~/.agents/skills/ with version comparison
// ---------------------------------------------------------------------------

export const installSkills = async (flowInstallRoot, { dryRun = false, force = false } = {}) => {
  const sourceSkills = await collectSourceSkills(flowInstallRoot);
  if (sourceSkills.length === 0) {
    log.warn("No skills found in flow-install skills/ directory.");
    return { installed: 0, skipped: 0, upgraded: 0 };
  }

  await ensureDir(GLOBAL_SKILLS_DIR);

  let installed = 0;
  let skipped = 0;
  let upgraded = 0;
  let commandShims = 0;

  for (const skill of sourceSkills) {
    const targetDir = path.join(GLOBAL_SKILLS_DIR, skill.name);
    const targetManifest = path.join(targetDir, "manifest.yaml");

    if (await pathExists(targetDir)) {
      // Check version
      const existingContent = await readFileSafe(targetManifest);
      const existing = existingContent ? parseSimpleYaml(existingContent) : {};
      const cmp = compareSemver(skill.version, existing.version || "0.0.0");

      if (cmp <= 0 && !force) {
        // Check for unpromoted improvements (installed version ahead of source)
        const installedAhead = compareSemver(existing.version || "0.0.0", skill.version) > 0;
        if (installedAhead) {
          const improvementsFile = path.join(homeDir, ".agents", "traces", skill.name, "improvements.ndjson");
          const improvementsContent = await readFileSafe(improvementsFile);
          if (improvementsContent) {
            const unpromoted = improvementsContent.split("\n").filter(l => {
              if (!l.trim()) return false;
              try { const r = JSON.parse(l); return r.improvement_id && !r.type; } catch { return false; }
            }).length;
            if (unpromoted > 0) {
              log.warn(`${skill.name}: installed v${existing.version} has ${unpromoted} unpromoted improvement(s) vs source v${skill.version}. Run /skill-promote ${skill.name} before upgrading source.`);
            }
          }
        }
        log.skip(`${skill.name} (${existing.version || "unknown"} >= ${skill.version})`);
        skipped++;
        commandShims += await installSkillExecutables(targetDir, { dryRun });
        continue;
      }

      // Upgrade — but warn if installed had improvements that will be overwritten
      const improvementsFile = path.join(homeDir, ".agents", "traces", skill.name, "improvements.ndjson");
      const improvementsContent = await readFileSafe(improvementsFile);
      if (improvementsContent) {
        const unpromoted = improvementsContent.split("\n").filter(l => {
          if (!l.trim()) return false;
          try { const r = JSON.parse(l); return r.improvement_id && !r.type; } catch { return false; }
        }).length;
        if (unpromoted > 0) {
          log.warn(`${skill.name}: overwriting installed v${existing.version} (${unpromoted} unpromoted improvement(s)) with source v${skill.version}. Improvements may be lost. Consider /skill-promote first.`);
        }
      }

      if (dryRun) {
        log.dryRun(`Would upgrade ${skill.name}: ${existing.version} -> ${skill.version}`);
        upgraded++;
        continue;
      }

      await fs.rm(targetDir, { recursive: true });
      await copyDir(skill.sourceDir, targetDir);
      log.ok(`${skill.name} upgraded: ${existing.version} -> ${skill.version}`);
      upgraded++;
      commandShims += await installSkillExecutables(targetDir, { dryRun });
    } else {
      // Fresh install
      if (dryRun) {
        log.dryRun(`Would install ${skill.name} v${skill.version}`);
        installed++;
        continue;
      }

      await copyDir(skill.sourceDir, targetDir);
      log.ok(`${skill.name} v${skill.version} installed`);
      installed++;
      commandShims += await installSkillExecutables(targetDir, { dryRun });
    }
  }

  // Copy _shared/ support directory (trace scripts, metrics, etc.)
  const sharedSource = path.join(flowInstallRoot, "skills", "_shared");
  const sharedTarget = path.join(GLOBAL_SKILLS_DIR, "_shared");
  if (await pathExists(sharedSource)) {
    if (!dryRun) {
      await ensureDir(sharedTarget);
      const sharedEntries = await fs.readdir(sharedSource, { withFileTypes: true });
      let sharedCount = 0;
      for (const entry of sharedEntries) {
        if (!entry.isFile()) continue;
        await fs.copyFile(path.join(sharedSource, entry.name), path.join(sharedTarget, entry.name));
        sharedCount++;
      }
      log.ok(`_shared/ support scripts synced (${sharedCount} files)`);
    } else {
      log.dryRun("Would sync _shared/ support scripts");
    }
  }

  if (!dryRun) {
    const dependencyChecks = planSkillsRoot(GLOBAL_SKILLS_DIR);
    const missingByManifest = dependencyChecks.filter((entry) => entry.missingRequired.length > 0);
    if (missingByManifest.length > 0) {
      log.warn(`${missingByManifest.length} installed skill manifest(s) still have missing required dependencies`);
      for (const entry of missingByManifest.slice(0, 5)) {
        const missing = entry.missingRequired.map((item) => `${item.kind}:${item.name}`).join(", ");
        log.warn(`${path.basename(path.dirname(entry.manifestPath))}: ${missing}`);
      }
      log.info(`Review with: flow-deps check --skills-root "${GLOBAL_SKILLS_DIR}"`);
      log.info(`Install explicitly with: flow-deps install --skills-root "${GLOBAL_SKILLS_DIR}"`);
    }
  }

  return { installed, skipped, upgraded, commandShims, total: sourceSkills.length };
};

export const registerClaudeSkills = async ({ dryRun = false } = {}) => {
  if (!(await pathExists(GLOBAL_SKILLS_DIR))) {
    log.warn("No skills directory at ~/.agents/skills/. Skipping Claude registration.");
    return 0;
  }
  const skills = await listActiveSkills(GLOBAL_SKILLS_DIR);
  return registerClaudeAgentSkills(skills, { dryRun });
};

export const registerOpenCodeSkills = async (_projectRoot, { dryRun = false } = {}) => (
  registerOpenCodeAgentSkills(GLOBAL_SKILLS_DIR, { dryRun })
);

export const registerCodexSkills = async ({ dryRun = false } = {}) => {
  if (!(await pathExists(GLOBAL_SKILLS_DIR))) {
    log.warn("No skills directory at ~/.agents/skills/. Skipping Codex registration.");
    return 0;
  }
  const skills = await listActiveSkills(GLOBAL_SKILLS_DIR);
  return registerCodexAgentSkills(skills, { dryRun });
};

export const registerAgentSkills = async ({ dryRun = false } = {}) => (
  registerAllAgents(GLOBAL_SKILLS_DIR, { dryRun })
);
