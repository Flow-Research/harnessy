#!/usr/bin/env node

/**
 * flow-install — hook installation to harnessy plugin + pipeline script deployment
 */

import fs from "node:fs/promises";
import path from "node:path";
import {
  pathExists,
  copyDir,
  ensureDir,
  writeIfMissing,
  GLOBAL_COMMANDS_DIR,
  GLOBAL_CLAUDE_MARKETPLACE,
  log,
} from "./utils.mjs";

const HARNESSY_ROOT = path.join(GLOBAL_CLAUDE_MARKETPLACE, "harnessy");

// ---------------------------------------------------------------------------
// Install hooks into the harnessy plugin directory
// ---------------------------------------------------------------------------

/**
 * Copies tools/flow-install/hooks/ → ~/.agents/claude-marketplace/harnessy/hooks/
 * so Claude Code discovers the hooks via the plugin's hooks.json manifest.
 */
export const installHooks = async (flowInstallDir, { dryRun = false } = {}) => {
  const sourceDir = path.join(flowInstallDir, "hooks");
  const targetDir = path.join(HARNESSY_ROOT, "hooks");

  if (!(await pathExists(sourceDir))) {
    log.warn("No hooks/ directory found in flow-install source.");
    return { installed: false };
  }

  if (dryRun) {
    log.dryRun("Would install hooks to ~/.agents/claude-marketplace/harnessy/hooks/");
    return { installed: false };
  }

  await ensureDir(targetDir);
  // Remove stale hooks dir before copying (ensures clean slate)
  await fs.rm(targetDir, { recursive: true, force: true });
  await copyDir(sourceDir, targetDir);
  log.ok("Pipeline hooks installed -> ~/.agents/claude-marketplace/harnessy/hooks/");
  return { installed: true };
};

// ---------------------------------------------------------------------------
// Deploy pipeline helper scripts to ~/.local/bin/
// ---------------------------------------------------------------------------

const PIPELINE_SCRIPTS = ["pipeline-trigger", "stale-gate-monitor"];

/**
 * Makes pipeline-trigger and stale-gate-monitor available on PATH
 * using the same symlink-with-fallback pattern as skill executables.
 */
export const installPipelineScripts = async (flowInstallDir, { dryRun = false } = {}) => {
  const scriptsDir = path.join(flowInstallDir, "scripts");
  await ensureDir(GLOBAL_COMMANDS_DIR);

  let installed = 0;

  for (const scriptName of PIPELINE_SCRIPTS) {
    const sourcePath = path.join(scriptsDir, scriptName);
    const targetPath = path.join(GLOBAL_COMMANDS_DIR, scriptName);

    if (!(await pathExists(sourcePath))) {
      log.warn(`Pipeline script ${scriptName} not found in harness`);
      continue;
    }

    if (dryRun) {
      log.dryRun(`Would link ${scriptName} -> ~/.local/bin/${scriptName}`);
      installed++;
      continue;
    }

    // Check if target already exists and is a correct symlink
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
      // Exists but points elsewhere or is a regular file — overwrite
      await fs.rm(targetPath, { force: true });
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }

    await fs.chmod(sourcePath, 0o755).catch(() => {});
    await fs.symlink(sourcePath, targetPath);
    log.ok(`pipeline script installed -> ~/.local/bin/${scriptName}`);
    installed++;
  }

  return { installed };
};

// ---------------------------------------------------------------------------
// Scaffold .jarvis/hooks.yaml with defaults
// ---------------------------------------------------------------------------

const DEFAULT_HOOKS_YAML = `# Flow pipeline hook configuration
# Customize notification channels, SLA thresholds, and protected file patterns.

notifications:
  desktop: true
  webhook_url: null

sla:
  stale_gate_hours: 4

protected_patterns: ["_shared/*.py", "program.md"]
`;

/**
 * Creates .jarvis/hooks.yaml with sensible defaults if it doesn't already exist.
 */
export const scaffoldHooksConfig = async (projectRoot, { dryRun = false } = {}) => {
  const targetPath = path.join(projectRoot, ".jarvis", "hooks.yaml");

  if (await pathExists(targetPath)) {
    log.skip(".jarvis/hooks.yaml already exists");
    return { created: false };
  }

  if (dryRun) {
    log.dryRun("Would scaffold .jarvis/hooks.yaml");
    return { created: false };
  }

  const created = await writeIfMissing(targetPath, DEFAULT_HOOKS_YAML);
  if (created) {
    log.ok(".jarvis/hooks.yaml scaffolded with defaults");
  }
  return { created };
};
