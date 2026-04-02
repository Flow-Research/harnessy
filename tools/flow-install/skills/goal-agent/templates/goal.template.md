<!-- Store this file at ~/.agents/goals/YYYY/Mon/dd-<name>.md -->
<!-- Example: ~/.agents/goals/2026/Apr/02-my-feature.md -->

# Goal: <title>

## Objective

<Clear, specific description of what needs to be achieved.
The orchestrator will read this and decompose it into phases.
Be concrete about what "done" looks like.>

## Working Directory

<path — default: current directory>

## Constraints

- Max iterations: 10
- Budget per phase: $2.00
- Total budget: $10.00
- Model: sonnet
- Allowed tools: Bash, Read, Write, Edit, Glob, Grep

## Verification

<How to objectively check if the goal is achieved.
These commands must return exit code 0 on success.>

### Commands

```bash
# Example verification commands:
npm test                              # All tests pass
test -f src/feature.ts                # File exists
grep "export" src/feature.ts          # Contains expected content
```

### File Checks

- [ ] `src/feature.ts` exists
- [ ] `tests/feature.test.ts` exists

## Context

<Background info, relevant architecture, existing code to build on.
Include file paths, technology choices, and conventions.>

## Approach Hints (optional)

<If you have opinions on how this should be done, include them.
The orchestrator uses these as guidance, not strict instructions.>
