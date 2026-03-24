---
name: dev-container
description: Build a reusable Docker development container baseline with spec-driven validation across Alpine, Debian, Ubuntu, or compatible custom images. Use when a repo needs a configurable dev container, layered tool installs, and a way to verify container state.
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, ApplyPatch, Bash, Question
argument-hint: "[scaffold|validate|update] [target-dir]"
---

# Dev Container

## Purpose

Scaffold and maintain a reusable Docker development container with:

- a baseline package manifest
- optional feature packs
- host-side build and validation wrappers
- an in-container validator driven by a machine-readable spec
- an interactive intake flow so the container can be tailored to the repo and the user's needs

## Inputs

- optional mode: `scaffold`, `validate`, or `update`
- optional source directory to inspect; default is the current working directory
- optional output directory for the generated bundle; default is `~/containers/<repo-slug>/<container-name>/`

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/dev-container/`.

## Steps

1. Follow the command specification in `${AGENTS_SKILLS_ROOT}/dev-container/commands/dev-container.md`.
2. Use `${AGENTS_SKILLS_ROOT}/dev-container/scripts/scaffold.py` to copy the container bundle into the chosen bundle root when scaffolding.
3. Use `${AGENTS_SKILLS_ROOT}/dev-container/scripts/recommend_features.py` to infer feature-pack and base-image recommendations from the inspected source repo before editing the spec.
4. Ask the user targeted setup questions before scaffolding or materially changing the baseline:
   - source repo or working directory to inspect
   - output location for the bundle, defaulting outside the repo under `~/containers/<repo-slug>/<container-name>/`
   - a sensible container bundle name derived from repo context when the user does not specify one
   - base image family (`alpine`, `debian`, `ubuntu`, or `custom`)
   - exact base image tag
   - package manager (`apk` or `apt` for v1)
   - required baseline tools and CLIs
   - optional feature packs
   - whether `sudo` is required
   - repo-specific validation commands
5. Keep the determinism split explicit:
   - declarative state lives in `<bundle-root>/baseline/`, `<bundle-root>/features/`, and `<bundle-root>/specs/`
   - repeatable execution lives in `<bundle-root>/scripts/`
   - repo-specific reasoning and adaptation happen in the agent workflow
6. Do not claim the container baseline works until `<bundle-root>/scripts/run-validation.sh` succeeds or the failure is explicitly reported.

## Output

- portable bundle root with Dockerfile, package manifests, feature packs, validation spec, and scripts
- updated spec or feature-pack configuration based on repo context and user-requested tools
- validation evidence from the host wrapper and in-container validator
