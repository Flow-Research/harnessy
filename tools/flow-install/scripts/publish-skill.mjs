#!/usr/bin/env node
import path from "node:path";
import { fileURLToPath } from "node:url";

import { WorkerClient } from "../lib/registry/worker-client.mjs";
import { publishSkillGit } from "../lib/registry/git-publish.mjs";
import { publishSkill } from "../lib/registry/publish-skill.mjs";

const HELP = `Usage: publish-skill <name> --version <semver> [options]

Publishes a skill to the Cloudflare Artifacts–backed registry: provisions the
remote via the management Worker, pushes the skill repo, and records the
{version, sha, remote} in skill-registry.lock.json.

Options:
  --version <semver>      Required. The version to tag and publish.
  --worker-url <url>      Required. Base URL of the management Worker.
                          Falls back to env HARNESSY_WORKER_URL.
  --token <token>         Required. Bearer token for the Worker.
                          Falls back to env HARNESSY_PUBLISH_TOKEN.
  --skills-root <path>    Defaults to tools/flow-install/skills.
  --lockfile <path>       Defaults to tools/flow-install/skill-registry.lock.json.
  --help                  Show this message.
`;

const parseArgs = (argv) => {
  const out = { positional: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--help" || a === "-h") { out.help = true; continue; }
    if (a.startsWith("--")) {
      const key = a.slice(2);
      out[key] = argv[++i];
      continue;
    }
    out.positional.push(a);
  }
  return out;
};

const main = async () => {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || args.positional.length === 0) {
    process.stdout.write(HELP);
    process.exit(args.help ? 0 : 1);
  }

  const [name] = args.positional;
  const version = args.version;
  const workerUrl = args["worker-url"] || process.env.HARNESSY_WORKER_URL;
  const token = args.token || process.env.HARNESSY_PUBLISH_TOKEN;

  const missing = [];
  if (!version) missing.push("--version");
  if (!workerUrl) missing.push("--worker-url (or HARNESSY_WORKER_URL)");
  if (!token) missing.push("--token (or HARNESSY_PUBLISH_TOKEN)");
  if (missing.length) {
    process.stderr.write(`Missing required argument(s): ${missing.join(", ")}\n\n${HELP}`);
    process.exit(2);
  }

  const flowInstallRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  const skillsRoot = args["skills-root"]
    ? path.resolve(args["skills-root"])
    : path.join(flowInstallRoot, "skills");
  const lockfilePath = args.lockfile
    ? path.resolve(args.lockfile)
    : path.join(flowInstallRoot, "skill-registry.lock.json");

  const workerClient = new WorkerClient({ baseUrl: workerUrl, token });
  const git = { publish: publishSkillGit };

  const result = await publishSkill({
    name, version, skillsRoot, lockfilePath, workerClient, git,
  });

  process.stdout.write(`Published ${name}@${version}\n`);
  process.stdout.write(`  sha:    ${result.sha}\n`);
  process.stdout.write(`  remote: ${result.remote}\n`);
  process.stdout.write(`  lock:   ${lockfilePath}\n`);
};

main().catch((error) => {
  process.stderr.write(`publish-skill: ${error?.message || error}\n`);
  process.exit(1);
});
