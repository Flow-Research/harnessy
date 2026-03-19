#!/usr/bin/env node

const { spawnSync } = require("child_process");
const path = require("path");

const PROTECTED_BRANCHES = new Set(["main", "dev"]);
const SECRET_PATTERNS = [
  /^\.env(?:\..+)?$/,
  /(?:^|\/)\.env(?:\..+)?$/,
  /(?:^|\/)[^/]+\.pem$/,
  /(?:^|\/)[^/]+\.key$/,
  /(?:^|\/)credentials\.json$/,
  /(?:^|\/)secrets\.[^/]+$/,
];

function fail(message, extra = {}) {
  process.stderr.write(`${message}\n`);
  if (Object.keys(extra).length > 0) {
    process.stderr.write(`${JSON.stringify(extra, null, 2)}\n`);
  }
  process.exit(1);
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd || process.cwd(),
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });

  if (result.error) {
    fail(result.error.message);
  }

  if (options.allowFailure) {
    return result;
  }

  if (result.status !== 0) {
    fail(result.stderr.trim() || result.stdout.trim() || `${command} failed`, {
      command: [command, ...args].join(" "),
      status: result.status,
    });
  }

  return result;
}

function git(args, options = {}) {
  return run("git", args, options).stdout.trimEnd();
}

function getRepoRoot() {
  return git(["rev-parse", "--show-toplevel"]).trim();
}

function getCurrentBranch() {
  return git(["rev-parse", "--abbrev-ref", "HEAD"]).trim();
}

function getStatusEntries() {
  const raw = git(["status", "--porcelain=1", "-uall"]);
  if (!raw) return [];

  return raw
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => {
      const indexStatus = line.slice(0, 1);
      const worktreeStatus = line.slice(1, 2);
      const rawPath = line.slice(3).trim();
      const pathParts = rawPath.split(" -> ");
      const filePath = pathParts[pathParts.length - 1];

      return {
        indexStatus,
        worktreeStatus,
        path: filePath,
        raw: line,
      };
    });
}

function parseNumstat(raw) {
  if (!raw) return [];

  return raw
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => {
      const [addedRaw, deletedRaw, ...pathParts] = line.split("\t");
      const filePath = pathParts.join("\t");
      const additions = Number.isNaN(Number(addedRaw)) ? 0 : Number(addedRaw);
      const deletions = Number.isNaN(Number(deletedRaw)) ? 0 : Number(deletedRaw);
      return {
        path: filePath,
        additions,
        deletions,
        churn: additions + deletions,
      };
    });
}

function parseNameStatus(raw) {
  if (!raw) return [];

  return raw
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => {
      const [status, ...pathParts] = line.split("\t");
      const finalPath = pathParts[pathParts.length - 1] || "";
      return { status, path: finalPath };
    });
}

function pathArea(filePath) {
  const parts = filePath.split("/");
  if (parts[0] === "apps" && parts[1]) return parts[1];
  if (parts[0] === "packages" && parts[1]) return parts[1];
  if (parts[0] === "plugins" && parts[2]) return parts[2];
  if (parts[0] === "tools" && parts[1]) return parts[1];
  if (parts[0] === ".jarvis") return "jarvis";
  if (parts[0] === ".github") return "ci";
  return parts[0] || "repo";
}

function isDocsPath(filePath) {
  return /(^|\/)(README|CHANGELOG).*|\.md$/i.test(filePath) || filePath.startsWith("docs/") || filePath.startsWith(".jarvis/");
}

function isTestPath(filePath) {
  return /(^|\/)(__tests__|tests)(\/|$)|\.(test|spec)\.[^/]+$/i.test(filePath);
}

function isDependencyPath(filePath) {
  return /(^|\/)(package\.json|pnpm-lock\.yaml|uv\.lock|pyproject\.toml|requirements[^/]*\.txt)$/i.test(filePath);
}

function isCiPath(filePath) {
  return filePath.startsWith(".github/");
}

function isBuildPath(filePath) {
  return /(^|\/)(turbo\.json|pnpm-workspace\.yaml|tsconfig[^/]*\.json|next\.config\.[^/]+|postcss\.config\.[^/]+|eslint[^/]*|prettier[^/]*|Dockerfile[^/]*|compose[^/]*\.ya?ml)$/i.test(filePath);
}

function countStatuses(entries) {
  const counts = { A: 0, M: 0, D: 0, R: 0 };
  for (const entry of entries) {
    const status = entry.status[0];
    if (counts[status] !== undefined) counts[status] += 1;
  }
  return counts;
}

