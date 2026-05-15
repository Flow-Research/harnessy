import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";

const getPlatform = () => {
  const platform = os.platform();
  if (platform === "darwin") return "darwin";
  if (platform === "linux") return "linux";
  return "other";
};

const parseList = (raw) => {
  if (!raw || typeof raw !== "string") return [];
  let value = raw.trim();
  if ((value.startsWith("\"") && value.endsWith("\"")) || (value.startsWith("'") && value.endsWith("'"))) {
    value = value.slice(1, -1);
  }
  return value.split(",").map((entry) => entry.trim()).filter(Boolean);
};

export const parseManifestContent = (content) => {
  const lines = content.split(/\r?\n/);
  const manifest = { dependencies: [], pythonPackages: [], nodePackages: [] };

  for (let index = 0; index < lines.length; index++) {
    const trimmed = lines[index].trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    if (trimmed.startsWith("python_packages:")) {
      manifest.pythonPackages = parseList(trimmed.slice("python_packages:".length));
      continue;
    }
    if (trimmed.startsWith("node_packages:")) {
      manifest.nodePackages = parseList(trimmed.slice("node_packages:".length));
      continue;
    }
    if (trimmed !== "dependencies:") continue;

    index++;
    let current = null;
    let inInstallBlock = false;
    for (; index < lines.length; index++) {
      const line = lines[index];
      const stripped = line.trim();
      if (!stripped) continue;
      const indent = line.match(/^\s*/)?.[0].length ?? 0;
      if (indent === 0 && !stripped.startsWith("- ")) {
        index--;
        break;
      }
      if (stripped.startsWith("- tool:")) {
        if (current) manifest.dependencies.push(current);
        current = {
          tool: stripped.slice("- tool:".length).trim().replace(/^['"]|['"]$/g, ""),
          required: true,
          install: {},
        };
        inInstallBlock = false;
        continue;
      }
      if (!current) continue;
      if (stripped === "install:") {
        inInstallBlock = true;
        continue;
      }
      const separatorIndex = stripped.indexOf(":");
      if (separatorIndex === -1) continue;
      const key = stripped.slice(0, separatorIndex).trim();
      const value = stripped.slice(separatorIndex + 1).trim().replace(/^['"]|['"]$/g, "");
      if (inInstallBlock) {
        current.install[key] = value;
        continue;
      }
      if (key === "required") current.required = /^(true|yes|1)$/i.test(value);
      else current[key] = value;
    }
    if (current) manifest.dependencies.push(current);
  }

  return manifest;
};

export const summarizeManifestRequirements = (manifestPath) => parseManifestContent(fs.readFileSync(manifestPath, "utf8"));

const commandAvailable = (command) => spawnSync(command, { shell: true, stdio: "ignore" }).status === 0;

const checkToolDependency = (dependency) => {
  const available = commandAvailable(dependency.check || `${dependency.tool} --version`);
  return {
    kind: "tool",
    name: dependency.tool,
    required: dependency.required !== false,
    available,
    authOk: available && dependency.auth_check ? commandAvailable(dependency.auth_check) : null,
    installCommand: dependency.install?.[getPlatform()] || dependency.install?.fallback || null,
  };
};

const checkPythonPackage = (spec) => {
  const [packageName, moduleNameRaw] = spec.split(":").map((entry) => entry.trim()).filter(Boolean);
  const moduleName = moduleNameRaw || packageName;
  return {
    kind: "python",
    name: packageName,
    required: true,
    available: commandAvailable(`python3 -c \"import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('${moduleName}') else 1)\"`),
    installCommand: `python3 -m pip install --user --disable-pip-version-check ${packageName}`,
  };
};

const resolveNodeInstaller = () => (commandAvailable("pnpm --version") ? "pnpm add -g" : "npm install -g");

const checkNodePackage = (packageName) => ({
  kind: "node",
  name: packageName,
  required: true,
  available: commandAvailable(`pnpm list -g --depth 0 ${packageName}`) || commandAvailable(`npm ls -g --depth 0 ${packageName}`),
  installCommand: `${resolveNodeInstaller()} ${packageName}`,
});

export const checkManifest = (manifestPath) => {
  const manifest = summarizeManifestRequirements(manifestPath);
  const requirements = [
    ...manifest.dependencies.map(checkToolDependency),
    ...manifest.pythonPackages.map(checkPythonPackage),
    ...manifest.nodePackages.map(checkNodePackage),
  ];
  return {
    manifestPath,
    requirements,
    missingRequired: requirements.filter((entry) => entry.required && !entry.available),
  };
};

export const collectManifestPaths = ({ cwd, manifestPath, skillsRoot }) => {
  if (manifestPath) {
    const absolute = path.resolve(cwd, manifestPath);
    if (!fs.existsSync(absolute)) throw new Error(`Manifest not found: ${absolute}`);
    return [absolute];
  }
  if (!skillsRoot) throw new Error("Provide --manifest <path> or --skills-root <path>.");
  const absoluteRoot = path.resolve(cwd, skillsRoot);
  if (!fs.existsSync(absoluteRoot)) throw new Error(`Skills root not found: ${absoluteRoot}`);
  return fs.readdirSync(absoluteRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(absoluteRoot, entry.name, "manifest.yaml"))
    .filter((entry) => fs.existsSync(entry));
};

export const planSkillsRoot = (skillsRoot, cwd = process.cwd()) => collectManifestPaths({ cwd, skillsRoot }).map((manifestPath) => checkManifest(manifestPath));

const installRequirement = (requirement, dryRun) => {
  if (requirement.available || !requirement.installCommand) return { ...requirement, changed: false, ok: requirement.available, skipped: true };
  if (dryRun) return { ...requirement, changed: false, ok: true, skipped: false, dryRun: true };
  const result = spawnSync(requirement.installCommand, { shell: true, stdio: "inherit" });
  return { ...requirement, changed: result.status === 0, ok: result.status === 0, skipped: false, exitCode: result.status };
};

export const installManifest = (manifestPath, { dryRun = false } = {}) => {
  const check = checkManifest(manifestPath);
  const attempted = check.requirements
    .filter((requirement) => requirement.required && !requirement.available)
    .map((requirement) => installRequirement(requirement, dryRun));
  return { manifestPath, attempted, ok: attempted.every((entry) => entry.ok) };
};
