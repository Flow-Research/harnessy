#!/usr/bin/env node
import os from "node:os";
import path from "node:path";

import { bootstrapInstall } from "../lib/registry/bootstrap.mjs";
import { installSkills } from "../lib/skills.mjs";

const HELP = `Usage: bootstrap [options]

Install Harnessy skills directly from a published cloud registry. No source
repo clone required. Fetches the public lockfile from the Worker, then pulls
each skill from Cloudflare Artifacts into ~/.agents/skills/.

Options:
  --worker-url <url>   Required. Base URL of the public skill registry Worker.
                       Falls back to env HARNESSY_WORKER_URL.
  --lockfile <path>    Where to cache the fetched lockfile.
                       Defaults to ~/.cache/harnessy/skill-registry.lock.json.
  --cache-dir <path>   Where to cache cloned skill repos.
                       Defaults to ~/.cache/harnessy/skills.
  --dry-run            Fetch lockfile and resolve skills, but don't install.
  --help               Show this message.
`;

const parseArgs = (argv) => {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--help" || a === "-h") { out.help = true; continue; }
    if (a === "--dry-run") { out.dryRun = true; continue; }
    if (a.startsWith("--")) { out[a.slice(2)] = argv[++i]; }
  }
  return out;
};

const main = async () => {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) { process.stdout.write(HELP); return; }

  const workerUrl = args["worker-url"] || process.env.HARNESSY_WORKER_URL;
  if (!workerUrl) {
    process.stderr.write(`Missing --worker-url (or HARNESSY_WORKER_URL).\n\n${HELP}`);
    process.exit(2);
  }

  const cacheRoot = path.join(os.homedir(), ".cache", "harnessy");
  const lockfilePath = args.lockfile
    ? path.resolve(args.lockfile)
    : path.join(cacheRoot, "skill-registry.lock.json");
  const cacheDir = args["cache-dir"]
    ? path.resolve(args["cache-dir"])
    : path.join(cacheRoot, "skills");

  process.stdout.write(`Bootstrapping from ${workerUrl}\n`);

  const installer = {
    install: async (registry) => {
      if (args.dryRun) {
        const list = await registry.list();
        process.stdout.write(`[dry-run] would install ${list.length} skills:\n`);
        for (const s of list) process.stdout.write(`  - ${s.name}@${s.version}\n`);
        return;
      }
      await installSkills(null, { registry });
    },
  };

  const { skillCount } = await bootstrapInstall({
    workerUrl,
    lockfilePath,
    cacheDir,
    fetchImpl: globalThis.fetch.bind(globalThis),
    installer,
  });

  process.stdout.write(`\nDone — ${skillCount} skill(s) ${args.dryRun ? "resolved" : "installed"}.\n`);
  process.stdout.write(`  lockfile: ${lockfilePath}\n`);
  process.stdout.write(`  cache:    ${cacheDir}\n`);
};

main().catch((error) => {
  process.stderr.write(`bootstrap: ${error?.message || error}\n`);
  process.exit(1);
});
