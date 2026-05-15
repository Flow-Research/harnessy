import test from "node:test";
import assert from "node:assert/strict";

import { parseManifestContent } from "../../tools/flow-install/lib/dependencies.mjs";

test("dependency-manager parses tool and package declarations", () => {
  const manifest = parseManifestContent(`name: sample
python_packages: "PyYAML:yaml, requests"
node_packages: "yaml, zod"
dependencies:
  - tool: gh
    check: "gh --version"
    required: true
    install:
      darwin: "brew install gh"
      fallback: "https://cli.github.com/"
  - tool: tmux
    check: "tmux -V"
    required: false
`);

  assert.deepEqual(manifest.pythonPackages, ["PyYAML:yaml", "requests"]);
  assert.deepEqual(manifest.nodePackages, ["yaml", "zod"]);
  assert.equal(manifest.dependencies.length, 2);
  assert.equal(manifest.dependencies[0].tool, "gh");
  assert.equal(manifest.dependencies[0].install.darwin, "brew install gh");
  assert.equal(manifest.dependencies[1].required, false);
});
