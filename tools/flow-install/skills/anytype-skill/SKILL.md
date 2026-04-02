---
name: anytype-skill
description: "Interact with Anytype's local REST API to manage spaces, objects, types, properties, tags, lists, and search."
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash, WebFetch
argument-hint: "<command> [args] (e.g., /anytype search 'meeting notes', /anytype objects list <space_id>)"
---

# Anytype Skill

## Purpose
Interact with Anytype's local-first REST API from Claude Code. Manage spaces, objects, types, properties, tags, lists, and run searches across your knowledge base — all without leaving the terminal.

Anytype runs a local HTTP API on your machine (no cloud). The desktop app listens on `127.0.0.1:31009`; `anytype-cli` on `127.0.0.1:31012`.

## Inputs
- Command group (auth, search, spaces, objects, types, properties, tags, lists, members)
- Subcommand (list, get, create, update, delete, etc.)
- Space ID (required for most operations)
- Object/type/property IDs as needed
- Search queries and filter expressions

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/anytype-skill/`.

## Prerequisites
1. Anytype desktop app must be running (or `anytype-cli` must be active).
2. An API key must be configured. See `${AGENTS_SKILLS_ROOT}/anytype-skill/commands/auth.md`.

## API Conventions
- **Base URL**: `http://127.0.0.1:31009/v1` (desktop) or `http://127.0.0.1:31012/v1` (CLI)
- **Auth header**: `Authorization: Bearer <api_key>`
- **Version header**: `Anytype-Version: 2025-11-08`
- **Content-Type**: `application/json`
- **Pagination**: `offset` and `limit` query params (default limit=100)
- All responses are JSON.

## Steps

### 1. Determine the base URL
Check which Anytype instance is running:
```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:31009/v1/spaces 2>/dev/null || \
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:31012/v1/spaces 2>/dev/null
```
Use whichever returns a response (even 401 means it's up).

### 2. Authenticate
If no API key is available, follow `${AGENTS_SKILLS_ROOT}/anytype-skill/commands/auth.md` to obtain one via the challenge-response flow.

### 3. Route to the appropriate command doc
Based on the user's request, read and follow the relevant command doc:
- `${AGENTS_SKILLS_ROOT}/anytype-skill/commands/auth.md` — Authentication & API keys
- `${AGENTS_SKILLS_ROOT}/anytype-skill/commands/search.md` — Global and space-scoped search
- `${AGENTS_SKILLS_ROOT}/anytype-skill/commands/spaces.md` — Space CRUD
- `${AGENTS_SKILLS_ROOT}/anytype-skill/commands/objects.md` — Object CRUD
- `${AGENTS_SKILLS_ROOT}/anytype-skill/commands/types.md` — Type CRUD + templates
- `${AGENTS_SKILLS_ROOT}/anytype-skill/commands/properties.md` — Property CRUD
- `${AGENTS_SKILLS_ROOT}/anytype-skill/commands/tags.md` — Tag CRUD on select/multi-select properties
- `${AGENTS_SKILLS_ROOT}/anytype-skill/commands/lists.md` — List views, add/remove objects
- `${AGENTS_SKILLS_ROOT}/anytype-skill/commands/members.md` — Space members

### 4. Execute the API call
Use `curl` via Bash to make the request. Always include auth and version headers.

### 5. Parse and present results
Format the JSON response for readability. Summarize key fields rather than dumping raw JSON unless the user asks for it.

## Error Handling
- **401 Unauthorized**: API key missing or expired. Re-authenticate.
- **404 Not Found**: Check space_id, object_id, etc. List available resources first.
- **Connection refused**: Anytype app is not running. Ask user to start it.
- **400 Bad Request**: Check request body against the command doc schema.

## Output
- Formatted summary of API response
- Raw JSON available on request
- Action confirmation for create/update/delete operations

## Feedback Capture

After completion, ask the user: **"Any feedback on this run? (skip to finish)"**
If provided, capture it:
```bash
python3 "${AGENTS_SKILLS_ROOT}/_shared/trace_capture.py" capture \
    --skill "anytype-skill" --gate "run_retrospective" --gate-type "retrospective" \
    --outcome "approved" --feedback "<user's feedback>"
```
