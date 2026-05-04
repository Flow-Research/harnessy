// harnessy-skill-registry
//
// Cloudflare Worker that provisions per-skill Git repos in Cloudflare Artifacts,
// records published-skill metadata in a KV-backed lockfile, mints scoped access
// tokens, and serves the public lockfile so consumers can install skills
// without ever cloning the publisher's source repo.
//
// API:
//   Authed (requires Bearer env.PUBLISH_TOKEN):
//     POST /skills/:name              -> { name, remote, writeToken, ttl }
//     POST /skills/:name/tokens       -> { token, access, ttl }
//     POST /skills/:name/publish      -> { name, ok }   (records lockfile entry)
//
//   Public (no auth):
//     GET  /lockfile                  -> canonical lockfile JSON
//     GET  /skills/:name              -> single skill entry, or 404
//
// RECONCILE markers point to assumptions about the Cloudflare Artifacts SDK
// surface that need to be verified against current docs.

const SKILL_NAME_RE = /^[a-z0-9][a-z0-9-]{0,62}$/;
const DEFAULT_READ_TTL = 60 * 60 * 24;          // 24h
const DEFAULT_WRITE_TTL = 60 * 60;              // 1h
const MAX_TTL = 60 * 60 * 24 * 30;              // 30d
const KV_PREFIX = "skill:";
const LOCKFILE_VERSION = 1;
const REGISTRY_NAMESPACE = "flow";
const REQUIRED_PUBLISH_FIELDS = ["version", "sha", "remote", "treeHash", "files"];

const json = (status, body, extraHeaders = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...extraHeaders },
  });

const constantTimeEqual = (a, b) => {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
};

const authorize = (request, env) => {
  const header = request.headers.get("authorization") || "";
  const presented = header.startsWith("Bearer ") ? header.slice(7) : "";
  return env.PUBLISH_TOKEN && constantTimeEqual(presented, env.PUBLISH_TOKEN);
};

const validateSkillName = (name) => {
  if (!name || !SKILL_NAME_RE.test(name)) {
    return "Skill name must match /^[a-z0-9][a-z0-9-]{0,62}$/";
  }
  return null;
};

const clampTtl = (requested, fallback) => {
  if (typeof requested !== "number" || !Number.isFinite(requested) || requested <= 0) {
    return fallback;
  }
  return Math.min(Math.floor(requested), MAX_TTL);
};

// RECONCILE: env.ARTIFACTS.create() — assumed idempotent, returns
// { remote, token, repo }. Wrap in try/catch for the alternative shape later.
const createOrGetRepo = async (env, name) => env.ARTIFACTS.create(name);

// RECONCILE: repo.createToken(access, ttlSeconds) — assumed signature.
const mintToken = async (repo, access, ttl) => repo.createToken(access, ttl);

const handleCreateSkill = async (request, env, name) => {
  const ttl = DEFAULT_WRITE_TTL;
  const { remote, token, repo } = await createOrGetRepo(env, name);
  const writeToken = token || (await mintToken(repo, "write", ttl));
  return json(200, { name, remote, writeToken, ttl });
};

const handleMintToken = async (request, env, name) => {
  let body = {};
  try {
    body = await request.json();
  } catch {
    return json(400, { error: "Invalid JSON body" });
  }

  const access = body.access === "write" ? "write" : "read";
  const fallback = access === "write" ? DEFAULT_WRITE_TTL : DEFAULT_READ_TTL;
  const ttl = clampTtl(body.ttlSeconds, fallback);

  const { repo } = await createOrGetRepo(env, name);
  const token = await mintToken(repo, access, ttl);
  return json(200, { token, access, ttl });
};

const handleRecordPublish = async (request, env, name) => {
  if (!env.LOCKFILE_KV) {
    return json(500, { error: "LOCKFILE_KV binding not configured" });
  }

  let body = {};
  try {
    body = await request.json();
  } catch {
    return json(400, { error: "Invalid JSON body" });
  }

  for (const field of REQUIRED_PUBLISH_FIELDS) {
    if (body[field] === undefined || body[field] === null) {
      return json(400, { error: `Missing required field: ${field}` });
    }
  }

  const entry = {
    version: body.version,
    sha: body.sha,
    remote: body.remote,
    treeHash: body.treeHash,
    files: body.files,
    registry: "artifacts",
    publishedAt: new Date().toISOString(),
  };
  await env.LOCKFILE_KV.put(`${KV_PREFIX}${name}`, JSON.stringify(entry));
  return json(200, { name, ok: true });
};

const handleGetLockfile = async (request, env) => {
  if (!env.LOCKFILE_KV) {
    return json(500, { error: "LOCKFILE_KV binding not configured" });
  }
  const { keys } = await env.LOCKFILE_KV.list({ prefix: KV_PREFIX });
  const skills = {};
  for (const { name: key } of keys) {
    const skillName = key.slice(KV_PREFIX.length);
    const entry = await env.LOCKFILE_KV.get(key, "json");
    if (entry) skills[skillName] = entry;
  }
  return json(200, {
    version: LOCKFILE_VERSION,
    namespace: REGISTRY_NAMESPACE,
    skills,
  }, { "cache-control": "public, max-age=60" });
};

const handleGetSkill = async (request, env, name) => {
  if (!env.LOCKFILE_KV) {
    return json(500, { error: "LOCKFILE_KV binding not configured" });
  }
  const entry = await env.LOCKFILE_KV.get(`${KV_PREFIX}${name}`, "json");
  if (!entry) return json(404, { error: "Skill not found" });
  return json(200, entry, { "cache-control": "public, max-age=60" });
};

const route = async (request, env) => {
  const url = new URL(request.url);
  const parts = url.pathname.split("/").filter(Boolean);
  const method = request.method;

  // Public routes — no auth required.
  if (parts.length === 1 && parts[0] === "lockfile" && method === "GET") {
    return handleGetLockfile(request, env);
  }
  if (parts.length === 2 && parts[0] === "skills" && method === "GET") {
    const nameError = validateSkillName(parts[1]);
    if (nameError) return json(400, { error: nameError });
    return handleGetSkill(request, env, parts[1]);
  }

  // Authed routes — require Bearer PUBLISH_TOKEN.
  if (parts[0] === "skills" && (method === "POST")) {
    if (!authorize(request, env)) return json(401, { error: "Unauthorized" });
    const name = parts[1];
    const nameError = validateSkillName(name);
    if (nameError) return json(400, { error: nameError });

    if (parts.length === 2) return handleCreateSkill(request, env, name);
    if (parts.length === 3 && parts[2] === "tokens") return handleMintToken(request, env, name);
    if (parts.length === 3 && parts[2] === "publish") return handleRecordPublish(request, env, name);
  }

  return null;
};

export default {
  async fetch(request, env) {
    try {
      const response = await route(request, env);
      return response || json(404, { error: "Not found" });
    } catch (error) {
      return json(500, { error: error?.message || "Internal error" });
    }
  },
};
