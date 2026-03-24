#!/usr/bin/env node

/**
 * flow-install — .jarvis/context/ vault scaffolding
 */

import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathExists, ensureDir, log } from "./utils.mjs";

// ---------------------------------------------------------------------------
// Directory structure for the context vault
// ---------------------------------------------------------------------------

const CONTEXT_DIRS = [
  "docs",
  "skills",
  "specs",
  "plans",
  "runbooks",
  "templates",
  "meetings",
  "private",
  "scopes",
];

// ---------------------------------------------------------------------------
// Scaffold .jarvis/context/
// ---------------------------------------------------------------------------

export const scaffoldContext = async (projectRoot, { dryRun = false, contextDirRel = ".jarvis/context" } = {}) => {
  const contextDir = path.join(projectRoot, contextDirRel);

  // Create directory structure
  for (const dir of CONTEXT_DIRS) {
    const full = path.join(contextDir, dir);
    if (await pathExists(full)) {
      log.skip(`${dir}/`);
      continue;
    }
    if (dryRun) {
        log.dryRun(`Would create ${contextDirRel}/${dir}/`);
    } else {
      await ensureDir(full);
        log.ok(`${contextDirRel}/${dir}/`);
    }
  }

  // Create private/<username>/
  const username = os.userInfo().username;
  const privateDir = path.join(contextDir, "private", username);
  if (await pathExists(privateDir)) {
    log.skip(`private/${username}/`);
  } else if (dryRun) {
    log.dryRun(`Would create private/${username}/`);
  } else {
    await ensureDir(privateDir);
    log.ok(`private/${username}/`);
  }

  // Create stub content files (never overwrite existing)
  const stubs = {
    "README.md": generateContextReadme(),
    "local.md.example": generateLocalMdExample(),
    "status.md": generateStatusTemplate(),
    "roadmap.md": generateRoadmapTemplate(),
    "team.md": generateTeamTemplate(),
    "technical-debt.md": generateTechDebtTemplate(),
  };

  for (const [filename, content] of Object.entries(stubs)) {
    const filePath = path.join(contextDir, filename);
    if (await pathExists(filePath)) {
      log.skip(filename);
      continue;
    }
    if (dryRun) {
      log.dryRun(`Would create ${filename}`);
    } else {
      await fs.writeFile(filePath, content, "utf8");
      log.ok(filename);
    }
  }

  return { contextDir };
};

// ---------------------------------------------------------------------------
// Catalog merge
// ---------------------------------------------------------------------------

export const mergeCatalog = async (projectRoot, newEntries, { dryRun = false } = {}) => {
  const catalogPath = path.join(projectRoot, ".jarvis", "context", "skills", "_catalog.md");
  const existing = await fs.readFile(catalogPath, "utf8").catch(() => null);

  if (!existing) {
    // Create fresh
    const content = generateCatalogHeader() + "\n" + newEntries.join("\n---\n\n");
    if (dryRun) {
      log.dryRun("Would create _catalog.md");
    } else {
      await ensureDir(path.dirname(catalogPath));
      await fs.writeFile(catalogPath, content, "utf8");
      log.ok("_catalog.md created");
    }
    return;
  }

  // Merge: find existing names, add missing
  const existingNames = new Set();
  const blocks = existing.split(/\n---\n/);
  for (const block of blocks) {
    const nameMatch = block.match(/^name:\s*"?([^"\n]+)"?/m);
    if (nameMatch) existingNames.add(nameMatch[1].trim());
  }

  const toAdd = newEntries.filter((entry) => {
    const nameMatch = entry.match(/^name:\s*"?([^"\n]+)"?/m);
    return nameMatch && !existingNames.has(nameMatch[1].trim());
  });

  if (toAdd.length === 0) {
    log.skip("_catalog.md (no new entries)");
    return;
  }

  if (dryRun) {
    log.dryRun(`Would add ${toAdd.length} entries to _catalog.md`);
  } else {
    const appended = existing.trimEnd() + "\n\n---\n\n" + toAdd.join("\n---\n\n") + "\n";
    await fs.writeFile(catalogPath, appended, "utf8");
    log.ok(`_catalog.md: ${toAdd.length} entries added`);
  }
};

// ---------------------------------------------------------------------------
// Templates
// ---------------------------------------------------------------------------

function generateContextReadme() {
  return `# .jarvis/context/ — Knowledge Base Protocol

## Purpose

This directory is the canonical knowledge base for this project. AI agents, Jarvis CLI, and human contributors read these files for project context.

## Loading Order

1. \`status.md\` — Canonical current-state document for active work and execution truth
2. \`roadmap.md\` — Canonical phase ordering, milestones, and deferred work
3. \`team.md\` — Canonical ownership and coordination guide
4. \`technical-debt.md\` — Canonical debt register for intentional shortcuts and cleanup

## Optional Supporting Docs

- \`projects.md\` — Workspace or repo inventory when present
- \`decisions.md\` — Settled architectural decisions when present
- \`AGENTS.md\` — Full Flow agent protocol for this installed repo

## Memory System

- Scope registry: \`scopes/_scopes.yaml\`
- Scoped memories: \`scopes/{org,project,project/apps/*}/\`
- User memories: \`private/<username>/\`
- Types: fact, decision, preference, event

## Template Syntax

Files may start with \`{{global}}\`. This is a Jarvis CLI feature; treat as no-op.

## Installed by

[flow-install](https://github.com/Flow-Research/flow-network/tree/main/tools/flow-install)
`;
}

function generateLocalMdExample() {
  return `# Local Context (Machine-Specific)

> This file is gitignored. Copy to \`local.md\` and fill in your values.

## External Projects

| Project | Local Path | Notes |
|---------|------------|-------|
| Jarvis CLI | | Python 3.11+ AI assistant CLI. Use \`uv run jarvis <command>\` |

## Environment Notes

- Node version manager: nvm / fnm / volta
- Default Node version: 22
`;
}

function generateTechDebtTemplate() {
  return `# Technical Debt Register

> Tracked intentional shortcuts, deferred migrations, and knowingly postponed cleanup.
> Every item: ID, status, type, scope, context, impact, proposed resolution, target phase, links.

## Open

_No open debt items._

## Resolved

_No resolved debt items._
`;
}

function generateStatusTemplate() {
  return `# Status

## Current Focus

- _Add the active work stream here._

## Active Work

- _List the in-flight initiatives that reflect current execution truth._

## Blockers

- _List blockers or write "None"._

## Constraints

- _List important constraints or write "None"._

## Next Review

- _Add the next date or milestone when this file should be refreshed._
`;
}

function generateRoadmapTemplate() {
  return `# Roadmap

## Now

- _List the current phase and immediate milestones._

## Next

- _List the next phase or the next major deliverables._

## Later

- _List deferred work, dependencies, or future milestones._

## Notes

- _Capture sequencing assumptions and open roadmap questions._
`;
}

function generateTeamTemplate() {
  return `# Team

## Ownership

| Area | Owner | Notes |
|------|-------|-------|
| _Example_ | _Name_ | _Responsibility summary_ |

## Coordination

- _Describe how work is delegated, reviewed, and handed off._

## Escalation

- _Describe who to involve when blocked on product, design, or engineering._
`;
}

function generateCatalogHeader() {
  return `# Skill Catalog

> Auto-managed by flow-install. Project-specific entries can be added manually.
> Format: YAML blocks separated by ---

`;
}