function collectPatchText() {
  return git(["diff", "--cached", "--no-ext-diff", "--unified=0"], { allowFailure: false });
}

function detectDriver(files) {
  if (files.length === 0) return "empty";
  if (files.every((file) => isDocsPath(file.path))) return "docs";
  if (files.every((file) => isTestPath(file.path))) return "test";
  if (files.some((file) => isDependencyPath(file.path))) return "deps";
  if (files.some((file) => isCiPath(file.path))) return "ci";
  if (files.some((file) => isBuildPath(file.path))) return "build";
  return "code";
}

function detectCommitType(driver, files, patchText) {
  if (driver === "docs") return "docs";
  if (driver === "test") return "test";
  if (driver === "deps" || driver === "ci" || driver === "build") return "chore";

  const addedFiles = files.filter((file) => file.status.startsWith("A")).length;
  const loweredPatch = patchText.toLowerCase();
  const fixSignals = ["fix", "bug", "fallback", "prevent", "guard", "handle", "null", "undefined", "error"];
  const featureSignals = ["+export", "+function", "+const", "+class", "+async function", "+interface ", "+type "];

  if (fixSignals.some((signal) => loweredPatch.includes(signal))) return "fix";
  if (addedFiles > 0 && featureSignals.some((signal) => loweredPatch.includes(signal))) return "feat";
  if (addedFiles > 0 && files.length <= 3) return "feat";
  return "refactor";
}

function summarizeAreas(files) {
  const areaMap = new Map();
  for (const file of files) {
    const area = pathArea(file.path);
    const current = areaMap.get(area) || { area, files: 0, additions: 0, deletions: 0, churn: 0 };
    current.files += 1;
    current.additions += file.additions;
    current.deletions += file.deletions;
    current.churn += file.churn;
    areaMap.set(area, current);
  }

  return Array.from(areaMap.values()).sort((a, b) => {
    if (b.churn !== a.churn) return b.churn - a.churn;
    if (b.files !== a.files) return b.files - a.files;
    return a.area.localeCompare(b.area);
  });
}

function dominantScope(areaSummary) {
  return (areaSummary[0]?.area || "repo").replace(/[^a-zA-Z0-9-]/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "") || "repo";
}

function buildFocus(driver, scope, files) {
  if (driver === "docs") return `${scope} documentation`;
  if (driver === "test") return `${scope} coverage`;
  if (driver === "deps") return `${scope} dependencies`;
  if (driver === "ci") return "CI workflows";
  if (driver === "build") return `${scope} build tooling`;

  const topFile = files[0]?.path ? path.basename(files[0].path).replace(/\.[^.]+$/, "") : scope;
  if (topFile && topFile !== scope) return `${scope} ${topFile}`;
  return `${scope} changes`;
}

function buildSubject(type, scope, driver, files) {
  const focus = buildFocus(driver, scope, files);
  const verbByType = {
    feat: "add",
    fix: "fix",
    docs: "document",
    test: "cover",
    refactor: "refactor",
    chore: "update",
  };

  let subject = `${type}(${scope}): ${verbByType[type]} ${focus}`;
  if (subject.length > 72) {
    subject = `${type}(${scope}): ${verbByType[type]} ${scope}`;
  }
  if (subject.length > 72) {
    subject = `${type}(${scope}): update changes`;
  }
  return subject;
}

function buildDescription(type, driver, areaSummary, files) {
  const areasText = areaSummary.slice(0, 2).map((entry) => entry.area).join(" and ") || "the repository";
  const fileText = files
    .slice(0, 2)
    .map((file) => file.path)
    .join(", ");
  const actionByType = {
    feat: "Adds",
    fix: "Fixes",
    docs: "Documents",
    test: "Covers",
    refactor: "Refactors",
    chore: "Updates",
  };

  const reasonByDriver = {
    docs: "clarify the latest workflow and implementation details",
    test: "capture the latest expected behavior",
    deps: "keep dependencies aligned with the current workspace state",
    ci: "keep automation aligned with repository changes",
    build: "keep tooling aligned with repository changes",
    code: "capture the latest implementation updates",
  };

  return `${actionByType[type]} changes across ${areasText}; notable files: ${fileText || "n/a"}. ${reasonByDriver[driver]}.`;
}

