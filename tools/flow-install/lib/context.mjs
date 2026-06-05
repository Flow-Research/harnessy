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
  "docs/standards",
  "docs/strategy",
  "skills",
  "specs",
  "profiles",
  "deployments",
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
    "docs/standards/README.md": generateStandardsReadme(),
    "docs/standards/skill-feedback-protocol.md": generateSkillFeedbackProtocol(),
    "docs/strategy/README.md": generateStrategyReadme(),
    "profiles/qa.json": generateQaProfileTemplate(),
    "profiles/ci.json": generateCiProfileTemplate(),
    "profiles/deploy.json": generateDeployProfileTemplate(),
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

For strategy, ideation, issue intake, PRD, and architecture tradeoff work, also read:
5. \`docs/strategy/README.md\` — Strategy folder guide and suggested read order
6. The relevant strategy docs linked from \`docs/strategy/README.md\`

For runtime contracts, use:
7. \`profiles/qa.json\` — QA source paths, test roots, result outputs, and test environment policy
8. \`profiles/ci.json\` — CI gates, release trigger, and local override policy
9. \`profiles/deploy.json\` — deployment apps, environments, provider adapters, and evidence policy

For development standards, read as relevant:
10. \`docs/standards/skill-feedback-protocol.md\` — mandatory capture triggers for reusable skill lessons

## Optional Supporting Docs

- \`projects.md\` — Workspace or repo inventory when present
- \`decisions.md\` — Settled architectural decisions when present
- \`AGENTS.md\` — Full Harnessy agent protocol for this installed repo

## Standard Strategy Folder

- \`docs/strategy/\` is the standard home for strategic intent, operating thesis, and business-model documents.
- \`docs/standards/\` is the standard home for shared Harnessy engineering, QA, CI, deployment, and testing standards.
- \`profiles/\` is the standard home for machine-readable runtime contracts.
- Use it to store org-level strategy docs that explain why the product exists, what leverage it creates, and which workflows matter most.
- Issue intake and brainstorming should cite this folder when it exists.

## Memory System

- Scope registry: \`scopes/_scopes.yaml\`
- Scoped memories: \`scopes/{org,project,project/apps/*}/\`
- User memories: \`private/<username>/\`
- Types: fact, decision, preference, event

## Template Syntax

Files may start with \`{{global}}\`. This is a Jarvis CLI feature; treat as no-op.

## Installed by

[flow-install](https://github.com/Flow-Research/harnessy/tree/main/tools/flow-install)
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

function generateStandardsReadme() {
  return `# Standards

Shared Harnessy standards for this repository.

Recommended baseline documents:

- \`qa-process.md\` — QA profiles, regression specs, drift, coverage, and validator expectations
- \`testing-strategy.md\` — integration-first testing, Testcontainers preference, and mock exceptions
- \`ci-process.md\` — CI gates, packaging, deployment, rollback, and evidence
- \`skill-feedback-protocol.md\` — mandatory trace capture triggers for reusable skill lessons
`;
}

function generateSkillFeedbackProtocol() {
  return `# Skill Feedback Protocol

Harnessy skills improve through decision traces. Agents must capture useful
skill feedback as structured traces instead of leaving it only in chat,
temporary notes, or memory.

## Mandatory Capture Triggers

Capture feedback whenever any of these occur during skill-backed work:

- The user explicitly says to treat something as feedback, learning, or a skill
  improvement.
- A skill misses a required step, uses a brittle assumption, or needs a manual
  workaround.
- A deterministic command, wrapper, profile, or artifact contract is missing or
  weaker than the work requires.
- A deployment, QA, browser, CI, provider, dependency, packaging, security, or
  mobile/runtime issue reveals a reusable gap in the skill.
- A skill's instructions are correct but incomplete for an observed real-world
  variant.
- The same correction, clarification, or workaround appears more than once.
- The user rejects, corrects, or materially redirects a skill-produced output.
- A run produces evidence that should change future defaults, checks, or
  escalation rules.

Do not capture feedback for a normal successful skill invocation with no
skill-level lesson. Empty traces reduce signal quality.

## Routing

Attach feedback to the skill that should change.

- If one skill caused the issue, trace that skill.
- If the issue is coordination between two skills, trace the primary orchestrator
  and mention the related skill in the feedback text.
- Do not attach routine feedback to \`skill-feedback\`; that skill is only the
  recorder unless the recorder itself is what failed.

## Capture Method

For ad-hoc feedback, use the installed \`skill-feedback\` skill or call the
shared trace recorder directly:

\`\`\`bash
python3 "\${AGENTS_SKILLS_ROOT}/_shared/trace_capture.py" capture \\
  --skill "<skill-name>" \\
  --gate "ad_hoc" \\
  --gate-type "retrospective" \\
  --outcome "approved" \\
  --feedback "<specific reusable lesson>"
\`\`\`

When a skill command already defines a gate-specific trace capture flow, use that
flow instead.

## Agent Workflow

Before finalizing a skill-backed task, perform a feedback capture check:

1. List the skill or skills used.
2. Decide whether any mandatory trigger fired.
3. Capture one trace per affected skill when a trigger fired.
4. If trace capture fails, report the failure and the reason in the final
   response.
5. If no trigger fired, do not create a trace.

## Relationship To Autoresearch

Skill feedback traces feed the short loop, where skills query recent traces
before gates, and the long loop, where \`skill-improve\` promotes recurring
patterns into durable changes. Skill mutation remains governed by the
autoresearch ratchet and human control surface.
`;
}

