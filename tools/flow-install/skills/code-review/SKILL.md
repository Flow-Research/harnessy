---
name: code-review
description: "Provider-neutral Harnessy code review capability for local diffs and CI gates: deterministic discovery, review rubric, verifier pass, normalized JSON/Markdown/SARIF output, and evidence capture."
disable-model-invocation: true
allowed-tools: Read, Write, ApplyPatch, Grep, Glob, Bash
argument-hint: "[--base <ref>] [--head <ref>] [--spec <path>] [ci|verify|status]"
---

# Code Review

## Purpose

Review a local or CI code diff as a Harnessy capability run, not as an ad-hoc prompt.

The capability packages:

- deterministic changed-file discovery;
- review and severity rubrics;
- verifier rules;
- output and evidence contracts;
- provider-neutral execution through the active agent's native skill system.
- provider-neutral CI gate execution through `harness-code-review ci`.

Provider-specific projections are optional and live under `projections/` only when a provider-native surface materially improves quality or ergonomics.

## Inputs

- Optional `--base <ref>`: base ref, default `main`.
- Optional `--head <ref>`: head ref, default `HEAD`.
- Optional `--spec <path>`: spec, issue brief, or acceptance-criteria source.
- `ci`: run the deterministic CI gate and optional provider review command.
- `verify`: validate the latest or supplied review JSON.
- `status`: summarize current review artifacts.

Template paths are resolved from `${AGENTS_SKILLS_ROOT}/code-review/`.

## Steps

1. Follow `${AGENTS_SKILLS_ROOT}/code-review/commands/code-review.md` exactly.
2. Use `${AGENTS_SKILLS_ROOT}/code-review/capability.yaml` as the capability contract.
3. Load the review materials in `${AGENTS_SKILLS_ROOT}/code-review/materials/`.
4. Generate or update:
   - `.jarvis/context/evidence/code-review/<run-id>/discovery.json`
   - `.jarvis/context/evidence/code-review/<run-id>/feedback.json`
   - `.jarvis/context/evidence/code-review/<run-id>/REVIEW_REPORT.md`
   - `.jarvis/context/evidence/code-review/<run-id>/review.sarif`
   - `.jarvis/context/evidence/code-review/<run-id>/evidence.json`
5. Validate output with `${AGENTS_SKILLS_ROOT}/code-review/scripts/validate-output.py`.
6. Validate evidence with `${AGENTS_SKILLS_ROOT}/code-review/scripts/validate-evidence.py`.

For CI, prefer:

```bash
harness-code-review ci --json
```

The CI command exits non-zero only for critical/major findings, invalid output,
failed evidence verification, configured provider failure, or required AI review
that cannot run. If no provider review command is configured, it records
`review_status=skipped` and still emits deterministic discovery, Markdown,
SARIF, and evidence artifacts.

## Feedback Capture

Before finalizing, check whether this run exposed a reusable skill or capability lesson. Capture feedback when:

- the review misses an important risk;
- deterministic discovery needs a new cluster or risk surface;
- the output schema is too loose or too strict;
- provider-native execution needs a projection;
- the user corrects the severity policy or review rubric.

Use:

```bash
python3 "${AGENTS_SKILLS_ROOT}/_shared/trace_capture.py" capture \
  --skill "code-review" \
  --gate "run_retrospective" \
  --gate-type "retrospective" \
  --outcome "approved" \
  --feedback "<specific reusable lesson>"
```

Do not capture empty traces for normal successful runs with no reusable lesson.

## Output

- Machine-readable review: `.jarvis/context/evidence/code-review/<run-id>/feedback.json`
- Human-readable report: `.jarvis/context/evidence/code-review/<run-id>/REVIEW_REPORT.md`
- SARIF report: `.jarvis/context/evidence/code-review/<run-id>/review.sarif`
- Evidence bundle: `.jarvis/context/evidence/code-review/<run-id>/evidence.json`
