import { test } from "node:test";
import assert from "node:assert/strict";

import worker from "../src/index.mjs";

const TOKEN = "test-publish-token";

const makeKV = (initial = {}) => {
  const store = new Map(Object.entries(initial));
  return {
    store,
    async get(key, opts) {
      const value = store.get(key);
      if (value === undefined) return null;
      if (opts === "json" || opts?.type === "json") return JSON.parse(value);
      return value;
    },
    async put(key, value) {
      store.set(key, typeof value === "string" ? value : JSON.stringify(value));
    },
    async list({ prefix } = {}) {
      const keys = Array.from(store.keys())
        .filter((k) => !prefix || k.startsWith(prefix))
        .sort()
        .map((name) => ({ name }));
      return { keys, list_complete: true };
    },
  };
};

const makeEnv = (overrides = {}) => {
  const calls = { create: [], createToken: [] };
  const env = {
    PUBLISH_TOKEN: TOKEN,
    LOCKFILE_KV: makeKV(overrides.kvSeed || {}),
    ARTIFACTS: {
      create: async (name) => {
        calls.create.push(name);
        return {
          remote: `https://artifacts.example/${name}.git`,
          token: "create-time-write-token",
          repo: {
            createToken: async (access, ttl) => {
              calls.createToken.push({ access, ttl });
              return `mock-${access}-${ttl}`;
            },
          },
        };
      },
      ...overrides.ARTIFACTS,
    },
    ...overrides,
  };
  delete env.kvSeed;
  env.__calls = calls;
  return env;
};

const req = (path, { method = "GET", auth = `Bearer ${TOKEN}`, body, headers } = {}) =>
  new Request(`https://x.test${path}`, {
    method,
    headers: {
      ...(auth ? { authorization: auth } : {}),
      "content-type": "application/json",
      ...headers,
    },
    body,
  });

const callJson = async (env, request) => {
  const res = await worker.fetch(request, env);
  const text = await res.text();
  let parsed = null;
  try { parsed = JSON.parse(text); } catch {}
  return { status: res.status, body: parsed, raw: text };
};

test("rejects requests with no Authorization header", async () => {
  const env = makeEnv();
  const { status, body } = await callJson(env, req("/skills/foo", { method: "POST", auth: null }));
  assert.equal(status, 401);
  assert.equal(body.error, "Unauthorized");
});

test("rejects requests with malformed Authorization header", async () => {
  const env = makeEnv();
  const { status } = await callJson(env, req("/skills/foo", { method: "POST", auth: "Basic abc" }));
  assert.equal(status, 401);
});

test("rejects requests with wrong bearer token", async () => {
  const env = makeEnv();
  const { status } = await callJson(env, req("/skills/foo", { method: "POST", auth: "Bearer nope" }));
  assert.equal(status, 401);
});

test("rejects skill names that violate /^[a-z0-9][a-z0-9-]{0,62}$/", async () => {
  const env = makeEnv();
  for (const bad of ["UPPER", "_under", "-leading", "with space", "a".repeat(64), ""]) {
    const { status, body } = await callJson(env, req(`/skills/${encodeURIComponent(bad)}`, { method: "POST" }));
    assert.equal(status, 400, `expected 400 for name "${bad}"`);
    assert.match(body.error, /Skill name/);
  }
});

test("POST /skills/:name creates the repo and returns remote + write token", async () => {
  const env = makeEnv();
  const { status, body } = await callJson(env, req("/skills/issue-flow", { method: "POST" }));
  assert.equal(status, 200);
  assert.equal(body.name, "issue-flow");
  assert.equal(body.remote, "https://artifacts.example/issue-flow.git");
  assert.equal(body.writeToken, "create-time-write-token");
  assert.equal(typeof body.ttl, "number");
  assert.deepEqual(env.__calls.create, ["issue-flow"]);
});

test("POST /skills/:name mints a write token explicitly when create returns no token", async () => {
  const env = makeEnv({
    ARTIFACTS: {
      create: async (name) => ({
        remote: `https://artifacts.example/${name}.git`,
        token: null,
        repo: { createToken: async (access, ttl) => `mock-${access}-${ttl}` },
      }),
    },
  });
  const { status, body } = await callJson(env, req("/skills/foo", { method: "POST" }));
  assert.equal(status, 200);
  assert.equal(body.writeToken, `mock-write-${body.ttl}`);
});

test("POST /skills/:name/tokens defaults to read access with 24h TTL", async () => {
  const env = makeEnv();
  const { status, body } = await callJson(
    env,
    req("/skills/foo/tokens", { method: "POST", body: JSON.stringify({}) }),
  );
  assert.equal(status, 200);
  assert.equal(body.access, "read");
  assert.equal(body.ttl, 60 * 60 * 24);
  assert.equal(body.token, `mock-read-${body.ttl}`);
});

test("POST /skills/:name/tokens honors access=write and custom ttlSeconds", async () => {
  const env = makeEnv();
  const { status, body } = await callJson(
    env,
    req("/skills/foo/tokens", {
      method: "POST",
      body: JSON.stringify({ access: "write", ttlSeconds: 600 }),
    }),
  );
  assert.equal(status, 200);
  assert.equal(body.access, "write");
  assert.equal(body.ttl, 600);
});

test("POST /skills/:name/tokens clamps ttlSeconds above the 30d ceiling", async () => {
  const env = makeEnv();
  const oneYear = 60 * 60 * 24 * 365;
  const { body } = await callJson(
    env,
    req("/skills/foo/tokens", { method: "POST", body: JSON.stringify({ ttlSeconds: oneYear }) }),
  );
  assert.equal(body.ttl, 60 * 60 * 24 * 30);
});

