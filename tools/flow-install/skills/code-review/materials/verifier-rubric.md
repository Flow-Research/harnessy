# Verifier Rubric

The verifier is adversarial and narrower than the reviewer. Its job is to remove unsupported findings and enforce the capability contract.

## Checks

- Every `critical` or `major` finding cites a concrete changed file and line, or a directly relevant unchanged file that explains why the changed code is unsafe.
- Every `test_gap` finding names the behavior that changed and the test surface that should catch it.
- Every requirement-compliance finding references the spec, issue, PR description, or command behavior that establishes the requirement.
- Severity matches the taxonomy and is not inflated.
- The verdict follows the severity policy exactly.
- The finding describes a real merge risk, not a preference.
- The review does not rely on untrusted external content or undocumented assumptions.
- The output validates against `contracts/output.schema.json`.

## Required Verifier Actions

- Remove unsupported findings.
- Downgrade vague, speculative, or preference-only findings.
- Require the reviewer to add missing file/line evidence for blocking findings.
- Reject a final `approve` verdict when risky behavior changed without adequate test evidence.
- Reject `request_changes` when no `critical` or `major` finding remains.
