const SKILL_NAME_RE = /^[a-z0-9][a-z0-9-]{0,62}$/;

export class WorkerError extends Error {
  constructor(status, message, body) {
    super(message);
    this.name = "WorkerError";
    this.status = status;
    this.body = body;
  }
}

const validateName = (name) => {
  if (typeof name !== "string" || !SKILL_NAME_RE.test(name)) {
    throw new Error(`Invalid skill name: ${JSON.stringify(name)}`);
  }
};

const parseError = async (response) => {
  const text = await response.text();
  let parsed = null;
  try { parsed = JSON.parse(text); } catch {}
  const message = parsed?.error || text || `Worker ${response.status}`;
  return new WorkerError(response.status, message, parsed ?? text);
};

export class WorkerClient {
  constructor({ baseUrl, token, fetchImpl } = {}) {
    if (!baseUrl) throw new Error("WorkerClient requires baseUrl");
    if (!token) throw new Error("WorkerClient requires token");
    this.baseUrl = String(baseUrl).replace(/\/+$/, "");
    this.token = token;
    this.fetch = fetchImpl || globalThis.fetch.bind(globalThis);
  }

  _headers() {
    return {
      authorization: `Bearer ${this.token}`,
      "content-type": "application/json",
    };
  }

  async _post(path, body) {
    const init = {
      method: "POST",
      headers: this._headers(),
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    };
    const res = await this.fetch(`${this.baseUrl}${path}`, init);
    if (!res.ok) throw await parseError(res);
    return res.json();
  }

  async createSkill(name) {
    validateName(name);
    return this._post(`/skills/${name}`);
  }

  async mintToken(name, { access = "read", ttlSeconds } = {}) {
    validateName(name);
    return this._post(`/skills/${name}/tokens`, { access, ttlSeconds });
  }
}
