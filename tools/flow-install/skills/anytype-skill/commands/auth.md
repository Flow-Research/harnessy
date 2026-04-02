# Auth — Anytype API Authentication

## Overview
Anytype uses a two-step challenge-response flow to issue API keys. Alternatively, keys can be created directly in the desktop app under Settings > API Keys.

## Challenge-Response Flow

### Step 1: Create a challenge
```bash
curl -s -X POST http://127.0.0.1:31009/v1/auth/challenges \
  -H "Content-Type: application/json" \
  -H "Anytype-Version: 2025-11-08" \
  -d '{"app_name": "claude-code-anytype"}'
```
**Response:**
```json
{
  "challenge_id": "abc123..."
}
```
The Anytype desktop app will display a **4-digit code**. Ask the user to read it.

### Step 2: Exchange for API key
```bash
curl -s -X POST http://127.0.0.1:31009/v1/auth/api_keys \
  -H "Content-Type: application/json" \
  -H "Anytype-Version: 2025-11-08" \
  -d '{"challenge_id": "<challenge_id>", "code": "<4-digit-code>"}'
```
**Response:**
```json
{
  "api_key": "base64-encoded-key..."
}
```

## Manual Key Creation
Users can also create keys in: **Anytype App > Settings > API Keys > Create new**

## Usage
All subsequent requests must include:
```
Authorization: Bearer <api_key>
Anytype-Version: 2025-11-08
```

## MCP Alternative
If the user has `@anyproto/anytype-mcp` installed, they can get a key via:
```bash
npx @anyproto/anytype-mcp get-key
```
