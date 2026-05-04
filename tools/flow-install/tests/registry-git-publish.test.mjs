import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

import { publishSkillGit } from "../lib/registry/git-publish.mjs";

const execFileAsync = promisify(execFile);

const GIT_ENV = {
  GIT_AUTHOR_NAME: "Test", GIT_AUTHOR_EMAIL: "t@test",
  GIT_COMMITTER_NAME: "Test", GIT_COMMITTER_EMAIL: "t@test",
  GIT_TERMINAL_PROMPT: "0",
};

const tmp = (label) => fs.mkdtemp(path.join(os.tmpdir(), `harnessy-git-${label}-`));

const setupSkillAndRemote = async () => {
  const skillDir = await tmp("skill");
  const remoteDir = await tmp("remote");
  await fs.writeFile(path.join(skillDir, "SKILL.md"), "# my-skill v1\n");
  await fs.writeFile(path.join(skillDir, "manifest.yaml"), "name: my-skill\nversion: 1.0.0\n");
  await execFileAsync("git", ["init", "--bare", remoteDir]);
  return { skillDir, remoteDir };
};

const remoteHas = async (remoteDir, ref) => {
  const { stdout } = await execFileAsync("git", ["-C", remoteDir, "show-ref", ref]);
  return stdout.trim().length > 0;
};

const remoteTags = async (remoteDir) => {
  const { stdout } = await execFileAsync("git", ["-C", remoteDir, "tag", "--list"]);
  return stdout.split("\n").map((s) => s.trim()).filter(Boolean);
};

test("publishSkillGit initializes, commits, tags and pushes to remote on fresh dir", async () => {
  const { skillDir, remoteDir } = await setupSkillAndRemote();
  const result = await publishSkillGit({
    skillDir,
    name: "my-skill",
    version: "1.0.0",
    pushUrl: remoteDir,
    gitEnv: GIT_ENV,
  });

  assert.match(result.sha, /^[0-9a-f]{40}$/, "sha should be a full git OID");

  const tags = await remoteTags(remoteDir);
  assert.deepEqual(tags, ["v1.0.0"]);

  assert.ok(await remoteHas(remoteDir, "refs/heads/main"), "main branch should exist on remote");
  assert.ok(await remoteHas(remoteDir, "refs/tags/v1.0.0"), "tag should be pushed");
});

test("publishSkillGit reuses existing git repo and adds a new tagged commit", async () => {
  const { skillDir, remoteDir } = await setupSkillAndRemote();
  await publishSkillGit({
    skillDir, name: "my-skill", version: "1.0.0", pushUrl: remoteDir, gitEnv: GIT_ENV,
  });

  await fs.writeFile(path.join(skillDir, "SKILL.md"), "# my-skill v2\n");
  const second = await publishSkillGit({
    skillDir, name: "my-skill", version: "1.0.1", pushUrl: remoteDir, gitEnv: GIT_ENV,
  });

  assert.match(second.sha, /^[0-9a-f]{40}$/);
  const tags = await remoteTags(remoteDir);
  assert.deepEqual(tags.sort(), ["v1.0.0", "v1.0.1"]);
});

test("publishSkillGit fails when tag already exists locally", async () => {
  const { skillDir, remoteDir } = await setupSkillAndRemote();
  await publishSkillGit({
    skillDir, name: "my-skill", version: "1.0.0", pushUrl: remoteDir, gitEnv: GIT_ENV,
  });
  await assert.rejects(
    () => publishSkillGit({
      skillDir, name: "my-skill", version: "1.0.0", pushUrl: remoteDir, gitEnv: GIT_ENV,
    }),
    /v1\.0\.0/,
  );
});

test("publishSkillGit surfaces git push errors when remote is invalid", async () => {
  const skillDir = await tmp("skill");
  await fs.writeFile(path.join(skillDir, "SKILL.md"), "# x\n");
  await assert.rejects(
    () => publishSkillGit({
      skillDir,
      name: "my-skill",
      version: "1.0.0",
      pushUrl: path.join(os.tmpdir(), "definitely-not-a-repo-" + Date.now()),
      gitEnv: GIT_ENV,
    }),
    /push|remote|repository/i,
  );
});

test("publishSkillGit returns the same sha that HEAD points to", async () => {
  const { skillDir, remoteDir } = await setupSkillAndRemote();
  const { sha } = await publishSkillGit({
    skillDir, name: "my-skill", version: "1.0.0", pushUrl: remoteDir, gitEnv: GIT_ENV,
  });
  const { stdout } = await execFileAsync("git", ["-C", skillDir, "rev-parse", "HEAD"]);
  assert.equal(stdout.trim(), sha);
});

test("publishSkillGit allows publishing with no file changes via empty commit", async () => {
  const { skillDir, remoteDir } = await setupSkillAndRemote();
  await publishSkillGit({
    skillDir, name: "my-skill", version: "1.0.0", pushUrl: remoteDir, gitEnv: GIT_ENV,
  });
  // No file edits between publishes — bumping only the version should still work.
  const second = await publishSkillGit({
    skillDir, name: "my-skill", version: "1.0.1", pushUrl: remoteDir, gitEnv: GIT_ENV,
  });
  assert.match(second.sha, /^[0-9a-f]{40}$/);
});
