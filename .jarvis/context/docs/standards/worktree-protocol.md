# Harnessy Worktree Protocol

## Purpose

This document defines the canonical filesystem layout and operating rules for
Harnessy-managed project repositories stored under the gitignored `projects/`
folder.

This protocol is not specific to `issue-flow`. It is the base workspace model
for how Harnessy manages active projects, integration checkouts, and branch
isolated worktrees.

## Canonical Layout

Each managed project uses a project container layout:

```text
projects/
  <project-name>/
    dev/
    worktrees/
      <worktree-dir>/
      <worktree-dir>/
```

Example:

```text
projects/
  garden/
    dev/
    worktrees/
      feat-auth-redirect/
      fix-ci-timeouts/
  accelerate-africa/
    dev/
    worktrees/
      117-program-team-investment/
```

### Meaning Of Each Directory

| Path | Role |
|------|------|
| `projects/<project-name>/` | Gitignored container directory for one managed project |
| `projects/<project-name>/dev/` | Canonical integration checkout for the project |
| `projects/<project-name>/worktrees/` | Parent directory containing all non-canonical linked worktrees |
| `projects/<project-name>/worktrees/<worktree-dir>/` | Branch-isolated working directory for one active worktree |

## Branch Model

- `dev` is the canonical integration branch for Harnessy-managed projects.
- `main` is the protected production or release branch unless a project defines a different release model locally.
- The canonical checkout at `projects/<project-name>/dev/` should normally be attached to the `dev` branch.
- New worktrees should normally branch from `dev` unless an explicit project-local override says otherwise.

If a project does not yet have a `dev` branch on the remote, the project must be
migrated intentionally. Temporary fallbacks may exist during migration, but the
target standard remains `dev`.

## Naming Rules

### Project container

- The project container directory must be named after the repository or product.
- Do not use ad hoc feature folders as project containers.

### Canonical checkout

- The canonical integration checkout directory must be named exactly `dev`.
- `dev/` is a checkout name and a branch intent marker. It represents the
  canonical integration workspace, not an arbitrary local folder.

### Worktree root

- The worktree parent directory must be named exactly `worktrees`.
- Do not use `.worktrees/`, `<project-name>-worktrees/`, or other alternate
  names for new Harnessy-managed projects.

### Worktree directories

- Each worktree directory should be derived from the branch name.
- Unsafe characters must be sanitized for filesystem portability.
- Lowercase branch-derived directory names by default.
- Replace whitespace and path separators with `-`.

Examples:

| Branch | Worktree directory |
|------|------|
| `117_program-team-investment` | `117-program-team-investment` |
| `feat/test-infra-ci` | `feat-test-infra-ci` |
| `fix/auth redirect` | `fix-auth-redirect` |

## Operating Rules

### 1. The project container is not a checkout

Use `projects/<project-name>/` only as the container that holds the canonical
checkout and the worktree directories.

Do not treat the project container itself as a Git repository.

### 2. `dev/` is for integration and coordination

Use `projects/<project-name>/dev/` for:

- pulling the latest `dev`
- repo-wide maintenance meant for the integration branch
- creating, listing, pruning, or removing worktrees
- reading canonical project context
- validating integration state before or after worktree creation

Do not use `dev/` as the active implementation workspace for a feature branch
once a dedicated worktree exists.

### 3. Branch work happens in `worktrees/`

Use `projects/<project-name>/worktrees/<worktree-dir>/` for:

- implementation work on non-`dev` branches
- QA or reproduction work on branch-local state
- code review follow-up on an isolated branch
- CI fix work tied to a non-canonical branch
- parallel work that must not disturb `dev/`

Once a worktree is created for a branch, all file writes for that branch should
happen inside that worktree.

### 4. One branch, one worktree

- A branch should map to one active worktree path.
- Do not attach the same branch to multiple worktree directories for the same
  project unless there is an explicit operational reason.
- If a branch already has an attached worktree, reuse it.

### 5. Keep canonical and branch work distinct

- `dev/` is the integration workspace.
- `worktrees/<worktree-dir>/` is the branch workspace.
- Do not treat them as interchangeable.
- Do not perform feature work directly in `dev/` when the branch should have its
  own worktree.

### 6. Keep tracked state portable

- Tracked state files must not depend on machine-specific absolute paths.
- Store portable metadata such as project name, branch name, worktree dirname,
  and strategy version.
- Prefer project-container-relative references such as `dev` or
  `worktrees/<worktree-dir>`.
- If legacy state includes absolute paths or old sibling-root assumptions, treat
  that as migration debt.

## Navigation Standard

### Enter the canonical checkout

```bash
cd "projects/<project-name>/dev"
```

### Move from `dev/` to a branch worktree

```bash
cd "projects/<project-name>/dev"
git worktree list
cd "../worktrees/<worktree-dir>"
```

### Move from a worktree back to `dev/`

```bash
cd "../../dev"
```

### Inspect all active worktrees for a project

Run from `projects/<project-name>/dev/`:

```bash
git worktree list --porcelain
```

### Inspect the project container structure

Run from `projects/<project-name>/`:

```bash
ls
```

Expected entries:

- `dev`
- `worktrees`

## Interaction Standard

### Creating a new worktree

1. Start from `projects/<project-name>/dev/`.
2. Pull the latest `dev`.
3. Create or reuse the worktree under `../worktrees/<worktree-dir>/`.
4. Perform branch-local work only inside that worktree.

### Syncing a project

- Sync `dev/` against `dev`.
- Sync a worktree branch against its declared base branch.
- Do not assume syncing a worktree also syncs `dev/`.
- Do not assume syncing `dev/` updates existing worktree branches.

### Finishing work

- Keep the worktree through PR review and acceptance by default.
- Remove the worktree only after the branch is no longer needed.
- Cleanup should happen from `dev/` using `git worktree remove`.

## Guardrails

- Verify the current path and branch before editing or committing.
- Never commit from `dev/` when the change belongs to a feature worktree.
- Never create alternate worktree naming conventions per project when the
  project-container layout already applies.
- Never treat `main` as the default active branch for Harnessy-managed project
  work unless a deeper project-local standard explicitly overrides the model.
- Never use the term "subtree" to mean Git subtree integration. In this
  protocol, worktrees are stored as child directories under `worktrees/`.

## Migration Guidance

A project is non-compliant when any of the following are true:

- the project does not have a dedicated container under `projects/`
- the canonical integration checkout is not located at `projects/<project-name>/dev/`
- worktrees do not live under `projects/<project-name>/worktrees/`
- branch work is happening directly in `dev/`
- multiple layout conventions exist for the same project
- tracked state relies on absolute paths or old sibling-root assumptions

Migration target:

1. Keep or create `projects/<project-name>/` as the gitignored project container.
2. Keep or create `projects/<project-name>/dev/` as the canonical `dev` checkout.
3. Keep or create `projects/<project-name>/worktrees/` as the only worktree parent directory.
4. Move active branch work into `worktrees/<worktree-dir>/`.
5. Normalize default base branch expectations to `dev`.
6. Remove obsolete sibling-root conventions once the container layout is active.

## Applies To

This protocol is the source of truth for:

- shared Harnessy context docs
- future Harnessy project onboarding under `projects/`
- worktree-aware Harnessy tooling and skills
- navigation and interaction guidance for any agent working in the gitignored
  project workspace
