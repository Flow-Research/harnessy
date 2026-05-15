import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { computeCoverage, computeDrift, parseAllSpecs, runCli, scanAllTests } from "../../tools/flow-install/skills/qa-runtime/scripts/qa-runtime-lib.mjs";

const createFixture = () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "qa-runtime-"));
  fs.mkdirSync(path.join(root, ".harnessy"), { recursive: true });
  fs.mkdirSync(path.join(root, "qa/browser/scripts"), { recursive: true });
  fs.mkdirSync(path.join(root, "apps/web/tests/browser-integration/suites"), { recursive: true });
  fs.writeFileSync(path.join(root, ".harnessy/qa-profile.json"), JSON.stringify({
    version: 1,
    specs: [
      { path: "../qa/browser/scripts/web-regression.md", app: "web", layer: "browser" }
    ],
    apps: [
      { id: "web", tests: { browser: ["../apps/web/tests/browser-integration/suites"] } }
    ],
    output: { coverage: "../qa/qa-coverage.md" }
  }, null, 2));
  fs.writeFileSync(path.join(root, "qa/browser/scripts/web-regression.md"), `## AUTH-001 Login works

Layer: browser
Status: implemented
Test File: apps/web/tests/browser-integration/suites/auth.spec.ts

- Open the login page
Expected: Login succeeds

## AUTH-002 Logged out users are redirected

Layer: browser
Status: scaffolded

- Open a protected page
Expected: Redirect to login
`);
  fs.writeFileSync(path.join(root, "apps/web/tests/browser-integration/suites/auth.spec.ts"), `// @qa-spec: qa/browser/scripts/web-regression.md
// @qa-suite: AUTH (authentication)

import { test } from "vitest";

test("AUTH-001 login works", () => {});
`);
  return root;
};

test("qa-runtime parses specs and tests from profile", () => {
  const root = createFixture();
  const specs = parseAllSpecs({ cwd: root });
  const tests = scanAllTests({ cwd: root });
  assert.equal(specs.records.length, 2);
  assert.equal(specs.errors.length, 0);
  assert.equal(tests.records.length, 1);
  assert.equal(tests.filesMissingHeader.length, 0);
});

test("qa-runtime drift flags implemented scenarios without tests", () => {
  const root = createFixture();
  fs.appendFileSync(path.join(root, "qa/browser/scripts/web-regression.md"), `
## AUTH-003 Missing test

Layer: browser
Status: implemented

- Attempt the flow
Expected: It works
`);
  const drift = computeDrift({ cwd: root });
  assert.equal(drift.ok, false);
  assert.ok(drift.issues.some((issue) => issue.rule === "implemented-without-test"));
});

test("qa-runtime coverage summarizes app/layer and prefix counts", () => {
  const root = createFixture();
  const coverage = computeCoverage({ cwd: root });
  assert.equal(coverage.appLayers.length, 1);
  assert.equal(coverage.prefixes.length, 1);
  assert.equal(coverage.prefixes[0].prefix, "AUTH");
  assert.equal(coverage.prefixes[0].withTests, 1);
});

test("qa-runtime help renders configured command name", async () => {
  let output = "";
  const code = await runCli(["--help"], {
    commandName: "qa",
    cwd: createFixture(),
    stdout: { write: (chunk) => { output += chunk; } },
    stderr: { write: () => {} },
  });
  assert.equal(code, 0);
  assert.match(output, /qa ids \[--profile <path>\]/);
  assert.doesNotMatch(output, /flow-qa ids/);
});
