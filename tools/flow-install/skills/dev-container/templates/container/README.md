# Dev Container Bundle

This directory is a portable Docker-based development container bundle. It can live outside the inspected repo and be reused from anywhere.

## Layout

```text
<bundle-root>/
  Dockerfile
  README.md
  baseline/apk.txt
  baseline/apt.txt
  baseline/npm.txt
  baseline/pip.txt
  features/<feature>/apk.txt
  features/<feature>/apt.txt
  specs/dev-baseline.json
  scripts/install-system-packages.sh
  scripts/installers/apk.sh
  scripts/installers/apt.sh
  scripts/build-image.sh
  scripts/run-container.sh
  scripts/run-validation.sh
  scripts/validate-container.py
```

## Concepts

- `baseline/<package-manager>.txt` holds always-on system packages for the chosen package manager.
- `baseline/npm.txt` holds global Node CLI packages installed during image build.
- `baseline/pip.txt` holds global Python CLI packages installed during image build.
- `features/<feature>/<package-manager>.txt` holds optional package bundles such as `rust`, `docker`, or `postgres`.
- `specs/dev-baseline.json` is the machine-readable validation contract.
- `scripts/validate-container.py` runs inside the container and checks actual state against the spec.
- `scripts/run-validation.sh` is the host wrapper that builds the image if needed and executes the validator inside the container.
- Source repos are mounted only when you pass a source path explicitly.

## Default Placement

Recommended default output is outside the source repo, for example:

```text
~/containers/<repo-slug>/dev-baseline/
```

## Typical Workflow

```bash
./scripts/build-image.sh
./scripts/run-container.sh ./specs/dev-baseline.json /path/to/source-repo
./scripts/run-validation.sh ./specs/dev-baseline.json /path/to/source-repo
```

If you are already inside the bundle root, the spec argument can be omitted.

## Updating the Baseline

1. Edit the correct baseline or feature manifest for the selected package manager.
2. Add or update checks in `specs/dev-baseline.json`.
3. Rebuild and run validation.

## Adding Feature Packs

Create a new directory like `features/go/` and add package-manager-specific files such as `apk.txt` and `apt.txt`. Then add the feature name to `build.feature_packs` in the spec.

## Validation Rule

Do not treat the container baseline as correct until `scripts/run-validation.sh` passes.
