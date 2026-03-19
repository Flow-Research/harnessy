#!/usr/bin/env node

/**
 * flow-install — project structure auto-detection
 *
 * Detects monorepo type, workspace apps/packages, git org,
 * and existing Flow infrastructure in the target project.
 */

import fs from "node:fs/promises";
import path from "node:path";
import { execSync } from "node:child_process";
import { readJsonSafe, pathExists } from "./utils.mjs";

/**
 * Detect the full project structure from a project root directory.
 * Returns a ProjectInfo object with everything flow-install needs.
 */
export const detectProject = async (projectRoot) => {
  const pkg = await readJsonSafe(path.join(projectRoot, "package.json"));

  const info = {
    root: projectRoot,
    name: pkg?.name || path.basename(projectRoot),
    version: pkg?.version || "0.0.0",
    packageManager: detectPackageManager(pkg),
    monorepo: null,       // { type, workspaceGlobs }
    apps: [],             // [{ name, path, relativePath }]
    packages: [],         // [{ name, path, relativePath }]
    gitOrg: null,         // string or null
    gitRepo: null,        // string or null
    existing: {           // existing Flow infrastructure
      jarvisContext: false,
      agentsDirLocal: false,
      pluginsOpencode: false,
      scopesYaml: false,
      agentsMd: false,
      lockfile: null,     // parsed flow-install.lock.json or null
    },
  };

  // Detect monorepo type
  info.monorepo = await detectMonorepo(projectRoot, pkg);

  // Resolve workspace apps and packages
  if (info.monorepo) {
    const workspaces = await resolveWorkspaces(projectRoot, info.monorepo.workspaceGlobs);
    info.apps = workspaces.filter((w) => w.type === "app");
    info.packages = workspaces.filter((w) => w.type === "package");
  }

  // Detect git org and repo
  const git = detectGitInfo(projectRoot);
  info.gitOrg = git.org;
  info.gitRepo = git.repo;

  // Detect existing infrastructure
  info.existing.jarvisContext = await pathExists(path.join(projectRoot, ".jarvis", "context"));
  info.existing.agentsDirLocal = await pathExists(path.join(projectRoot, ".agents"));
  info.existing.pluginsOpencode = await pathExists(path.join(projectRoot, "plugins", "opencode"));
  info.existing.scopesYaml = await pathExists(path.join(projectRoot, ".jarvis", "context", "scopes", "_scopes.yaml"));
  info.existing.agentsMd = await pathExists(path.join(projectRoot, "AGENTS.md"));
  info.existing.lockfile = await readJsonSafe(path.join(projectRoot, "flow-install.lock.json"));

  return info;
};

// ---------------------------------------------------------------------------
// Monorepo detection
// ---------------------------------------------------------------------------

const detectMonorepo = async (projectRoot, pkg) => {
  // Check for turborepo
  const hasTurbo = await pathExists(path.join(projectRoot, "turbo.json"));

  // Check for Nx
  const hasNx = await pathExists(path.join(projectRoot, "nx.json"));

  // Check for pnpm workspaces
  const hasPnpmWorkspace = await pathExists(path.join(projectRoot, "pnpm-workspace.yaml"));

  // Determine workspace globs
  let workspaceGlobs = [];

  if (hasPnpmWorkspace) {
    const raw = await fs.readFile(path.join(projectRoot, "pnpm-workspace.yaml"), "utf8").catch(() => "");
    // Simple extraction of packages: lines
    const lines = raw.split(/\r?\n/);
    let inPackages = false;
    for (const line of lines) {
      if (/^packages:/.test(line)) {
        inPackages = true;
        continue;
      }
      if (inPackages && /^\s+-\s+/.test(line)) {
        const glob = line.replace(/^\s+-\s+/, "").replace(/['"`]/g, "").trim();
        if (glob) workspaceGlobs.push(glob);
      } else if (inPackages && /^\S/.test(line)) {
        inPackages = false;
      }
    }
  }

  if (workspaceGlobs.length === 0 && pkg?.workspaces) {
    // npm/yarn workspaces in package.json
    const ws = Array.isArray(pkg.workspaces) ? pkg.workspaces : pkg.workspaces?.packages || [];
    workspaceGlobs = ws;
  }

  if (workspaceGlobs.length === 0 && !hasTurbo && !hasNx) {
    return null; // Not a monorepo
  }

  const type = hasTurbo ? "turborepo" : hasNx ? "nx" : "pnpm-workspaces";
  return { type, workspaceGlobs };
};

// ---------------------------------------------------------------------------
// Workspace resolution
// ---------------------------------------------------------------------------

const resolveWorkspaces = async (projectRoot, globs) => {
  const results = [];

  for (const glob of globs) {
    // Convert simple glob like "apps/*" or "packages/*" to directory scan
    const cleanGlob = glob.replace(/\/\*$/, "").replace(/\/\*\*$/, "");
    const parentDir = path.join(projectRoot, cleanGlob);

    if (!(await pathExists(parentDir))) continue;

    const stat = await fs.stat(parentDir);
    if (!stat.isDirectory()) continue;

    const entries = await fs.readdir(parentDir, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      if (entry.name.startsWith(".")) continue;

      const wsDir = path.join(parentDir, entry.name);
      const wsPkg = await readJsonSafe(path.join(wsDir, "package.json"));

      const relativePath = path.relative(projectRoot, wsDir);
      const type = classifyWorkspace(relativePath);

      results.push({
        name: wsPkg?.name || entry.name,
        dirName: entry.name,
        path: wsDir,
        relativePath,
        type,
      });
    }
  }

  return results;
};

const classifyWorkspace = (relativePath) => {
  if (relativePath.startsWith("apps/") || relativePath.startsWith("app/")) return "app";
  if (relativePath.startsWith("packages/") || relativePath.startsWith("libs/")) return "package";
  if (relativePath.startsWith("tools/") || relativePath.startsWith("scripts/")) return "tool";
  return "package"; // default
};

// ---------------------------------------------------------------------------
// Git info detection
// ---------------------------------------------------------------------------

const detectGitInfo = (projectRoot) => {
  try {
    const remote = execSync("git remote get-url origin", {
      cwd: projectRoot,
      encoding: "utf8",
      stdio: ["pipe", "pipe", "pipe"],
    }).trim();

    // Parse org and repo from common remote URL formats
    // git@github.com:org/repo.git
    // https://github.com/org/repo.git
    const sshMatch = remote.match(/[:\/@]([^/]+)\/([^/.]+)(?:\.git)?$/);
    if (sshMatch) {
      return { org: sshMatch[1], repo: sshMatch[2] };
    }

    return { org: null, repo: null };
  } catch {
    return { org: null, repo: null };
  }
};

// ---------------------------------------------------------------------------
// Package manager detection
// ---------------------------------------------------------------------------

const detectPackageManager = (pkg) => {
  if (pkg?.packageManager) {
    if (pkg.packageManager.startsWith("pnpm")) return "pnpm";
    if (pkg.packageManager.startsWith("yarn")) return "yarn";
    if (pkg.packageManager.startsWith("npm")) return "npm";
  }
  return "pnpm"; // default
};
