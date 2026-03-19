import fs from "node:fs/promises";
import path from "node:path";
import { getSkillsRootConfig } from "./skills-root.mjs";

const projectRoot = process.cwd();

const postInstallChecks = async () => {
  const skillsRootConfig = await getSkillsRootConfig(projectRoot);
  await fs.mkdir(skillsRootConfig.skillsRoot, { recursive: true });

  console.log(
    `OK: Ensured ${skillsRootConfig.skillsRoot} exists for global skill discovery`
  );

  const localMd = path.join(projectRoot, ".jarvis", "context", "local.md");
  try {
    await fs.access(localMd);
  } catch {
    console.log(
      "TIP: Run `pnpm setup` to configure your personal context files."
    );
  }
};

postInstallChecks().catch((error) => {
  console.error("Failed postinstall checks:", error);
  process.exitCode = 1;
});
