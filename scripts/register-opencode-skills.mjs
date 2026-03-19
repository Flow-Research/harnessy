import fs from "node:fs/promises";
import path from "node:path";
import { getSkillsRootConfig } from "./skills-root.mjs";

const projectRoot = process.cwd();
const sharedSkillsRoot = path.join(projectRoot, "tools", "flow-install", "skills");
const projectSkillsRoot = path.join(projectRoot, ".agents", "skills");

let skillsRootConfig;

const pathExists = async (target) => {
  try {
    await fs.access(target);
    return true;
  } catch {
    return false;
  }
};

const collectSkills = async () => {
  const skills = [];
  const roots = [
    { type: "opencode", rootDir: sharedSkillsRoot },
    { type: "project", rootDir: projectSkillsRoot },
  ];

  for (const { type, rootDir } of roots) {
    const entries = await fs.readdir(rootDir, { withFileTypes: true }).catch(() => []);
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      const skillDir = path.join(rootDir, entry.name);
      const skillDoc = path.join(skillDir, "SKILL.md");
      if (await pathExists(skillDoc)) {
        skills.push({ name: entry.name, type, skillDir });
      }
    }
  }

  return skills;
};

const validateSkillCommandReferences = async (skill) => {
  const skillDocPath = path.join(skill.skillDir, "SKILL.md");
  const skillContent = await fs.readFile(skillDocPath, "utf8").catch(() => "");
  if (!skillContent) return [];

  const errors = [];
  const expectedTemplateRootLine = `- Template paths are resolved from \`${skillsRootConfig.placeholder}/${skill.name}/\`.`;
  const templateRootLinePrefix = `- Template paths are resolved from \`${skillsRootConfig.placeholder}/`;

  if (!skillContent.includes(expectedTemplateRootLine)) {
    const templateRootLine = skillContent
      .split(/\r?\n/)
      .find((line) => line.startsWith(templateRootLinePrefix));
    if (!templateRootLine) {
      errors.push(`${skill.name}: add template root declaration: ${expectedTemplateRootLine}`);
    } else {
      const actualSkillSegment = templateRootLine
        .slice(templateRootLinePrefix.length)
        .replace(/\/`\.$/, "");
      errors.push(
        `${skill.name}: expected template root ${skillsRootConfig.placeholder}/${skill.name}/, found ${skillsRootConfig.placeholder}/${actualSkillSegment}/`
      );
    }
  }

  const hasFragileCommandPath =
    /Follow the command specification in `\.\/commands\//.test(skillContent) ||
    /Follow the command specifications under `\.\/commands\//.test(skillContent);

  if (hasFragileCommandPath) {
    errors.push(
      `${skill.name}: replace ./commands paths with ${skillsRootConfig.placeholder}/${skill.name}/commands/<file>.md`
    );
  }

  const escapedPlaceholder = skillsRootConfig.placeholder.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const installedPathRegex = new RegExp(`${escapedPlaceholder}\\/([^/\\s]+)\\/commands\\/`, "g");
  let match = installedPathRegex.exec(skillContent);
  while (match) {
    const referencedSkill = match[1];
    const isTemplatePlaceholder = referencedSkill.includes("<") || referencedSkill.includes("{");
    if (!isTemplatePlaceholder && referencedSkill !== skill.name) {
      errors.push(
        `${skill.name}: expected ${skillsRootConfig.placeholder}/${skill.name}/..., found ${skillsRootConfig.placeholder}/${referencedSkill}/...`
      );
    }
    match = installedPathRegex.exec(skillContent);
  }

  return errors;
};

const copyDir = async (src, dest) => {
  await fs.mkdir(dest, { recursive: true });
  const entries = await fs.readdir(src, { withFileTypes: true });

  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);

    if (entry.isDirectory()) {
      await copyDir(srcPath, destPath);
    } else {
      await fs.copyFile(srcPath, destPath);
    }
  }
};

const syncSkillDirsToRoot = async (skills, rootDir) => {
  await fs.mkdir(rootDir, { recursive: true });
  const synced = [];

  for (const skill of skills) {
    const targetDir = path.join(rootDir, skill.name);

    if (await pathExists(targetDir)) {
      await fs.rm(targetDir, { recursive: true });
    }

    await copyDir(skill.skillDir, targetDir);
    synced.push({ name: skill.name, targetDir });
  }

  return synced;
};

const registerSkills = async () => {
  skillsRootConfig = await getSkillsRootConfig(projectRoot);
  const skills = await collectSkills();
  if (skills.length === 0) {
    console.warn("No skill directories found under tools/flow-install/skills or .agents/skills. Nothing to register.");
    return;
  }

  const commandPathErrors = [];
  for (const skill of skills) {
    const errors = await validateSkillCommandReferences(skill);
    commandPathErrors.push(...errors);
  }

  if (commandPathErrors.length > 0) {
    throw new Error(
      "Command doc path validation failed:\n" +
        commandPathErrors.map((entry) => `- ${entry}`).join("\n")
    );
  }

  const syncedGlobal = await syncSkillDirsToRoot(skills, skillsRootConfig.skillsRoot);

  console.log(`Installed full skill directories to ${skillsRootConfig.skillsRoot}:`);
  for (const entry of syncedGlobal) console.log(`- ${entry.name}: ${entry.targetDir}`);
};

registerSkills()
  .then(async () => {
    const { registerClaudeSkills } = await import("./register-claude-skills.mjs");
    await registerClaudeSkills();
  })
  .catch((error) => {
    console.error("Failed to register skills:", error);
    process.exitCode = 1;
  });
