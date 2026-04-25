import { test } from "node:test";
import assert from "node:assert/strict";

import worker from "../src/index.mjs";

const TOKEN = "test-publish-token";

const makeEnv = (overrides = {}) => {
  const calls = { create: [], createToken: [] };
  const env = {
    PUBLISH_TOKEN: TOKEN,
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