test("POST /skills/:name/tokens falls back to default ttl when ttlSeconds is invalid", async () => {
  const env = makeEnv();
  for (const bad of [-1, 0, "abc", null]) {
    const { body } = await callJson(
      env,
      req("/skills/foo/tokens", {
        method: "POST",
        body: JSON.stringify({ access: "read", ttlSeconds: bad }),
      }),
    );
    assert.equal(body.ttl, 60 * 60 * 24, `expected default TTL for ttlSeconds=${bad}`);
  }
});

test("POST /skills/:name/tokens returns 400 on malformed JSON body", async () => {
  const env = makeEnv();
  const { status, body } = await callJson(
    env,
    req("/skills/foo/tokens", { method: "POST", body: "not-json{" }),
  );
  assert.equal(status, 400);
  assert.match(body.error, /Invalid JSON/);
});

test("returns 404 for unknown route", async () => {
  const env = makeEnv();
  const { status } = await callJson(env, req("/nope"));
  assert.equal(status, 404);
});

test("returns 404 for wrong method on a known path", async () => {
  const env = makeEnv();
  const { status } = await callJson(env, req("/skills/foo", { method: "GET" }));
  assert.equal(status, 404);
});

// ── Phase 6A: lockfile endpoints ────────────────────────────────────────────

const validPublishEntry = {
  version: "1.2.3",
  sha: "a".repeat(40),
  remote: "https://artifacts.example/foo.git",
  treeHash: "f".repeat(64),
  files: [{ path: "SKILL.md", sha256: "b".repeat(64) }],
};

test("POST /skills/:name/publish requires bearer auth", async () => {
  const env = makeEnv();
  const { status } = await callJson(
    env,
    req("/skills/foo/publish", {
      method: "POST", auth: null, body: JSON.stringify(validPublishEntry),
    }),
  );
  assert.equal(status, 401);
});

test("POST /skills/:name/publish stores the entry in KV under key skill:<name>", async () => {
  const env = makeEnv();
  const { status, body } = await callJson(
    env,
    req("/skills/foo/publish", { method: "POST", body: JSON.stringify(validPublishEntry) }),
  );
  assert.equal(status, 200);
  assert.equal(body.name, "foo");
  const stored = JSON.parse(env.LOCKFILE_KV.store.get("skill:foo"));
  assert.equal(stored.version, "1.2.3");
  assert.equal(stored.sha, "a".repeat(40));
  assert.equal(stored.treeHash, "f".repeat(64));
  assert.equal(stored.registry, "artifacts");
  assert.match(stored.publishedAt, /^\d{4}-\d{2}-\d{2}T/);
});

test("POST /skills/:name/publish rejects body missing required fields", async () => {
  const env = makeEnv();
  for (const missing of ["version", "sha", "remote", "treeHash", "files"]) {
    const partial = { ...validPublishEntry };
    delete partial[missing];
    const { status, body } = await callJson(
      env,
      req("/skills/foo/publish", { method: "POST", body: JSON.stringify(partial) }),
    );
    assert.equal(status, 400, `expected 400 when ${missing} is missing`);
    assert.match(body.error, new RegExp(missing));
  }
});

test("GET /lockfile is public (no bearer required) and returns canonical lockfile JSON", async () => {
  const seed = {
    "skill:foo": JSON.stringify({
      version: "1.0.0", sha: "x".repeat(40), remote: "r", treeHash: "y".repeat(64),
      files: [], registry: "artifacts", publishedAt: "2026-04-25T00:00:00.000Z",
    }),
  };
  const env = makeEnv({ kvSeed: seed });
  const { status, body } = await callJson(env, req("/lockfile", { method: "GET", auth: null }));
  assert.equal(status, 200);
  assert.equal(body.version, 1);
  assert.equal(body.namespace, "flow");
  assert.equal(body.skills.foo.version, "1.0.0");
});

test("GET /lockfile returns an empty lockfile shape when KV is empty", async () => {
  const env = makeEnv();
  const { status, body } = await callJson(env, req("/lockfile", { method: "GET", auth: null }));
  assert.equal(status, 200);
  assert.deepEqual(body.skills, {});
});

test("GET /skills/:name is public and returns the single entry", async () => {
  const seed = {
    "skill:bar": JSON.stringify({
      version: "2.0.0", sha: "z".repeat(40), remote: "r", treeHash: "w".repeat(64),
      files: [], registry: "artifacts", publishedAt: "t",
    }),
  };
  const env = makeEnv({ kvSeed: seed });
  const { status, body } = await callJson(env, req("/skills/bar", { method: "GET", auth: null }));
  assert.equal(status, 200);
  assert.equal(body.version, "2.0.0");
});

test("GET /skills/:name returns 404 for unknown skill", async () => {
  const env = makeEnv();
  const { status } = await callJson(env, req("/skills/nope", { method: "GET", auth: null }));
  assert.equal(status, 404);
});

test("returns 500 when the Artifacts binding throws", async () => {
  const env = makeEnv({
    ARTIFACTS: {
      create: async () => {
        throw new Error("simulated artifacts failure");
      },
    },
  });
  const { status, body } = await callJson(env, req("/skills/foo", { method: "POST" }));
  assert.equal(status, 500);
  assert.match(body.error, /simulated artifacts failure/);
});