function buildBranchSuggestion(type, scope, subject) {
  const branchType = ["feat", "fix", "docs", "refactor", "test", "chore"].includes(type) ? type : "chore";
  const summarySlug = subject
    .split(":")
    .slice(1)
    .join(":")
    .trim()
    .split(/\s+/)
    .slice(0, 4)
    .join("-")
    .toLowerCase()
    .replace(/[^a-z0-9-]/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "") || "update-changes";
  return `${branchType}/${scope}/${summarySlug}`;
}

function collectCandidateChanges() {
  const statusEntries = getStatusEntries();
  const numstatEntries = parseNumstat(git(["diff", "--cached", "--numstat", "-M"]));
  const nameStatusEntries = parseNameStatus(git(["diff", "--cached", "--name-status", "-M"]));

  if (nameStatusEntries.length > 0) {
    const merged = nameStatusEntries.map((entry) => {
      const stat = numstatEntries.find((numstatEntry) => numstatEntry.path === entry.path) || {
        additions: 0,
        deletions: 0,
        churn: 0,
      };

      return {
        ...entry,
        additions: stat.additions,
        deletions: stat.deletions,
        churn: stat.churn,
      };
    });

    return { statusEntries, files: merged, source: "staged" };
  }

  const files = statusEntries.map((entry) => ({
    status: entry.indexStatus === "?" ? "A" : `${entry.indexStatus}${entry.worktreeStatus}`.trim() || "M",
    path: entry.path,
    additions: 0,
    deletions: 0,
    churn: 0,
  }));

  return { statusEntries, files, source: "working-tree" };
}

function buildMessagePayload(files) {
  const patchText = files.length > 0 ? collectPatchText() : "";
  const driver = detectDriver(files);
  const type = detectCommitType(driver, files, patchText);
  const areaSummary = summarizeAreas(files);
  const scope = dominantScope(areaSummary);
  const subject = buildSubject(type, scope, driver, files);
  const description = buildDescription(type, driver, areaSummary, files);
  const stats = files.reduce(
    (accumulator, file) => {
      accumulator.files += 1;
      accumulator.additions += file.additions;
      accumulator.deletions += file.deletions;
      return accumulator;
    },
    { files: 0, additions: 0, deletions: 0 },
  );
  const statusCounts = countStatuses(files);
  const topFiles = [...files].sort((a, b) => {
    if (b.churn !== a.churn) return b.churn - a.churn;
    return a.path.localeCompare(b.path);
  });

  const bodyLines = [
    `Description: ${description}`,
    `Stats: files=${stats.files} +${stats.additions}/-${stats.deletions} A=${statusCounts.A} M=${statusCounts.M} D=${statusCounts.D} R=${statusCounts.R}`,
    `Driver: ${driver}`,
    "Areas:",
    ...areaSummary.slice(0, 10).map((entry) => `- ${entry.area}: files=${entry.files} +${entry.additions}/-${entry.deletions} churn=${entry.churn}`),
    "Top files:",
    ...topFiles.slice(0, 10).map((file) => `- [${file.status}] ${file.path} (+${file.additions}/-${file.deletions})`),
    "Reason: capture the current local repository changes on the selected branch.",
  ];

  if (areaSummary.length > 10) {
    bodyLines.splice(14, 0, `... (+${areaSummary.length - 10} more areas)`);
  }

  if (topFiles.length > 10) {
    bodyLines.push(`... (+${topFiles.length - 10} more files)`);
  }

  return {
    type,
    driver,
    scope,
    subject,
    body: bodyLines.join("\n"),
    suggestedBranchName: buildBranchSuggestion(type, scope, subject),
    areaSummary,
    topFiles,
    stats,
  };
}

function ensureNoSecrets(paths) {
  const secretPaths = paths.filter((filePath) => SECRET_PATTERNS.some((pattern) => pattern.test(filePath)));
  if (secretPaths.length > 0) {
    fail("Refusing to commit likely secret-bearing files.", { secretPaths });
  }
}

function inspect() {
  const repoRoot = getRepoRoot();
  const currentBranch = getCurrentBranch();
  const { statusEntries, files, source } = collectCandidateChanges();
  const protectedBranch = PROTECTED_BRANCHES.has(currentBranch);
  const counts = {
    staged: statusEntries.filter((entry) => entry.indexStatus !== " " && entry.indexStatus !== "?").length,
    unstaged: statusEntries.filter((entry) => entry.worktreeStatus !== " ").length,
    untracked: statusEntries.filter((entry) => entry.indexStatus === "?").length,
  };
  const message = buildMessagePayload(files);

  process.stdout.write(
    JSON.stringify(
      {
        repoRoot,
        currentBranch,
        detachedHead: currentBranch === "HEAD",
        protectedBranch,
        hasChanges: statusEntries.length > 0,
        counts,
        changeSource: source,
        candidatePaths: statusEntries.map((entry) => entry.path),
        suggestedBranchName: message.suggestedBranchName,
        suggestedCommit: {
          type: message.type,
          driver: message.driver,
          scope: message.scope,
          subject: message.subject,
          body: message.body,
        },
      },
      null,
      2,
    ),
  );
}

