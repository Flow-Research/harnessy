# Skill Promotion Maintainer Playbook

This playbook defines how a maintainer promotes a skill from a Harnessy-installed project into Harnessy's shared skill set.

This is a Git-native maintainer workflow. The installed repo is the proving ground. Harnessy is the distribution layer.

## Use Case

Use this playbook when all of the following are true:

- you are working in a Harnessy-installed repo
- the skill currently lives in that repo's `.agents/skills/`
- the skill has proven useful locally
- you believe it should become a shared Harnessy skill under `tools/flow-install/skills/`

Example source repo:

```text
<repo-root>
```

Any Harnessy-installed repo can use this process.

## Core Principle

- installed repo = validate usefulness
- Harnessy repo = validate reusability and distribution

A skill should earn promotion by succeeding locally first, then being generalized cleanly into a shared Harnessy artifact.

## Promotion Lifecycle

CREATE/ITERATE IN INSTALLED REPO -> PROVE LOCAL VALUE -> GENERALIZE -> PROMOTE TO HARNESSY -> RE-VALIDATE IN HARNESSY -> ADOPT SHARED VERSION BACK IN INSTALLED REPO

## Phase 1: Prove the skill locally

The skill begins life in the installed repo:

```text
.agents/skills/<skill-name>/
```

Do not start in Harnessy core unless the work is obviously framework-owned from day one.

The local skill should be used in real project work until you are confident that:

- it solves a recurring problem
- the interface is stable enough to teach others
- the workflow is not a one-off temporary workaround
- the current implementation is not tightly coupled to one sprint or one emergency

## Phase 2: Validate in the installed repo

Before promotion, validate the skill using the installed repo's normal lifecycle.

Minimum commands:

```bash
pnpm skills:validate
pnpm skills:register
pnpm harness:verify
```

The goal is to prove:

- the skill is structurally valid
- metadata is complete enough for governance
- the skill registers correctly for the local user
- the installed repo still preserves Harnessy parity

If the skill fails here, it is not ready for promotion.

## Phase 3: Run the maintainer promotion review

Before copying anything into Harnessy, review the skill as a maintainer.

### Reusability checks

Ask:

1. Does this solve a problem likely to recur across Harnessy-installed repos?
2. Is the name generic enough for other teams and repos?
3. Are the docs written for strangers, not only the source project?
4. Would another maintainer understand when to use it without project-specific context?

### Coupling checks

Reject direct promotion if the skill depends on:

- project-specific folder structure
- project-specific entities or domain nouns
- team-internal slang
- temporary migration steps
- source-repo-only CI assumptions

### Governance checks

Confirm:

- owner is set
- blast radius is justified
- permissions are minimal
- egress is explicit
- data categories are explicit
- docs reference installed command paths correctly

If the skill is valuable but too coupled, do not discard it. Move to the split path in Phase 4.

## Phase 4: Decide the promotion outcome

There are only three valid outcomes.

### Outcome A: Keep local only

Choose this if the skill is useful but remains repo-specific.

### Outcome B: Promote as shared Harnessy skill

Choose this if the skill is already generic enough to be reused across Harnessy installs.

### Outcome C: Split into shared core plus local wrapper

Choose this if:

- the core capability is reusable
- but the current interface or docs still include source-repo assumptions

In that case:

- promote the reusable core into Harnessy
- leave a thin project-local wrapper or project-local guidance in the source repo

This is often the best option.

## Phase 5: Extract the reusable version

When promoting, do not blindly copy the local skill into Harnessy.

Instead:

1. remove source-repo branding and assumptions
2. rename commands or examples if needed
3. replace repo-specific examples with generic ones
4. keep only the reusable behavior in the shared version
5. leave project-specific guidance behind in the installed repo if still useful

The shared skill must feel native to Harnessy, not like a project-specific export.

## Phase 6: Promote into Harnessy

Once generalized, create the shared skill in:

```text
tools/flow-install/skills/<skill-name>/
```

Then update all required Harnessy-side references such as:

- skill metadata
- catalog entries if applicable
- shared docs if the new skill changes contributor or maintainer workflows

Promotion should happen on a Harnessy branch, separate from the original source-repo branch.

## Phase 7: Re-validate in Harnessy

After promotion, validate the skill in the Harnessy repo as a distributed artifact.

Minimum checks:

- Harnessy skill validation passes
- Harnessy registration behavior remains correct
- Harnessy parity remains correct
- the shared skill is visible and consistent across supported agent surfaces

This step matters because a skill can be valid in the source repo but still be a poor shared Harnessy artifact.

## Phase 8: Decide what to do in the source repo

After the Harnessy version exists, resolve the source repo intentionally.

Use one of these patterns:

### Pattern 1: Shared-only adoption

Delete the local skill and rely on the shared Harnessy version.

### Pattern 2: Thin local wrapper

Keep a local wrapper that points maintainers toward the shared Harnessy capability while preserving small repo-specific guidance.

### Pattern 3: Local extension

Keep the shared Harnessy skill as the reusable base and leave extra repo-specific behavior in the local version.

Do not keep two divergent full implementations without a conscious reason.

## Git Workflow Recommendation

Use three logical branches when needed.

### 1. Source repo branch

Purpose: prove and stabilize the local skill.

### 2. Harnessy promotion branch

Purpose: productize and generalize the shared Harnessy version.

### 3. Source repo cleanup branch

Purpose: switch the source repo to the shared version, wrapper, or extension model.

This separation makes the history clean:

- source repo proves value
- Harnessy branch packages the abstraction
- source repo cleanup adopts the promoted result

## Promotion Checklist

Use this before opening the Harnessy promotion PR.

- [ ] Skill has been used successfully in real source-repo work
- [ ] Local validation passes in the source repo
- [ ] Name is generic enough for other Harnessy installs
- [ ] Docs are understandable outside the source repo
- [ ] Source-repo assumptions have been removed or isolated
- [ ] Blast radius, permissions, egress, and data categories are complete
- [ ] I have decided whether this is keep-local, shared, or shared-core-plus-wrapper
- [ ] Harnessy shared version has a clear maintainer

## Review Checklist for Harnessy promotion PRs

Reviewers should ask:

1. Is this really cross-project, or is it just high-quality local tooling?
2. What specific source-repo assumptions were removed during extraction?
3. Should this stay shared-only, or should the source repo keep a wrapper?
4. Does the skill fit Harnessy naming and governance conventions?
5. Will it preserve registration and harness parity once distributed?

## What should usually stay local

These are usually not promotion candidates:

- project-specific migration helpers
- domain-specific admin workflows
- tightly coupled CI or deployment commands for one repo
- skills that depend on one monorepo's folder structure
- one-team process wrappers that do not generalize

## Strong promotion candidates

These are often good shared candidates:

- reusable local-run workflows
- CI triage and rerun helpers
- browser QA workflows
- issue/PR hygiene helpers
- reusable spec or validation orchestration
- skills that improve maintainer operations across many repos

## Acceptance Criteria

The promotion process is considered successful when:

1. the skill was proven locally before promotion
2. the Harnessy version is meaningfully more generic than the source-repo version
3. shared Harnessy validation and parity still pass
4. the source repo has a clear post-promotion adoption plan
5. future maintainers can tell where the shared abstraction came from and why it was promoted

## One-line rule

A skill is promoted from an installed repo to Harnessy only after it has been validated locally, generalized to remove source-repo assumptions, and re-validated in Harnessy as a shared distributed artifact.
