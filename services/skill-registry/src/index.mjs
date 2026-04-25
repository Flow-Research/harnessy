// harnessy-skill-registry
//
// Cloudflare Worker that provisions per-skill Git repos in Cloudflare Artifacts
// and mints scoped access tokens. Used by the Harnessy installer to publish and
// fetch versioned skills.
//
// API:
//   POST /skills/:name              -> { name, remote, writeToken, ttl }
//   POST /skills/:name/tokens       -> { token, access, ttl }   body: {access, ttlSeconds?}
//
// Auth: bearer token, must equal env.PUBLISH_TOKEN. Constant-time compared.
//
// RECONCILE markers point to assumptions about the Cloudflare Artifacts SDK
// surface that need to be verified against current docs.

const SKILL_NAME_RE = /^[a-z0-9][a-z0-9-]{0,62}$/;
const DEFAULT_READ_TTL = 60 * 60 * 24;          // 24h
const DEFAULT_WRITE_TTL = 60 * 60;              // 1h
const MAX_TTL = 60 * 60 * 24 * 30;              // 30d

const json = (status, body) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
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

// RECONCILE: env.ARTIFACTS.create() — assumed idempotent and returning
// { remote, token, repo }. If the actual SDK throws on existing names, wrap
// in try/catch and fall back to env.ARTIFACTS.get(name).
const createOrGetRepo = async (env, name) => {
  return env.ARTIFACTS.create(name);
};

// RECONCILE: repo.createToken(access, ttlSeconds) — assumed signature.
const mintToken = async (repo, access, ttl) => {
  return repo.createToken(access, ttl);
};

const handleCreateSkill = async (request, env, name) => {
  const ttl = DEFAULT_WRITE_TTL;
  const { remote, token, repo } = await createOrGetRepo(env, name);
  // Some SDKs return the create-time token; if not, mint one explicitly.
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

const route = async (request, env) => {
  const url = new URL(request.url);
  const parts = url.pathname.split("/").filter(Boolean);

  if (parts[0] !== "skills") return null;
  const name = parts[1];
  const nameError = validateSkillName(name);
  if (nameError) return json(400, { error: nameError });

  if (parts.length === 2 && request.method === "POST") {
    return handleCreateSkill(request, env, name);
  }
  if (parts.length === 3 && parts[2] === "tokens" && request.method === "POST") {
    return handleMintToken(request, env, name);
  }
  return null;
};

export default {
  async fetch(request, env) {
    if (!authorize(request, env)) {
      return json(401, { error: "Unauthorized" });
    }
    try {
      const response = await route(request, env);
      return response || json(404, { error: "Not found" });
    } catch (error) {
      return json(500, { error: error?.message || "Internal error" });
    }
  },
};