function parseArgs(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--branch-mode") options.branchMode = argv[index + 1];
    if (token === "--branch-name") options.branchName = argv[index + 1];
    if (token === "--allow-protected-current") options.allowProtectedCurrent = true;
    if (token.startsWith("--") && token !== "--allow-protected-current") index += 1;
  }
  return options;
}

function commit(argv) {
  const repoRoot = getRepoRoot();
  const currentBranch = getCurrentBranch();
  if (currentBranch === "HEAD") {
    fail("Cannot commit from detached HEAD. Check out a branch first.");
  }

  const options = parseArgs(argv);
  if (!["current", "new"].includes(options.branchMode)) {
    fail("Missing or invalid --branch-mode. Use current or new.");
  }

  if (options.branchMode === "new" && !options.branchName) {
    fail("Missing --branch-name for new branch mode.");
  }

  if (options.branchMode === "current" && PROTECTED_BRANCHES.has(currentBranch) && !options.allowProtectedCurrent) {
    fail("Current branch is protected. Choose a new branch or explicitly allow the protected branch.", {
      currentBranch,
    });
  }

  const beforePaths = getStatusEntries().map((entry) => entry.path);
  if (beforePaths.length === 0) {
    fail("No local changes to commit.");
  }

  ensureNoSecrets(beforePaths);

  let selectedBranch = currentBranch;
  let createdBranch = false;
  let switchedBranch = false;

  if (options.branchMode === "new") {
    const branchName = options.branchName;
    const validation = run("git", ["check-ref-format", "--branch", branchName], {
      cwd: repoRoot,
      allowFailure: true,
    });

    if (validation.status !== 0) {
      fail("Invalid branch name.", { branchName });
    }

    const branchExists = run("git", ["show-ref", "--verify", "--quiet", `refs/heads/${branchName}`], {
      cwd: repoRoot,
      allowFailure: true,
    }).status === 0;

    if (branchExists) {
      git(["switch", branchName]);
    } else {
      git(["switch", "-c", branchName]);
      createdBranch = true;
    }
    switchedBranch = branchName !== currentBranch;
    selectedBranch = branchName;
  }

  git(["add", "-A"]);

  const stagedNameStatus = parseNameStatus(git(["diff", "--cached", "--name-status", "-M"]));
  if (stagedNameStatus.length === 0) {
    fail("Nothing staged after git add -A.");
  }

  ensureNoSecrets(stagedNameStatus.map((entry) => entry.path));

  const stagedNumstat = parseNumstat(git(["diff", "--cached", "--numstat", "-M"]));
  const stagedFiles = stagedNameStatus.map((entry) => {
    const numstat = stagedNumstat.find((item) => item.path === entry.path) || {
      additions: 0,
      deletions: 0,
      churn: 0,
    };

    return {
      ...entry,
      additions: numstat.additions,
      deletions: numstat.deletions,
      churn: numstat.churn,
    };
  });

  const message = buildMessagePayload(stagedFiles);
  const commitResult = run(
    "git",
    ["commit", "-m", message.subject, "-m", message.body],
    { cwd: repoRoot, allowFailure: true },
  );

  if (commitResult.status !== 0) {
    fail(commitResult.stderr.trim() || commitResult.stdout.trim() || "git commit failed", {
      command: `git commit -m ${JSON.stringify(message.subject)} -m <body>`,
      branch: selectedBranch,
    });
  }

  const commitHash = git(["rev-parse", "HEAD"]).trim();
  const finalStatus = git(["status", "--short"]);

  process.stdout.write(
    JSON.stringify(
      {
        repoRoot,
        previousBranch: currentBranch,
        selectedBranch,
        createdBranch,
        switchedBranch,
        commitHash,
        subject: message.subject,
        body: message.body,
        finalWorkingTree: finalStatus ? "dirty" : "clean",
      },
      null,
      2,
    ),
  );
}

const [subcommand, ...rest] = process.argv.slice(2);

if (subcommand === "inspect") {
  inspect();
} else if (subcommand === "commit") {
  commit(rest);
} else {
  fail("Usage: git-commit.js <inspect|commit> [options]");
}