function generateQaProfileTemplate() {
  return `${JSON.stringify({
    version: 1,
    specs: [
      { path: "qa/browser/scripts/app-full-regression.md", app: "web", layer: "browser" },
      { path: "qa/api/scripts/app-api-regression.md", app: "web", layer: "api" },
    ],
    apps: [
      {
        id: "web",
        tests: {
          browser: ["apps/web/tests/browser-integration/suites"],
          api: ["apps/web/tests/integration/api-routes"],
        },
      },
    ],
    output: {
      coverage: "qa/qa-coverage.md",
      featureCatalog: "qa/features.generated.yaml",
      featureOverrides: "qa/features.overrides.yaml",
      featureChangelog: "qa/features.changelog.md",
      runResultsDir: "qa/run-results",
      securityFindingsDir: "qa/security/findings",
      walkthroughDir: ".qa-sweep",
    },
    resultSinks: [],
    commands: {
      plan: "",
      execute: "",
      syncSpecs: "",
      syncResults: "",
      integration: "",
    },
    testEnvironment: {
      runtimePreference: "testcontainers",
      composeFile: "",
      services: [],
      mockPolicy: {
        default: "warn",
        allowedExternalBoundaries: [],
        exceptions: [],
      },
    },
  }, null, 2)}
`;
}

function generateCiProfileTemplate() {
  return `${JSON.stringify({
    version: 1,
    project: {
      name: "",
      integrationBranch: "main",
      specRoot: ".jarvis/context/specs",
    },
    release: {
      versionFile: "VERSION",
      changelogFile: "CHANGELOG.md",
      productionTrigger: "semver-tag",
      tagPattern: "v*.*.*",
    },
    qa: {
      profile: ".jarvis/context/profiles/qa.json",
      requiredGates: ["qa drift", "qa coverage", "test-quality-validator"],
    },
    gates: [
      {
        name: "qa drift",
        command: "qa drift --profile .jarvis/context/profiles/qa.json",
        required: true,
      },
      {
        name: "qa coverage",
        command: "qa coverage --profile .jarvis/context/profiles/qa.json --json",
        required: true,
      },
    ],
    policy: {
      allowLocalOverride: true,
      requireSameGatesForLocalOverride: true,
    },
  }, null, 2)}
`;
}

function generateDeployProfileTemplate() {
  return `${JSON.stringify({
    version: 1,
    defaultEnvironment: "canary",
    apps: [
      {
        id: "web",
        type: "auto",
        root: ".",
        buildCommand: "",
        startCommand: "",
        outputDir: "dist",
        package: "auto",
        runtime: {
          mode: "auto",
          healthcheckPath: "/",
          notes: "Use docker-compose, systemd, static, node, node-managed, or process.",
        },
      },
    ],
    environments: {
      canary: {
        provider: "hostinger",
        adapter: "mcp",
        strategy: "canary",
        healthcheckPath: "/",
        url: "",
      },
      production: {
        provider: "hostinger",
        adapter: "mcp",
        strategy: "canary-promote",
        requiresTag: true,
        healthcheckPath: "/",
        url: "",
      },
    },
    providerPolicy: {
      forbidBillingActions: true,
      forbidDestructiveActions: true,
      forbidDnsMutation: true,
    },
    evidence: {
      persist: true,
      root: ".jarvis/context/deployments",
    },
  }, null, 2)}
`;
}

function generateStrategyReadme() {
  return `# Strategy Docs

Use this folder for strategic intent, operating thesis, and business-model documents that explain why the product exists, what leverage it should create, and how the organization expects to win.

## What Belongs Here

- Company or org vision documents
- Product or platform strategy briefs
- Operating-model writeups
- Market, customer, or workflow theses
- Strategic non-goals and sequencing memos

## Agent Guidance

Read this folder when working on:

- issue intake and discovery recovery
- brainstorming and ideation
- PRDs and roadmap shaping
- architecture tradeoffs that depend on business model or operating constraints

When this folder exists, issue-flow artifacts should cite the strategy sources consulted and explain how the proposed work aligns with them.

## Suggested Read Order

1. Start with the most compact thesis or overview doc.
2. Read the main vision or strategy brief.
3. Read workflow-specific or domain-specific strategy docs.
4. Capture the exact docs used in issue_intake.md and brainstorm.md.
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
