#!/usr/bin/env node

/**
 * flow-install — install destination selection for copied framework files
 */

import path from "node:path";
import { log, promptWithDefault } from "./utils.mjs";

const DEFAULT_PATHS = {
  agentsFile: "AGENTS.md",
  contextDir: ".jarvis/context",
  skillsDir: ".agents/skills",
  scriptsDir: "scripts/flow",
};

const normalizeRelative = (value, { file = false } = {}) => {
  const trimmed = value.trim().replace(/^\.\//, "").replace(/\/+/g, "/");
  const normalized = path.posix.normalize(trimmed || (file ? "AGENTS.md" : "."));
  if (normalized.startsWith("../") || normalized === "..") {
    throw new Error(`Path must stay inside the project: ${value}`);
  }
  return normalized;
};

export const resolveInstallPaths = async (projectRoot, projectInfo, { yesAll = false, reconfigure = false } = {}) => {
  const saved = projectInfo.existing.lockfile?.installPaths || {};
  const current = {
    agentsFile: saved.agentsFile || DEFAULT_PATHS.agentsFile,
    contextDir: saved.contextDir || DEFAULT_PATHS.contextDir,
    skillsDir: saved.skillsDir || DEFAULT_PATHS.skillsDir,
    scriptsDir: saved.scriptsDir || DEFAULT_PATHS.scriptsDir,
  };

  if (yesAll || (projectInfo.existing.lockfile?.installPaths && !reconfigure)) {
    return current;
  }

  log.header("Choose install locations");
  log.info("Press Enter to accept the default for each file type.");

  const prompts = [
    {
      key: "agentsFile",
      label: "AGENTS.md file",
      file: true,
    },
    {
      key: "contextDir",
      label: "Context vault directory",
    },
    {
      key: "skillsDir",
      label: "Project-local skills directory",
    },
    {
      key: "scriptsDir",
      label: "Lifecycle scripts directory",
    },
  ];

  for (const prompt of prompts) {
    const answer = await promptWithDefault(`${prompt.label}`, current[prompt.key]);
    current[prompt.key] = normalizeRelative(answer, { file: prompt.file });
  }

  return current;
};
