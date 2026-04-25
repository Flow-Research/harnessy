// Skill registry interface.
//
// A registry exposes versioned skills as a list of {name, version, manifest}
// records, and resolves a (name, version) pair to a local filesystem path
// containing that skill's files. The installer copies from that path the same
// way regardless of whether the skill came from disk, a git remote, or
// Cloudflare Artifacts.

export const REGISTRY_NAMESPACE = "flow";

export const formatRef = (name, version) => `${REGISTRY_NAMESPACE}/${name}@${version}`;

export const parseRef = (ref) => {
  const match = /^([^/]+)\/([^@]+)@(.+)$/.exec(ref);
  if (!match) throw new Error(`Invalid skill ref: ${ref}`);
  const [, namespace, name, version] = match;
  return { namespace, name, version };
};

// Marker base class — backends extend this. We don't enforce method signatures
// at runtime; consumers just call list() and fetch() and trust the backend.
export class Registry {
  // async list() -> [{ name, version, manifest }]
  async list() {
    throw new Error("Registry.list() not implemented");
  }

  // async fetch(name, version) -> { dir, sha? }
  // dir: absolute path on local fs containing SKILL.md, manifest.yaml, etc.
  // sha: optional content hash for verification (used by remote backends).
  async fetch(_name, _version) {
    throw new Error("Registry.fetch() not implemented");
  }
}
