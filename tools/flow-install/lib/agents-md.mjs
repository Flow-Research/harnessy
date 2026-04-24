#!/usr/bin/env node

/**
 * flow-install — AGENTS.md marker-based merge
 *
 * Injects or updates a Harnessy framework section in the project's AGENTS.md
 * using <!-- flow:start --> and <!-- flow:end --> markers.
 * All existing project content outside the markers is preserved.
 */

import fs from "node:fs/promises";
import path from "node:path";
import { pathExists, readFileSafe, log } from "./utils.mjs";

// ---------------------------------------------------------------------------
// Harnessy framework section markers
// ---------------------------------------------------------------------------

const FLOW_START = "<!-- flow:start -->";
const FLOW_END = "<!-- flow:end -->";

// ---------------------------------------------------------------------------
// Generate the Harnessy framework section
// ---------------------------------------------------------------------------

const generateFlowSection = (installPaths) => `${FLOW_START}
## Harnessy Framework

> \`FLOW_SKIP_SUBPROJECTS=true\`

This repo is Harnessy-managed.

- Read \`${installPaths.contextDir}/README.md\`
- Read \`${installPaths.contextDir}/AGENTS.md\`
- Global skills: \`~/.agents/skills/\`
- Project skills: \`${installPaths.skillsDir}/\` (if present)
- If inside a sub-project, prefer its local \`.jarvis/context/\`
${FLOW_END}`;

// ---------------------------------------------------------------------------
// Merge Harnessy section into existing AGENTS.md
// ---------------------------------------------------------------------------

export const mergeAgentsMd = async (projectRoot, { dryRun = false, agentsFileRel = "AGENTS.md", installPaths = { contextDir: ".jarvis/context", skillsDir: ".agents/skills" } } = {}) => {
  const agentsPath = path.join(projectRoot, agentsFileRel);
  const flowSection = generateFlowSection(installPaths);

  const existing = await readFileSafe(agentsPath);

  if (!existing) {
    // No AGENTS.md exists — create one with just the Harnessy section
    if (dryRun) {
      log.dryRun(`Would create ${agentsFileRel} with Harnessy framework section`);
      return;
    }
    await fs.mkdir(path.dirname(agentsPath), { recursive: true });
    await fs.writeFile(agentsPath, flowSection + "\n", "utf8");
    log.ok(`${agentsFileRel} created with Harnessy framework section`);
    return;
  }

  // Check for existing markers
  const startIdx = existing.indexOf(FLOW_START);
  const endIdx = existing.indexOf(FLOW_END);

  if (startIdx !== -1 && endIdx !== -1 && endIdx > startIdx) {
    // Update existing Harnessy section
    const before = existing.slice(0, startIdx);
    const after = existing.slice(endIdx + FLOW_END.length);

    const updated = before + flowSection + after;

    if (updated === existing) {
      log.skip("AGENTS.md (Harnessy section already current)");
      return;
    }

    if (dryRun) {
      log.dryRun(`Would update Harnessy section in ${agentsFileRel}`);
      return;
    }

    await fs.writeFile(agentsPath, updated, "utf8");
    log.ok(`${agentsFileRel}: Harnessy section updated`);
    return;
  }

  // No markers found — append Harnessy section
  if (dryRun) {
    log.dryRun(`Would append Harnessy framework section to ${agentsFileRel}`);
    return;
  }

  const appended = existing.trimEnd() + "\n\n" + flowSection + "\n";
  await fs.writeFile(agentsPath, appended, "utf8");
  log.ok(`${agentsFileRel}: Harnessy section appended`);
};
