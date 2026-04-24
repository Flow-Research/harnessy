# Shared Skill Candidate Packet

Use this template when proposing a repo-local skill for promotion into Harnessy shared skills.

## Summary

- skill name:
- source repo:
- source path: `.agents/skills/<skill-name>/`
- proposed shared path: `tools/flow-install/skills/<skill-name>/`
- proposed maintainer:

## Problem

What recurring problem does this skill solve?

## Local Proof

Describe the real downstream use case that proved this skill was worth promoting.

- project or repo:
- task or workflow:
- number of successful uses:

## Why This Should Be Shared

Explain why this belongs in Harnessy instead of staying project-local.

## Genericization Notes

List the project-specific assumptions removed or isolated before promotion.

- removed branding:
- removed repo-specific paths:
- removed domain-specific nouns:
- local wrapper retained after promotion: yes/no

## Validation Evidence

Run these in the source repo before proposing promotion:

```bash
pnpm skills:validate
pnpm skills:register
pnpm harness:verify
```

Paste a concise result summary here.

- `pnpm skills:validate`:
- `pnpm skills:register`:
- `pnpm harness:verify`:

## Governance Metadata

- owner:
- version:
- blast radius:
- permissions:
- data categories:
- egress:

## Adoption Plan

How should the source repo behave if the shared skill is accepted?

- delete local version
- keep thin local wrapper
- keep local extension on top of shared base

## Reviewer Notes

Anything the Harnessy maintainer should check closely during promotion.
