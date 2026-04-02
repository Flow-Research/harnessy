# Attribute Validation

This directory contains the validation suite for the Phase 1 descriptive attribution layer.

It also contains the Phase 1.5 validation-gate checks for replay review capture and validation summary generation.

## What is validated

The automated suite currently covers:

1. Successful attribution generation after a kept ratchet cycle
2. Conservative behavior when no gate mapping is available
3. Rejection of non-`keep` ratchet states
4. Confidence downgrade when multiple concurrent changes are present
5. Ignoring retrospective traces in gate statistics
6. Component index aggregation across multiple attribution records
7. Real CLI invocation against temporary project and trace directories
8. Replay review queue generation for unreviewed attributions
9. Human review capture for attribution usefulness scoring
10. Validation summary generation and readiness gating

## Run the suite

From the repository root:

```bash
tools/flow-install/scripts/validate-attribute.sh
```

Or run the tests directly:

```bash
python3 -m pytest tools/flow-install/tests/test_attribute.py
```

Backfill missing attribution records once real improvement history exists:

```bash
python3 "tools/flow-install/skills/_shared/attribute.py" backfill --skill <skill-name>
```

## What the suite does not prove

The automated suite proves mechanical correctness and conservative behavior. It does **not** prove that attribution is decision-useful on real historical runs.

That still requires replay review against real kept ratchet cycles.

## Manual replay review

Use this checklist on real data before promoting later phases:

1. Pick a kept improvement cycle with known human context.
2. Run:

```bash
python3 "tools/flow-install/skills/_shared/attribute.py" compute --skill <skill-name> --json
```

3. Inspect:
   - `~/.agents/traces/<skill-name>/attributions.ndjson`
   - `~/.agents/traces/<skill-name>/component_index.json`
   - `~/.agents/traces/<skill-name>/validation_summary.json`

4. Score the output:
   - Legible
   - Plausible
   - Conservative
   - Useful for proposal ranking
   - Non-misleading

If the output is mechanically correct but not useful, stop and improve Phase 1 before building lessons or transfer logic.

## Replay review workflow

List attribution records that still need replay review:

```bash
python3 "tools/flow-install/skills/_shared/attribute_validate.py" queue --skill <skill-name>
```

Record a replay review:

```bash
python3 "tools/flow-install/skills/_shared/attribute_validate.py" review \
  --skill <skill-name> \
  --attribution-id <attr_id> \
  --legibility 4 \
  --plausibility 4 \
  --conservatism 5 \
  --usefulness 4 \
  --trustworthiness 4 \
  --notes "Good support for proposal ranking"
```

Generate the Phase 1.5 validation summary:

```bash
python3 "tools/flow-install/skills/_shared/attribute_validate.py" summary --skill <skill-name>
```

Generate a markdown replay packet for pending reviews:

```bash
python3 "tools/flow-install/skills/_shared/attribute_validate.py" packet --skill <skill-name>
```

The summary is intentionally conservative. It can mark Phase 1 as mechanically ready while still blocking promotion because human usefulness evidence is missing.
