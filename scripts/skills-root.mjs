import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

const defaultConfig = {
  placeholder: "${AGENTS_SKILLS_ROOT}",
  envVar: "AGENTS_SKILLS_ROOT",
  defaultRelativeToHome: ".agents/skills",
};

const readConfig = async (projectRoot) => {
  const configPath = path.join(projectRoot, "scripts", "skills-root.config.json");
  const raw = await fs.readFile(configPath, "utf8").catch(() => null);
  if (!raw) return defaultConfig;

  try {
    const parsed = JSON.parse(raw);
    return {
      placeholder: parsed.placeholder || defaultConfig.placeholder,
      envVar: parsed.envVar || defaultConfig.envVar,
      defaultRelativeToHome:
        parsed.defaultRelativeToHome || defaultConfig.defaultRelativeToHome,
    };
  } catch {
    return defaultConfig;
  }
};

export const getSkillsRootConfig = async (projectRoot) => {
  const config = await readConfig(projectRoot);
  const envValue = process.env[config.envVar];
  const skillsRoot = envValue && envValue.trim().length > 0
    ? envValue
    : path.join(os.homedir(), config.defaultRelativeToHome);

  return {
    placeholder: config.placeholder,
    envVar: config.envVar,
    skillsRoot,
  };
};
