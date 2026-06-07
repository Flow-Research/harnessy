---
description: Provider-neutral Harnessy code review capability for local diffs and CI gates
argument-hint: "[--base <ref>] [--head <ref>] [--spec <path>] [ci|verify|status]"
---

# Harnessy Code Review Capability

## Mission

Review `base...head` as a governed Harnessy capability run.

The review must answer:

> Can this change merge under Harnessy's correctness, simplicity, test adequacy, standards, and evidence expectations?

Do not treat this as a broad style review. Produce a small number of high-confidence findings with concrete evidence.

## Defaults

- Source type: `local_diff`
- Base ref: `main`
- Head ref: `HEAD`
- QA profile: `.jarvis/context/profiles/qa.json`
- Evidence root: `.jarvis/context/evidence/code-review/`
- Output directory: `.jarvis/context/evidence/code-review/<run-id>/`
- Blocking severities: `critical`, `major`
- CI entrypoint: `harness-code-review ci`
- CI report formats: JSON, Markdown, SARIF

## Command Routing

### Default Review

Run a full capability review of the local diff.

Recognize optional flags:

- `--base <ref>`
- `--head <ref>`
- `--spec <path>`

If a flag is omitted, use the defaults above. Do not ask for a spec path when one is not provided.

### `verify`

Validate the latest review JSON, or a supplied review JSON path, with:

```bash
python3 "${AGENTS_SKILLS_ROOT}/code-review/scripts/validate-output.py" <review-json>
```

If valid, summarize the verdict, finding counts, and whether evidence exists.

### `status`

Report whether these artifacts exist:

- `.jarvis/context/evidence/code-review/<run-id>/discovery.json`
- `.jarvis/context/evidence/code-review/<run-id>/feedback.json`
- `.jarvis/context/evidence/code-review/<run-id>/REVIEW_REPORT.md`
- `.jarvis/context/evidence/code-review/<run-id>/review.sarif`
- `.jarvis/context/evidence/code-review/<run-id>/evidence.json`

Do not create a top-level `code-review/` output directory. Older runs may have used it; new runs must use `.jarvis/context/evidence/code-review/<run-id>/`.

If one or more evidence runs exist, use the newest run directory by modification time unless the user supplies a specific path. If `feedback.json` exists, summarize its verdict and finding counts.

### `ci`

Run the provider-neutral CI quality gate:

```bash
harness-code-review ci --json
```

Recognize optional flags:

- `--base <ref>`
- `--head <ref>`
- `--run-id <id>`
- `--ci-profile <path>`
- `--output-root <path>`
- `--format json,markdown,sarif`
- `--review-command <command>`
- `--require-ai`

Base/head resolution order is:

1. explicit flags;
2. `HARNESSY_CODE_REVIEW_BASE` / `HARNESSY_CODE_REVIEW_HEAD`;
3. `.jarvis/context/profiles/ci.json` `codeReview.base_ref` / `codeReview.head_ref`;
4. CI provider metadata;
5. `main` / `HEAD`.

If `HARNESSY_CODE_REVIEW_COMMAND` or `--review-command` is set, the command must
write JSON to `$HARNESSY_CODE_REVIEW_FEEDBACK_JSON`. Harnessy passes these env vars:

- `HARNESSY_CODE_REVIEW_OUTPUT_DIR`
- `HARNESSY_CODE_REVIEW_DISCOVERY_JSON`
- `HARNESSY_CODE_REVIEW_FEEDBACK_JSON`
- `HARNESSY_CODE_REVIEW_BASE_REF`
- `HARNESSY_CODE_REVIEW_HEAD_REF`
- `HARNESSY_CODE_REVIEW_CI_PROVIDER`
- `HARNESSY_CODE_REVIEW_CI_RUN_ID`

The CI gate exits:

- `0` when the gate passes;
- `1` when critical or major findings exist;
- `2` when deterministic discovery, schema validation, evidence generation, or evidence verification fails;
- `3` when a configured or required provider review cannot run.

If no review command is configured and AI is not required, the gate still writes
artifacts with `mode=deterministic_only` and `review_status=skipped`.

## Required Materials

Read these files before producing findings:

- `${AGENTS_SKILLS_ROOT}/code-review/capability.yaml`
- `${AGENTS_SKILLS_ROOT}/code-review/materials/review-rubric.md`
- `${AGENTS_SKILLS_ROOT}/code-review/materials/severity-taxonomy.md`
- `${AGENTS_SKILLS_ROOT}/code-review/materials/verifier-rubric.md`

Also read the repo's Harnessy standards when present:

- `.jarvis/context/docs/harnessy-positioning.md`
- `.jarvis/context/docs/standards/qa-process.md`
- `.jarvis/context/docs/standards/testing-strategy.md`
- `.jarvis/context/docs/standards/ci-process.md`
- `.jarvis/context/docs/standards/skill-feedback-protocol.md`

