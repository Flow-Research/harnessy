# Provider Projections

Provider-specific projections are optional.

The default Code Review capability is provider-neutral: Harnessy exposes the same `SKILL.md`, command docs, rubrics, contracts, deterministic scripts, and `harness-code-review ci` gate through each provider's native skill discovery and registration path.

Add a provider projection only when the provider has a native capability surface that materially improves review quality, CI integration, user experience, or evidence capture.

Examples:

- `projections/codex/agents/openai.yaml` for Codex app metadata, invocation policy, or tool dependency hints.
- `projections/codex/github-action.prompt.md` for a CI-native Codex review prompt.
- `projections/claude/workflow-template.js` for Claude dynamic workflows when worker fan-out improves quality.
- `projections/opencode/skill-wrapper.md` only if OpenCode needs materially different instructions.

Do not create empty provider folders just to show support. Provider support starts with the shared capability contract and the existing Harnessy skill registration layer.

## CI Projection Rule

CI integrations must remain thin projections over `harness-code-review ci`.

GitHub Actions, GitLab CI, Jenkins, Buildkite, or any other CI system may handle:

- checkout and base/head fetch depth;
- secret injection;
- command-shim installation;
- artifact upload;
- optional SARIF upload or native annotation.

They must not fork the gate policy. The generic command owns diff discovery,
review-command execution, schema validation, SARIF/Markdown rendering, evidence
capture, and exit-code semantics.

GitHub Actions starter template:

```text
tools/flow-install/templates/harness-code-review.yml
```

Generic CI shape:

```bash
harness-code-review ci --json
```

Always upload:

```text
.jarvis/context/evidence/code-review/
```
