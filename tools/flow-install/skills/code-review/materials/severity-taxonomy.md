# Severity Taxonomy

## critical

Blocks merge. Use only for changes that are likely to cause one of:

- security vulnerability or secret exposure;
- data loss, tenant isolation failure, or irreversible destructive behavior;
- production outage, broken deployment, or broken rollback path;
- major requirement failure where the feature cannot work.

## major

Blocks merge. Use for serious issues that must be fixed before approval:

- incorrect behavior with a plausible user or operator impact;
- missing requirement or acceptance criterion;
- missing test coverage for a risky behavior change;
- architecture or policy violation that will make future work unsafe or hard to maintain;
- false-green QA, CI, or deployment evidence.

## minor

Does not block merge. Use for localized issues that should be fixed when practical:

- unclear naming;
- small edge-case risk;
- local maintainability concern;
- incomplete but non-critical documentation;
- test readability or organization issue that does not invalidate coverage.

## suggestion

Does not block merge. Use for optional improvements:

- alternative implementation ideas;
- future refactor opportunities;
- extra tests beyond the risk level;
- documentation polish.

## Downgrade Rules

- Downgrade if evidence is indirect or speculative.
- Downgrade broad style preferences unless they create a concrete risk.
- Downgrade docs-only concerns unless they would mislead an operator or agent into unsafe behavior.
- Do not mark a finding `major` only because a different implementation would be cleaner.