Load the optional spec path only if the user provides one.

## Phase 1: Discovery

Create a run directory under the existing Harnessy evidence root:

```bash
RUN_ID="cr_$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_DIR=".jarvis/context/evidence/code-review/${RUN_ID}"
mkdir -p "${OUTPUT_DIR}"
```

Then run:

```bash
python3 "${AGENTS_SKILLS_ROOT}/code-review/scripts/discover-diff.py" \
  --base "<base-ref>" \
  --head "<head-ref>" \
  --output "${OUTPUT_DIR}/discovery.json"
```

Use `${OUTPUT_DIR}/discovery.json` as the authoritative review scope.

Inspect:

- changed-file inventory;
- risk surfaces;
- shortstat;
- relevant diffs and nearby files;
- tests touching the changed surfaces.

For the diff itself, prefer targeted commands such as:

```bash
git diff --unified=80 <base-ref>...<head-ref> -- <path>
rg "<symbol-or-route>" <relevant-root>
```

## Phase 2: Review

Produce candidate findings against the rubric.

Categories should be concise and operational, for example:

- `correctness`
- `missing_requirement`
- `test_gap`
- `architecture`
- `over_engineering`
- `security_policy`
- `deployment_risk`
- `qa_evidence`
- `standards`

Every blocking finding must include:

- changed file path;
- line or line range;
- specific evidence;
- concrete risk;
- recommended fix.

## Phase 3: Test Adequacy

For each risky changed behavior, answer:

- What behavior changed?
- Which tests or QA gates should catch regressions?
- Were those tests added or updated?
- Are mocks hiding the behavior that should be integration-tested?
- Would CI/deploy evidence catch this class of failure?

Missing test coverage is `major` only when the diff introduces or changes risky behavior and the current tests would plausibly miss a regression.

## Phase 4: Verifier Pass

Apply `${AGENTS_SKILLS_ROOT}/code-review/materials/verifier-rubric.md`.

Remove or downgrade findings that are:

- speculative;
- preference-only;
- missing concrete file/line evidence;
- not tied to the changed scope;
- too severe for the risk described.

The verifier must ensure the verdict follows:

- any `critical` or `major` finding -> `request_changes`
- only `minor` or `suggestion` findings -> `comment`
- no findings -> `approve`

## Phase 5: Write Artifacts

Write `${OUTPUT_DIR}/feedback.json` in this shape:

```json
{
  "schema_version": 1,
  "mode": "ai_review",
  "review_status": "completed",
  "verdict": "approve",
  "summary": "No blocking issues found.",
  "findings": [],
  "tests_reviewed": [],
  "missing_tests": [],
  "verification": {
    "schema_valid": true,
    "citations_valid": true,
    "blocking_findings_verified": true,
    "verifier_notes": "Verifier found no unsupported blocking findings."
  }
}
```

Then validate it:

```bash
python3 "${AGENTS_SKILLS_ROOT}/code-review/scripts/validate-output.py" "${OUTPUT_DIR}/feedback.json"
```

Write `${OUTPUT_DIR}/REVIEW_REPORT.md` using `${AGENTS_SKILLS_ROOT}/code-review/materials/report-template.md` as the shape.

For CI runs, `harness-code-review ci` writes `${OUTPUT_DIR}/review.sarif`.

Build evidence:

```bash
python3 "${AGENTS_SKILLS_ROOT}/code-review/scripts/build-evidence.py" \
  --discovery "${OUTPUT_DIR}/discovery.json" \
  --review "${OUTPUT_DIR}/feedback.json" \
  --run-id "${RUN_ID}" \
  --markdown-report "${OUTPUT_DIR}/REVIEW_REPORT.md" \
  --validation-result pass \
  --provider "${HARNESSY_AI_PROVIDER:-codex}" \
  --print-path
```

Then validate evidence:

```bash
python3 "${AGENTS_SKILLS_ROOT}/code-review/scripts/validate-evidence.py" "${OUTPUT_DIR}/evidence.json"
```

Evidence verification checks:

- required evidence fields and enum values;
- referenced artifact paths exist;
- `base_ref`, `head_ref`, file count, risk surfaces, and commands match `discovery.json`;
- mode, review status, skipped reason, verifier result, and verdict match `feedback.json`;
- passing gates have no critical or major findings.

If validation fails, fix the JSON or artifact mismatch before accepting the run.

## Completion Criteria

- Discovery exists and matches the selected refs.
- `feedback.json` passes `validate-output`.
- Markdown report matches the JSON verdict and findings.
- SARIF report exists for CI artifact/code-scanning consumers when requested.
- Evidence bundle is written.
- `evidence.json` passes `validate-evidence`.
- Final response reports verdict, blocking finding count, artifacts, and tests or checks run.

## Feedback Capture

Capture a `code-review` decision trace only when this run exposes a reusable lesson. Do not capture empty traces.
