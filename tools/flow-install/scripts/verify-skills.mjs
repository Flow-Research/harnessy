#!/usr/bin/env node
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { verifySkills } from "../lib/registry/verify.mjs";

const HELP = `Usage: verify-skills [options]

Verify installed skills against the recorded content manifest in
skill-registry.lock.json. Exits non-zero if any skill fails verification.

Options:
  --lockfile <path>        Defaults to tools/flow-install/skill-registry.lock.json.
  --installed-root <path>  Defaults to ~/.agents/skills.
  --json                   Emit machine-readable JSON instead of a table.
  --help                   Show this message.
`;

const parseArgs = (argv) => {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--help" || a === "-h") { out.help = true; continue; }
    if (a === "--json") { out.json = true; continue; }
    if (a.startsWith("--")) { out[a.slice(2)] = argv[++i]; }
  }
  return out;
};

const summarize = (results) => {
  const ok = results.filter((r) => r.ok).length;
  const failed = results.length - ok;
  return { ok, failed, total: results.length };
};

const printTable = (results) => {
  if (results.length === 0) {
    process.stdout.write("No artifacts-backed skills in lockfile.\n");
    return;
  }
  for (const r of results) {
    if (r.ok) {
      process.stdout.write(`OK    ${r.name}@${r.version}\n`);
    } else if (r.reason) {
      process.stdout.write(`FAIL  ${r.name}@${r.version}  (${r.reason})\n`);
    } else {
      const m = r.mismatches;
      const parts = [];
      if (m.changed.length) parts.push(`changed=${m.changed.join(",")}`);
      if (m.added.length) parts.push(`added=${m.added.join(",")}`);
      if (m.removed.length) parts.push(`removed=${m.removed.join(",")}`);
      process.stdout.write(`FAIL  ${r.name}@${r.version}  ${parts.join(" ")}\n`);
    }
  }
  const s = summarize(results);
  process.stdout.write(`\n${s.ok}/${s.total} skills verified, ${s.failed} failed.\n`);
};

const main = async () => {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) { process.stdout.write(HELP); return; }

  const flowInstallRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  const lockfilePath = args.lockfile
    ? path.resolve(args.lockfile)
    : path.join(flowInstallRoot, "skill-registry.lock.json");
  const installedRoot = args["installed-root"]
    ? path.resolve(args["installed-root"])
    : path.join(os.homedir(), ".agents", "skills");

  const results = await verifySkills({ lockfilePath, installedRoot });

  if (args.json) {
    process.stdout.write(JSON.stringify({ results, summary: summarize(results) }, null, 2) + "\n");
  } else {
    printTable(results);
  }

  if (results.some((r) => !r.ok)) process.exit(1);
};

main().catch((error) => {
  process.stderr.write(`verify-skills: ${error?.message || error}\n`);
  process.exit(2);
});
