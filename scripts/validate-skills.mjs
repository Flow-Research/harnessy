import fs from "node:fs/promises";
import path from "node:path";
import { getSkillsRootConfig } from "./skills-root.mjs";

const projectRoot = process.cwd();
const sharedSkillsRoot = path.join(projectRoot, "tools", "flow-install", "skills");
const projectSkillsRoot = path.join(projectRoot, ".agents", "skills");
const catalogPath = path.join(
  projectRoot,
  ".jarvis/context/skills/_catalog.md"
);

let skillsRootConfig;

const requiredManifestFields = [
  "name",
  "type",
  "version",
  "owner",
  "status",
  "blast_radius",
  "description",
  "permissions",
  "data_categories",
  "egress",
  "invoke",
  "location",
];

const allowedTypes = new Set(["opencode", "OpenClaw", "n8n", "project"]);
const allowedStatuses = new Set(["active", "experimental"]);
const allowedBlastRadius = new Set(["low", "medium", "high"]);

const readFileSafe = async (filePath) => {
  try {
    return await fs.readFile(filePath, "utf8");
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }
};

const parseYamlFrontmatter = (content) => {
  const match = content.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return null;
  const lines = match[1].split(/\r?\n/);
  const data = {};

  for (const line of lines) {
    if (!line.trim() || line.trim().startsWith("#")) continue;
    const [key, ...rest] = line.split(":");
    if (!key || rest.length === 0) continue;
    const rawValue = rest.join(":").trim();
    data[key.trim()] = rawValue;
  }

  return data;
};

const parseManifest = (content) => {
  const lines = content.split(/\r?\n/);
  const data = {};

  for (const line of lines) {
    if (!line.trim() || line.trim().startsWith("#")) continue;
    const [key, ...rest] = line.split(":");
    if (!key || rest.length === 0) continue;
    const rawValue = rest.join(":").trim();
    data[key.trim()] = rawValue;
  }

  return data;
};

