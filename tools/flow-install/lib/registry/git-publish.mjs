import fs from "node:fs/promises";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

const runGit = async (cwd, args, env = {}) => {
  try {
    const result = await execFileAsync("git", ["-C", cwd, ...args], {
      env: { ...process.env, ...env },
    });
    return result;
  } catch (error) {
    const stderr = error?.stderr?.toString?.().trim() || "";
    const stdout = error?.stdout?.toString?.().trim() || "";
    const detail = stderr || stdout || error.message;
    const wrapped = new Error(`git ${args[0]} failed: ${detail}`);
    wrapped.cause = error;
    wrapped.stderr = stderr;
    throw wrapped;
  }
};

const ensureRepo = async (skillDir, env) => {
  const gitDir = path.join(skillDir, ".git");
  try {
    await fs.access(gitDir);
    return;
  } catch {}
  await runGit(skillDir, ["init", "--initial-branch=main"], env);
};

const tagExists = async (skillDir, tag, env) => {
  try {
    await runGit(skillDir, ["rev-parse", "--verify", `refs/tags/${tag}`], env);
    return true;
  } catch {
    return false;
  }
};

const headSha = async (skillDir, env) => {
  const { stdout } = await runGit(skillDir, ["rev-parse", "HEAD"], env);
  return stdout.trim();
};

export const publishSkillGit = async ({
  skillDir,
  name,
  version,
  pushUrl,
  gitEnv = {},
  message,
}) => {
  if (!skillDir) throw new Error("publishSkillGit requires skillDir");
  if (!name) throw new Error("publishSkillGit requires name");
  if (!version) throw new Error("publishSkillGit requires version");
  if (!pushUrl) throw new Error("publishSkillGit requires pushUrl");

  const tag = `v${version}`;
  const env = { ...gitEnv };

  await ensureRepo(skillDir, env);

  if (await tagExists(skillDir, tag, env)) {
    throw new Error(`Tag ${tag} already exists in ${skillDir}; bump version before re-publishing`);
  }

  await runGit(skillDir, ["add", "-A"], env);
  await runGit(
    skillDir,
    ["commit", "--allow-empty", "-m", message || `publish: ${name}@${version}`],
    env,
  );
  await runGit(skillDir, ["tag", tag], env);

  await runGit(skillDir, ["push", pushUrl, "HEAD:refs/heads/main"], env);
  await runGit(skillDir, ["push", pushUrl, `refs/tags/${tag}`], env);

  return { sha: await headSha(skillDir, env), tag };
};
