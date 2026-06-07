# WhatsApp Local Automation Runbook

This runbook describes the recommended local workflow for receiving Meta
WhatsApp Cloud API webhooks, archiving payloads, ingesting them into local-first
threads, and sending compliant replies through Jarvis.

## Goal

Run one local automation stack that:

1. receives WhatsApp Cloud API webhooks,
2. verifies Meta signatures,
3. archives raw webhook payloads,
4. normalizes messages and status events,
5. writes local-first conversation threads and optional context/journal/memory
   records.

## Provider Baseline

Use the official Meta WhatsApp Cloud API, not browser automation. The integration
requires a Meta business portfolio, WhatsApp Business Account, business phone
number, app access token, app secret, webhook verification token, and a public
HTTPS webhook URL.

Meta sends inbound messages and outbound delivery status updates through
webhooks. Free-form business replies depend on the customer service window;
template messages are required for outbound starts and delayed replies.

## Local Setup

Create or update local account config:

```bash
jarvis config whatsapp-setup
```

The command stores non-secret account metadata in `~/.jarvis/config.yaml` and
can write secrets into a managed env file:

```text
~/.jarvis/env/whatsapp.zsh
```

Verify wiring:

```bash
jarvis whatsapp webhook status --account personal --json
```

## Tunnel And Receiver

Dry-run the deterministic launch plan first:

```bash
jarvis whatsapp start --account personal --dry-run --json
```

Launch a local receiver plus quick Cloudflare tunnel:

```bash
jarvis whatsapp start \
  --account personal \
  --auto-ingest \
  --dest team-inbox \
  --no-attach
```

For stable Meta webhook registration, prefer a named Cloudflare tunnel and fixed
hostname:

```bash
cloudflared tunnel login
cloudflared tunnel create jarvis-whatsapp
cloudflared tunnel route dns jarvis-whatsapp whatsapp.example.com
```

Then configure `~/.cloudflared/config.yml` with ingress to
`http://127.0.0.1:8787` and launch:

```bash
jarvis whatsapp start \
  --account personal \
  --auto-ingest \
  --dest team-inbox \
  --tunnel-name jarvis-whatsapp \
  --no-attach
```

Register the public HTTPS URL in the Meta app webhook settings and subscribe to
the WhatsApp `messages` field.

## Operational Commands

```bash
# Ingest archived pending payloads manually
jarvis whatsapp webhook ingest-inbox --account personal --dest team-inbox

# Inspect conversation threads
jarvis whatsapp threads list --account personal
jarvis whatsapp threads read <thread-id>
jarvis whatsapp threads set-status <thread-id> --status waiting

# Reply inside the customer service window
jarvis whatsapp send --account personal --to +234... --text "Got it"

# Send an approved template for outbound starts or delayed replies
jarvis whatsapp send-template \
  --account personal \
  --to +234... \
  --template daily_brief
```

## File Locations

Raw archived payloads:

```text
.jarvis/context/private/<user>/whatsapp/<account>/inbox/pending/
.jarvis/context/private/<user>/whatsapp/<account>/inbox/processed/
.jarvis/context/private/<user>/whatsapp/<account>/inbox/invalid/
```

Local thread store:

```text
.jarvis/context/private/<user>/whatsapp/<account>/threads/
```

Optional private message logs:

```text
.jarvis/context/private/<user>/whatsapp/<account>/messages/YYYY/Mon/dd.md
```

## Quality Gates

- `jarvis whatsapp webhook status --json` shows app secret and verify token
  configured before starting the receiver.
- A signed sample webhook archives into `pending/`.
- `jarvis whatsapp webhook ingest-inbox --json` moves valid payloads to
  `processed/`.
- Duplicate message IDs do not create duplicate thread entries.
- Free-form sends are blocked unless a recent inbound message opens the service
  window.
- Template sends remain available for outbound starts.
