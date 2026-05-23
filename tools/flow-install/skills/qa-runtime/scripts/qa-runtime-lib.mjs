import fs from "node:fs";
import path from "node:path";

const CANONICAL_ID_RE = /^[A-Z][A-Z0-9]{1,4}-\d{3}$/;
const SCENARIO_LIKE_RE = /^##\s+[A-Za-z0-9]+[.\-][A-Za-z0-9]/;
const SPEC_HEADING_RE = /^##\s+([A-Z][A-Z0-9]{1,4}-\d{3})(?:\s+(.+))?$/;
const FIELD_RE = /^([A-Z][A-Za-z ]*[A-Za-z]):\s*(.*)$/;
const TEST_CALL_RE = /\b(?:it|test)\s*\(\s*["'`]([^"'`]+)["'`]/g;
const TEST_ID_PREFIX_RE = /^\s*(?:[A-Z][A-Z0-9]{1,4}-\d{3})\b/;
const HEADER_SPEC_RE = /^\s*\/\/\s*@qa-spec:\s*(.+?)\s*$/;
const HEADER_SUITE_RE = /^\s*\/\/\s*@qa-suite:\s*(.+?)\s*$/;
const VALID_LAYERS = new Set(["browser", "api", "security", "manual"]);
const VALID_STATUSES = new Set(["implemented", "scaffolded", "not-implemented", "manual-only"]);
const KNOWN_FIELDS = new Set([
  "Layer",
  "Linked Refs",
  "User Flow",
  "Status",
  "Test File",
  "Role",
  "Route",
  "Mode",
  "Type",
  "Prerequisites",
  "Function",
  "Module",
  "Seed",
  "Input",
  "DB Assert",
  "Expected",
  "Security Class",
  "Threat Actor",
  "Attack Surface",
  "Exploitation",
]);

const usage = (commandName = "qa") => `Usage:\n  ${commandName} ids [--profile <path>] [--json]\n  ${commandName} tests [--profile <path>] [--json]\n  ${commandName} drift [--profile <path>] [--json]\n  ${commandName} coverage [--profile <path>] [--json] [--output <path>]\n`;

const readJson = (filePath) => JSON.parse(fs.readFileSync(filePath, "utf8"));

const normalizeArray = (value) => {
  if (!value) return [];
  return Array.isArray(value) ? value.filter(Boolean) : [value].filter(Boolean);
};

const parseArgs = (argv) => {
  const args = [...argv];
  const subcommand = args[0] && !args[0].startsWith("--") ? args.shift() : null;
  const flags = {};
  for (let index = 0; index < args.length; index++) {
    const current = args[index];
    if (!current.startsWith("--")) continue;
    const key = current.slice(2);
    const next = args[index + 1];
    if (!next || next.startsWith("--")) {
      flags[key] = true;
      continue;
    }
    flags[key] = next;
    index++;
  }
  return { subcommand, flags };
};

const resolveProfilePath = (cwd, explicitPath) => {
  if (explicitPath) {
    const absolute = path.resolve(cwd, explicitPath);
    if (!fs.existsSync(absolute)) {
      throw new Error(`QA profile not found: ${absolute}`);
    }
    return absolute;
  }

  let current = cwd;
  while (true) {
    for (const candidate of [".harnessy/qa-profile.json", ".flow/qa-profile.json", "qa/qa-profile.json"]) {
      const absolute = path.join(current, candidate);
      if (fs.existsSync(absolute)) return absolute;
    }
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }

  throw new Error("No QA profile found. Create .harnessy/qa-profile.json or pass --profile.");
};

const loadProfile = (cwd, explicitPath) => {
  const profilePath = resolveProfilePath(cwd, explicitPath);
  const profile = readJson(profilePath);
  if (!profile || typeof profile !== "object") throw new Error(`Invalid QA profile JSON: ${profilePath}`);
  if (!Array.isArray(profile.specs) || profile.specs.length === 0) throw new Error(`QA profile must declare a non-empty specs array: ${profilePath}`);
  if (!Array.isArray(profile.apps) || profile.apps.length === 0) throw new Error(`QA profile must declare a non-empty apps array: ${profilePath}`);
  return { profilePath, rootDir: path.dirname(profilePath), profile };
};

const parseSpecFile = (content, relativeFilePath, app, defaultLayer) => {
  const records = [];
  const errors = [];
  const lines = content.split(/\r?\n/);
  let current = null;

  const flush = () => {
    if (!current) return;
    const layerField = current.fields.Layer?.toLowerCase();
    const statusField = current.fields.Status?.toLowerCase();
    const layer = VALID_LAYERS.has(layerField) ? layerField : defaultLayer;
    const status = VALID_STATUSES.has(statusField) ? statusField : "not-implemented";
    if (!CANONICAL_ID_RE.test(current.id)) {
      errors.push({ file: relativeFilePath, line: current.line, message: `ID does not match canonical form: ${current.id}` });
      current = null;
      return;
    }
    records.push({
      app,
      layer,
      id: current.id,
      file: relativeFilePath,
      line: current.line,
      title: current.title,
      linkedRefs: current.fields["Linked Refs"] ? current.fields["Linked Refs"].split(",").map((entry) => entry.trim()).filter(Boolean) : [],
      status,
      testFile: current.fields["Test File"] || undefined,
      executionSteps: current.steps,
      dbAssert: current.fields["DB Assert"] || undefined,
      expected: current.fields.Expected || undefined,
      raw: current.fields,
    });
    current = null;
  };

  for (let index = 0; index < lines.length; index++) {
    const line = lines[index];
    const lineNumber = index + 1;
    if (line.startsWith("## ")) {
      flush();
      const canonicalMatch = line.trimEnd().match(SPEC_HEADING_RE);
      if (canonicalMatch) {
        current = { id: canonicalMatch[1], title: (canonicalMatch[2] || "").trim(), line: lineNumber, fields: {}, steps: [] };
      } else if (SCENARIO_LIKE_RE.test(line)) {
        errors.push({ file: relativeFilePath, line: lineNumber, message: `Heading does not match canonical form: ${line.trim()}` });
      }
      continue;
    }
    if (!current) continue;
    const trimmed = line.trim();
    if (trimmed.startsWith("- ")) {
      current.steps.push(trimmed.slice(2).trim());
      continue;
    }
    const fieldMatch = line.match(FIELD_RE);
    if (fieldMatch && KNOWN_FIELDS.has(fieldMatch[1])) {
      current.fields[fieldMatch[1]] = (fieldMatch[2] || "").trim();
    }
  }

  flush();
  return { records, errors };
};

export const parseAllSpecs = ({ cwd, profilePath }) => {
  const { rootDir, profile } = loadProfile(cwd, profilePath);
  const records = [];
  const errors = [];
  for (const spec of profile.specs) {
    const absolutePath = path.resolve(rootDir, spec.path);
    try {
      const content = fs.readFileSync(absolutePath, "utf8");
      const parsed = parseSpecFile(content, path.relative(cwd, absolutePath), spec.app, spec.layer);
      records.push(...parsed.records);
      errors.push(...parsed.errors);
    } catch (error) {
      errors.push({ file: spec.path, line: 0, message: `Failed to read spec file: ${error.message}` });
    }
  }
  return { records, errors, profile };
};

const extractHeaderAnnotations = (content) => {
  const head = content.split(/\r?\n/).slice(0, 30);
  let spec;
  let suite;
  for (const line of head) {
    if (!spec) {
      const match = line.match(HEADER_SPEC_RE);
      if (match) spec = match[1].trim();
    }
    if (!suite) {
      const match = line.match(HEADER_SUITE_RE);
      if (match) suite = match[1].trim();
    }
    if (spec && suite) break;
  }
  return { spec, suite };
};

const safeWalk = (rootDir) => {
  if (!fs.existsSync(rootDir)) return [];
  const stat = fs.statSync(rootDir, { throwIfNoEntry: false });
  if (!stat || !stat.isDirectory()) return [];
  const output = [];
  const stack = [rootDir];
  while (stack.length > 0) {
    const current = stack.pop();
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const absolute = path.join(current, entry.name);
      if (entry.isDirectory()) stack.push(absolute);
      else if (entry.isFile()) output.push(absolute);
    }
  }
  return output;
};

export const scanAllTests = ({ cwd, profilePath }) => {
  const { rootDir, profile } = loadProfile(cwd, profilePath);
  const records = [];
  const filesMissingHeader = [];
  let filesScanned = 0;
  for (const app of profile.apps) {
    const tests = app.tests || {};
    for (const layer of ["browser", "api"]) {
      for (const root of normalizeArray(tests[layer])) {
        const absoluteRoot = path.resolve(rootDir, root);
        for (const absoluteFilePath of safeWalk(absoluteRoot)) {
          if (!/\.(api\.test|spec)\.[cm]?[jt]s$/.test(absoluteFilePath)) continue;
          filesScanned++;
          const content = fs.readFileSync(absoluteFilePath, "utf8");
          const relativeFilePath = path.relative(cwd, absoluteFilePath);
          const headers = extractHeaderAnnotations(content);
          if (!headers.spec || !headers.suite) filesMissingHeader.push(relativeFilePath);
          const lines = content.split(/\r?\n/);
          for (let lineIndex = 0; lineIndex < lines.length; lineIndex++) {
            const line = lines[lineIndex];
            const matches = line.matchAll(TEST_CALL_RE);
            for (const match of matches) {
              const testName = match[1];
              const idMatch = testName.match(TEST_ID_PREFIX_RE);
              if (!idMatch) continue;
              records.push({ app: app.id, layer, testFile: relativeFilePath, line: lineIndex + 1, extractedId: idMatch[0].trim(), suiteAnnotation: headers.suite, specAnnotation: headers.spec });
            }
          }
        }
      }
    }
  }
  return { records, filesScanned, filesMissingHeader, profile };
};

const toIdMap = (records, key = "id") => {
  const map = new Map();
  for (const record of records) {
    const id = record[key];
    const existing = map.get(id);
    if (existing) existing.push(record);
    else map.set(id, [record]);
  }
  return map;
};

export const computeDrift = ({ cwd, profilePath }) => {
  const specs = parseAllSpecs({ cwd, profilePath });
  const tests = scanAllTests({ cwd, profilePath });
  const testsById = toIdMap(tests.records, "extractedId");
  const specsById = toIdMap(specs.records, "id");
  const issues = [];
  for (const error of specs.errors) issues.push({ rule: "spec-parse", severity: "error", ...error });
  for (const specRecord of specs.records) {
    if (specRecord.status === "implemented" && !testsById.has(specRecord.id)) {
      issues.push({ rule: "implemented-without-test", severity: "error", file: specRecord.file, line: specRecord.line, message: `${specRecord.id} is implemented but has no matching test` });
    }
  }
  for (const testRecord of tests.records) {
    if (!specsById.has(testRecord.extractedId)) {
      issues.push({ rule: "test-references-nonexistent-spec", severity: "error", file: testRecord.testFile, line: testRecord.line, message: `${testRecord.extractedId} does not exist in the configured spec sources` });
    }
  }
  for (const filePath of tests.filesMissingHeader) {
    issues.push({ rule: "test-missing-header", severity: "error", file: filePath, line: 1, message: "Missing @qa-spec / @qa-suite header" });
  }
  return { ok: issues.length === 0, issues, specs, tests };
};

export const computeCoverage = ({ cwd, profilePath }) => {
  const specs = parseAllSpecs({ cwd, profilePath });
  const tests = scanAllTests({ cwd, profilePath });
  const testsById = toIdMap(tests.records, "extractedId");
  const byAppLayer = new Map();
  const byPrefix = new Map();
  for (const record of specs.records) {
    const appLayerKey = `${record.app}:${record.layer}`;
    const appLayer = byAppLayer.get(appLayerKey) || { app: record.app, layer: record.layer, total: 0, implemented: 0, withTests: 0 };
    appLayer.total++;
    if (record.status === "implemented") appLayer.implemented++;
    if (testsById.has(record.id)) appLayer.withTests++;
    byAppLayer.set(appLayerKey, appLayer);

    const prefix = record.id.split("-")[0];
    const prefixEntry = byPrefix.get(prefix) || { prefix, total: 0, implemented: 0, withTests: 0, apps: new Set(), layers: new Set() };
    prefixEntry.total++;
    if (record.status === "implemented") prefixEntry.implemented++;
    if (testsById.has(record.id)) prefixEntry.withTests++;
    prefixEntry.apps.add(record.app);
    prefixEntry.layers.add(record.layer);
    byPrefix.set(prefix, prefixEntry);
  }
  return {
    generatedAt: new Date().toISOString(),
    parseErrors: specs.errors.length,
    filesMissingHeader: tests.filesMissingHeader.length,
    appLayers: [...byAppLayer.values()].sort((a, b) => `${a.app}:${a.layer}`.localeCompare(`${b.app}:${b.layer}`)),
    prefixes: [...byPrefix.values()].map((entry) => ({ ...entry, apps: [...entry.apps].sort(), layers: [...entry.layers].sort() })).sort((a, b) => a.prefix.localeCompare(b.prefix)),
  };
};

const renderMarkdownCoverage = (coverage) => {
  const lines = ["# QA Coverage", "", `Generated: ${coverage.generatedAt}`, "", "## App / Layer Summary", "", "| App | Layer | Total | Implemented | With Tests |", "|---|---|---:|---:|---:|"];
  for (const row of coverage.appLayers) lines.push(`| ${row.app} | ${row.layer} | ${row.total} | ${row.implemented} | ${row.withTests} |`);
  lines.push("", "## Prefix Summary", "", "| Prefix | Total | Implemented | With Tests | Apps | Layers |", "|---|---:|---:|---:|---|---|");
  for (const row of coverage.prefixes) lines.push(`| ${row.prefix} | ${row.total} | ${row.implemented} | ${row.withTests} | ${row.apps.join(", ")} | ${row.layers.join(", ")} |`);
  lines.push("", "## Drift Snapshot", "", `- Parse errors: ${coverage.parseErrors}`, `- Files missing headers: ${coverage.filesMissingHeader}`);
  return `${lines.join("\n")}\n`;
};

const writeJson = (stream, value) => stream.write(`${JSON.stringify(value, null, 2)}\n`);

const renderDrift = (stream, drift, commandName = "qa") => {
  if (drift.ok) {
    stream.write(`${commandName} drift: no issues found\n`);
    return;
  }
  stream.write(`${commandName} drift: ${drift.issues.length} issue(s) found\n`);
  for (const issue of drift.issues) stream.write(`- [${issue.rule}] ${issue.file}:${issue.line} ${issue.message}\n`);
};

export const runCli = async (argv, io = {}) => {
  const stdout = io.stdout || process.stdout;
  const stderr = io.stderr || process.stderr;
  const cwd = io.cwd || process.cwd();
  const commandName = io.commandName || "qa";
  const { subcommand, flags } = parseArgs(argv);
  if (!subcommand || flags.help || flags.h) {
    stdout.write(usage(commandName));
    return 0;
  }
  try {
    if (subcommand === "ids") {
      const result = parseAllSpecs({ cwd, profilePath: flags.profile });
      if (flags.json) writeJson(stdout, result);
      else stdout.write(`${commandName} ids: ${result.records.length} record(s), ${result.errors.length} parse error(s)\n`);
      return result.errors.length > 0 ? 1 : 0;
    }
    if (subcommand === "tests") {
      const result = scanAllTests({ cwd, profilePath: flags.profile });
      if (flags.json) writeJson(stdout, result);
      else stdout.write(`${commandName} tests: scanned ${result.filesScanned} file(s), extracted ${result.records.length} test ID(s)\n`);
      return 0;
    }
    if (subcommand === "drift") {
      const drift = computeDrift({ cwd, profilePath: flags.profile });
      if (flags.json) writeJson(stdout, drift);
      else renderDrift(stdout, drift, commandName);
      return drift.ok ? 0 : 1;
    }
    if (subcommand === "coverage") {
      const coverage = computeCoverage({ cwd, profilePath: flags.profile });
      if (flags.json) {
        writeJson(stdout, coverage);
        return 0;
      }
      const { rootDir, profile } = loadProfile(cwd, flags.profile);
      const outputPath = flags.output ? path.resolve(cwd, flags.output) : profile.output?.coverage ? path.resolve(rootDir, profile.output.coverage) : null;
      const markdown = renderMarkdownCoverage(coverage);
      if (outputPath) {
        fs.mkdirSync(path.dirname(outputPath), { recursive: true });
        fs.writeFileSync(outputPath, markdown, "utf8");
        stdout.write(`${commandName} coverage: wrote ${path.relative(cwd, outputPath)}\n`);
      } else {
        stdout.write(markdown);
      }
      return 0;
    }
    stderr.write(`Unknown subcommand: ${subcommand}\n\n${usage(commandName)}`);
    return 2;
  } catch (error) {
    stderr.write(`${error.message}\n`);
    return 1;
  }
};