const normalizeList = (value) =>
  value
    .replace(/^\[/, "")
    .replace(/\]$/, "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

const validateSkillCommandReferences = (skillName, skillPath, skillContent) => {
  const errors = [];
  const expectedTemplateRootLine = `- Template paths are resolved from \`${skillsRootConfig.placeholder}/${skillName}/\`.`;
  const templateRootLinePrefix = `- Template paths are resolved from \`${skillsRootConfig.placeholder}/`;

  if (!skillContent.includes(expectedTemplateRootLine)) {
    const templateRootLine = skillContent
      .split(/\r?\n/)
      .find((line) => line.startsWith(templateRootLinePrefix));
    if (!templateRootLine) {
      errors.push(
        `Missing template root declaration in ${skillPath}. Add: ${expectedTemplateRootLine}`
      );
    } else {
      const actualSkillSegment = templateRootLine
        .slice(templateRootLinePrefix.length)
        .replace(/\/`\.$/, "");
      errors.push(
        `Mismatched template root declaration in ${skillPath}: expected ${skillsRootConfig.placeholder}/${skillName}/, found ${skillsRootConfig.placeholder}/${actualSkillSegment}/`
      );
    }
  }

  const hasFragileCommandPath =
    /Follow the command specification in `\.\/commands\//.test(skillContent) ||
    /Follow the command specifications under `\.\/commands\//.test(skillContent);

  if (hasFragileCommandPath) {
    errors.push(
      `Fragile command doc path in ${skillPath}. Use ${skillsRootConfig.placeholder}/${skillName}/commands/<file>.md`
    );
  }

  const escapedPlaceholder = skillsRootConfig.placeholder.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const installedPathRegex = new RegExp(`${escapedPlaceholder}\\/([^/\\s]+)\\/commands\\/`, "g");
  let match = installedPathRegex.exec(skillContent);
  while (match) {
    const referencedSkill = match[1];
    const isTemplatePlaceholder = referencedSkill.includes("<") || referencedSkill.includes("{");
    if (!isTemplatePlaceholder && referencedSkill !== skillName) {
      errors.push(
        `Mismatched installed command path in ${skillPath}: expected ${skillsRootConfig.placeholder}/${skillName}/..., found ${skillsRootConfig.placeholder}/${referencedSkill}/...`
      );
    }
    match = installedPathRegex.exec(skillContent);
  }

  return errors;
};

const collectPluginDirs = async () => {
  const results = [];

  const roots = [
    { type: "opencode", rootDir: sharedSkillsRoot },
    { type: "project", rootDir: projectSkillsRoot },
  ];

  for (const { type, rootDir } of roots) {
    const entries = await fs.readdir(rootDir, { withFileTypes: true }).catch(() => []);
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      results.push({ type, name: entry.name, dir: path.join(rootDir, entry.name) });
    }
  }

  return results;
};

const parseCatalogEntries = async () => {
  const catalogContent = await readFileSafe(catalogPath);
  if (!catalogContent) return [];

  const blocks = catalogContent.split(/\n---\n/).filter((block) => block.trim());
  return blocks
    .map((block) => {
      const data = parseYamlFrontmatter(`---\n${block}\n---`);
      if (!data) return null;
      const name = data.name?.replace(/"/g, "");
      const invoke = data.invoke?.replace(/"/g, "");
      return { name, invoke, raw: data };
    })
    .filter(Boolean);
};

const validate = async () => {
  skillsRootConfig = await getSkillsRootConfig(projectRoot);
  const errors = [];
  const catalogEntries = await parseCatalogEntries();
  const catalogNames = new Map();
  const catalogInvokes = new Map();

  for (const entry of catalogEntries) {
    if (entry.name) {
      if (catalogNames.has(entry.name)) {
        errors.push(`Duplicate catalog name: ${entry.name}`);
      }
      catalogNames.set(entry.name, entry);
    }
    if (entry.invoke) {
      if (catalogInvokes.has(entry.invoke)) {
        errors.push(`Duplicate catalog invoke: ${entry.invoke}`);
      }
      catalogInvokes.set(entry.invoke, entry);
    }
  }

  const pluginDirs = await collectPluginDirs();
  for (const plugin of pluginDirs) {
    const manifestPath = path.join(plugin.dir, "manifest.yaml");
    const manifestContent = await readFileSafe(manifestPath);
    if (!manifestContent) {
      errors.push(`Missing manifest.yaml in ${plugin.dir}`);
      continue;
    }

    const manifest = parseManifest(manifestContent);
    for (const field of requiredManifestFields) {
      if (!manifest[field]) {
        errors.push(`Missing field '${field}' in ${manifestPath}`);
      }
    }

    const manifestName = manifest.name?.replace(/"/g, "");
    if (manifestName && manifestName !== plugin.name) {
      errors.push(
        `Manifest name '${manifestName}' does not match folder '${plugin.name}' in ${plugin.dir}`
      );
    }

    if (manifest.type && !allowedTypes.has(manifest.type)) {
      errors.push(`Invalid type '${manifest.type}' in ${manifestPath}`);
    }

    if (manifest.status && !allowedStatuses.has(manifest.status)) {
      errors.push(`Invalid status '${manifest.status}' in ${manifestPath}`);
    }

    if (manifest.blast_radius && !allowedBlastRadius.has(manifest.blast_radius)) {
      errors.push(`Invalid blast_radius '${manifest.blast_radius}' in ${manifestPath}`);
    }

    if (manifest.permissions) {
      const perms = normalizeList(manifest.permissions);
      if (perms.length === 0) {
        errors.push(`Empty permissions list in ${manifestPath}`);
      }
    }

    if (manifest.data_categories) {
      const categories = normalizeList(manifest.data_categories);
      if (categories.length === 0) {
        errors.push(`Empty data_categories list in ${manifestPath}`);
      }
    }

    if (manifest.egress) {
      const egress = normalizeList(manifest.egress);
      if (egress.length === 0 && manifest.egress !== "[]") {
        errors.push(`Empty egress list in ${manifestPath}`);
      }
    }

    if (manifestName && !catalogNames.has(manifestName)) {
      errors.push(`Missing catalog entry for skill '${manifestName}'`);
    }

    if (manifest.invoke) {
      const invokeValue = manifest.invoke.replace(/"/g, "");
      if (!catalogInvokes.has(invokeValue)) {
        errors.push(`Missing catalog entry for invoke '${invokeValue}'`);
      }
    }

    const skillPath = path.join(plugin.dir, "SKILL.md");
    const skillContent = await readFileSafe(skillPath);
    if (skillContent) {
      const pathErrors = validateSkillCommandReferences(plugin.name, skillPath, skillContent);
      errors.push(...pathErrors);
    }
  }

  if (errors.length > 0) {
    console.error("Skill validation failed:\n" + errors.map((e) => `- ${e}`).join("\n"));
    process.exitCode = 1;
    return;
  }

  console.log("Skill validation passed.");
};

validate().catch((error) => {
  console.error("Skill validation error:", error);
  process.exitCode = 1;
});
