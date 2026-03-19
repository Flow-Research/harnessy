---
name: git-commit
description: "Interactive git commit flow with branch selection and contextual commit messages."
disable-model-invocation: true
allowed-tools: Bash, Question
argument-hint: "[--branch current|new] [--name <branch-name>]"
---

# Git Commit

## Purpose
Create a local git commit through a guided branch-selection flow that always shows the current branch, optionally creates or switches to a new branch, generates a contextual commit message, and commits all repository changes safely.

## Inputs
- Optional flags: `--branch current|new`, `--name <branch-name>`

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/git-commit/`.

## Steps
1. Follow the command specification in `${AGENTS_SKILLS_ROOT}/git-commit/commands/git-commit.md` exactly.
2. Use `${AGENTS_SKILLS_ROOT}/git-commit/scripts/git-commit.js inspect` before asking any questions.
   - Read the current branch, detached-head state, protected-branch status, change counts, and suggested branch name from the JSON output.
3. If the user did not explicitly choose a branch mode with arguments, ask a single branch-selection question.
   - Show the current branch in the option label.
   - Recommended option: keep the current branch when it is not protected.
   - Recommended option: create a new branch when the current branch is `main` or `dev`.
4. If the user chooses a new branch and did not already provide `--name`, ask for the new branch name.
   - Show the script-provided `suggestedBranchName` as the recommended default.
   - Require a valid git branch name; if invalid, stop and explain the expected format.
5. Before committing, protect against obvious secret commits.
   - If any staged or unstaged path matches `.env`, `.env.*`, `*.pem`, `*.key`, `credentials.json`, or `secrets.*`, stop and warn instead of committing automatically.
6. Use `${AGENTS_SKILLS_ROOT}/git-commit/scripts/git-commit.js commit` as the deterministic executor.
   - It must switch or create the selected branch, run `git add -A`, generate the commit subject/body from staged changes, and create the commit.
   - It must return structured JSON with the selected branch, generated message, commit hash, and whether a branch was created.
7. If the commit fails because a hook changes files, re-run `${AGENTS_SKILLS_ROOT}/git-commit/scripts/git-commit.js commit` to create a new commit with the updated staged state.
   - Do not amend unless the user explicitly asks.
8. Return a concise summary with the selected branch, whether it was current/new, the generated commit message, and final git status.

## Output
- Selected branch and whether the skill stayed on the current branch or created/switched to another branch.
- Generated commit subject and body summary grounded in the actual staged changes.
- Commit hash and final working-tree status, or a plain-language reason the commit was blocked.
