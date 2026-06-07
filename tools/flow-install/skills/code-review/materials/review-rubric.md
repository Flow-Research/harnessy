# Code Review Rubric

Use this rubric for every Harnessy Code Review capability run.

## Review Priorities

1. Correctness: The changed behavior works as intended and does not introduce a plausible runtime regression.
2. Requirement compliance: When a spec, issue, PR description, or acceptance criteria are provided, the implementation satisfies them directly.
3. Simplicity: The implementation is no more complex than the requirement demands and avoids speculative abstractions.
4. Architecture fit: The change follows local ownership boundaries, dependency direction, naming, and conventions.
5. Test adequacy: The tests would catch the behavior that changed, prefer integration coverage where appropriate, and avoid false-green mocks.
6. Security and safety: The change does not weaken auth, permissions, secrets handling, sandbox policy, egress policy, deployment safety, or data isolation.
7. Harnessy standards: Changes to QA, CI, deployment, skills, profiles, scripts, and context follow the shared Harnessy standards when present.

## Review Method

- Start from deterministic changed-file discovery. Do not infer scope from memory.
- Read the relevant diff and nearby code before raising a finding.
- Prefer a small number of high-confidence findings over broad commentary.
- Tie every blocking finding to concrete file and line evidence.
- Treat missing tests as blocking only when the changed behavior has a realistic regression path.
- For docs-only changes, block only when the doc would cause dangerous or materially wrong execution.
- Do not flag style preferences unless they create maintainability, correctness, or standards risk.

## Required Output Discipline

- Use the normalized JSON output shape from `contracts/output.schema.json`.
- Use only the severities from `materials/severity-taxonomy.md`.
- The final verdict must follow the severity policy:
  - `critical` or `major` finding: `request_changes`
  - only `minor` or `suggestion` findings: `comment`
  - no findings: `approve`
