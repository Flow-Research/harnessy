import { test } from "node:test";
import assert from "node:assert/strict";

import { WorkerClient, WorkerError } from "../lib/registry/worker-client.mjs";

const makeFetch = (handler) => {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url: String(url), init });
    return handler({ url: String(url), init });
  };
  fetchImpl.calls = calls;
  return fetchImpl;
};

const jsonResponse = (status, body) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

test("WorkerClient.createSkill POSTs to /skills/:name with bearer token", async () => {
  const fetchImpl = makeFetch(() =>
    jsonResponse(200, {
      name: "issue-flow",
      remote: "https://artifacts.example/issue-flow.git",
      writeToken: "wt",
      ttl: 3600,
    }),
  );
  const client = new WorkerClient({
    baseUrl: "https://worker.example",
    token: "publish-token",
    fetchImpl,
  });
  const result = await client.createSkill("issue-flow");
  assert.equal(result.remote, "https://artifacts.example/issue-flow.git");
  assert.equal(result.writeToken, "wt");
  assert.equal(fetchImpl.calls.length, 1);
  assert.equal(fetchImpl.calls[0].url, "https://worker.example/skills/issue-flow");
  assert.equal(fetchImpl.calls[0].init.method, "POST");
  assert.equal(fetchImpl.calls[0].init.headers.authorization, "Bearer publish-token");
});

test("WorkerClient strips trailing slash from baseUrl", async () => {
  const fetchImpl = makeFetch(() => jsonResponse(200, {
    name: "foo", remote: "r", writeToken: "w", ttl: 1,
  }));
  const client = new WorkerClient({ baseUrl: "https://w.example/", token: "t", fetchImpl });
  await client.createSkill("foo");
  assert.equal(fetchImpl.calls[0].url, "https://w.example/skills/foo");
});

test("WorkerClient.mintToken POSTs body with access + ttlSeconds", async () => {
  const fetchImpl = makeFetch(() =>
    jsonResponse(200, { token: "rt", access: "read", ttl: 7200 }),
  );
  const client = new WorkerClient({ baseUrl: "https://w.example", token: "t", fetchImpl });
  const result = await client.mintToken("foo", { access: "read", ttlSeconds: 7200 });
  assert.equal(result.token, "rt");
  assert.equal(fetchImpl.calls[0].url, "https://w.example/skills/foo/tokens");
  assert.equal(fetchImpl.calls[0].init.method, "POST");
  assert.deepEqual(JSON.parse(fetchImpl.calls[0].init.body), { access: "read", ttlSeconds: 7200 });
});

test("WorkerClient throws WorkerError with status + body on 4xx", async () => {
  const fetchImpl = makeFetch(() => jsonResponse(401, { error: "Unauthorized" }));
  const client = new WorkerClient({ baseUrl: "https://w.example", token: "bad", fetchImpl });
  await assert.rejects(
    () => client.createSkill("foo"),
    (err) => {
      assert.ok(err instanceof WorkerError);
      assert.equal(err.status, 401);
      assert.match(err.message, /Unauthorized/);
      return true;
    },
  );
});

test("WorkerClient throws WorkerError on 5xx", async () => {
  const fetchImpl = makeFetch(() => jsonResponse(500, { error: "boom" }));
  const client = new WorkerClient({ baseUrl: "https://w.example", token: "t", fetchImpl });
  await assert.rejects(
    () => client.createSkill("foo"),
    (err) => err instanceof WorkerError && err.status === 500,
  );
});

test("WorkerClient surfaces non-JSON error bodies", async () => {
  const fetchImpl = makeFetch(() => new Response("plain text error", { status: 502 }));
  const client = new WorkerClient({ baseUrl: "https://w.example", token: "t", fetchImpl });
  await assert.rejects(
    () => client.createSkill("foo"),
    (err) => err instanceof WorkerError && err.status === 502 && /plain text/.test(err.message),
  );
});

test("WorkerClient validates skill name client-side before calling fetch", async () => {
  const fetchImpl = makeFetch(() => jsonResponse(200, {}));
  const client = new WorkerClient({ baseUrl: "https://w.example", token: "t", fetchImpl });
  await assert.rejects(() => client.createSkill("BAD NAME"), /Invalid skill name/);
  assert.equal(fetchImpl.calls.length, 0, "fetch must not be called for invalid name");
});

test("WorkerClient requires baseUrl and token at construction", () => {
  assert.throws(() => new WorkerClient({ token: "t" }), /baseUrl/);
  assert.throws(() => new WorkerClient({ baseUrl: "https://x" }), /token/);
});
