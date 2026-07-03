# Fathom Local Automation Runbook

This runbook describes the recommended local workflow for receiving Fathom
meeting webhooks, automatically converting them into normalized meeting notes,
and writing those notes into Jarvis destinations such as private context or a
wiki domain.

## Goal

Run one local automation stack that:

1. receives Fathom webhooks,
2. verifies signatures,
3. archives raw webhook payloads,
4. normalizes them into the canonical meeting format,
5. writes digestible markdown meeting notes automatically.

## Prerequisites

- `tmux` installed
- `cloudflared` installed
- `jarvis` installed from this repository or use `uv run python -m jarvis`
- a configured Fathom account in `~/.jarvis/config.yaml`
- a Fathom API key available via the configured environment variable
- for stable webhooks: a Cloudflare named tunnel and fixed hostname

Verify dependencies:

```bash
which tmux
which cloudflared
which jarvis
```

## Account Configuration

Jarvis uses named Fathom accounts.

Example `~/.jarvis/config.yaml`:

```yaml
fathom:
  default_account: personal
  accounts:
    personal:
      email: "you@gmail.com"
      api_key_env_var: "FATHOM_API_KEY_PERSONAL"
      webhook_secret_env_var: "FATHOM_WEBHOOK_SECRET_PERSONAL"
      webhook_id: "ikEoQ4bVoq4JYUmc"
      webhook_destination_url: "https://fathom.example.com"
    work:
      email: "you@company.com"
      api_key_env_var: "FATHOM_API_KEY_WORK"
      webhook_secret_env_var: "FATHOM_WEBHOOK_SECRET_WORK"
```

The account labels are arbitrary but must be used consistently in CLI commands.

## Recommended Setup Command

Use the interactive setup flow if needed:

```bash
jarvis config fathom-setup
```

That command can:

- normalize missing env var names,
- prompt for API keys and webhook secrets,
- write them into a managed env file,
- optionally source that env file from your shell profile.

Verify current setup:

```bash
jarvis config show
```

## Stable Tunnel Setup

Quick `trycloudflare.com` tunnels are useful for tests, but their URL changes
whenever the tunnel restarts. For daily automation, use a named Cloudflare
Tunnel with a stable hostname.

One-time Cloudflare setup:

```bash
cloudflared tunnel login
cloudflared tunnel create jarvis-fathom
cloudflared tunnel route dns jarvis-fathom fathom.example.com
```

Create `~/.cloudflared/config.yml` with the tunnel ID and credentials path that
`cloudflared tunnel create` prints:

```yaml
tunnel: <tunnel-id>
credentials-file: /Users/<user>/.cloudflared/<tunnel-id>.json
ingress:
  - hostname: fathom.example.com
    service: http://127.0.0.1:8765
  - service: http_status:404
```

Register the stable URL with Fathom via API:

```bash
jarvis meeting fathom webhook create \
  --account personal \
  --destination-url https://fathom.example.com
```

The create command stores the returned webhook ID/URL in `~/.jarvis/config.yaml`
and stores the returned signing secret in the managed Fathom env file.

If a webhook must be replaced, Fathom documents create/delete but not update:

```bash
jarvis meeting fathom webhook delete --account personal
jarvis meeting fathom webhook create --account personal --destination-url https://fathom.example.com
```

## Fully Automated Local Workflow

The simplest end-to-end command is:

```bash
jarvis meeting fathom start --account personal --auto-ingest --dest private-context
```

This creates a tmux session with:

- one window running the webhook receiver,
- one window running `cloudflared`.

For the stable named tunnel, use:

```bash
jarvis meeting fathom start \
  --account personal \
  --auto-ingest \
  --dest private-context \
  --tunnel-name jarvis-fathom \
  --no-attach
```

By default, the command attaches to the tmux session immediately. Use
`--no-attach` if you want it to launch in the background only.

If you want both processes visible at once, launch them as panes:

```bash
jarvis meeting fathom start --account personal --auto-ingest --dest private-context --layout panes
```

Tmux navigation:

- window layout: `Ctrl-b` then `n` / `p`
- pane layout: `Ctrl-b` then arrow keys

If one pane exits immediately, tmux now keeps the pane visible so you can read
the process error instead of losing it instantly.

### Dry Run First

```bash
jarvis meeting fathom start --account personal --dry-run --json
```

This prints:

- session name,
- webhook command,
- tunnel command,
- tmux launch commands.

### Launch In Background Only

```bash
jarvis meeting fathom start --account personal --auto-ingest --dest private-context --no-attach
```

Then attach later if needed:

```bash
tmux attach-session -t fathom-personal
```

## What Happens In Auto-Ingest Mode

When Fathom sends a webhook:

1. Jarvis receives the request on the local webhook server.
2. Jarvis verifies the webhook signature.
3. Jarvis archives the raw JSON payload locally.
4. Jarvis immediately normalizes the payload into a `MeetingRecord`.
5. Jarvis renders a summary-first markdown meeting artifact.
6. Jarvis writes that markdown into the chosen destination(s).
7. The archived inbox file moves from `pending/` to `processed/`.

The written artifact keeps summaries, key decisions, action items, open
questions, participants, project tags, and source metadata. Raw webhook payloads
remain archived for audit/retry, but the full transcript is not dumped into
private context, wiki, or journal notes by default.

## Where Files Go

Raw archived webhook payloads:

```text
.jarvis/context/private/<user>/meeting-inbox/fathom/<account>/pending/
.jarvis/context/private/<user>/meeting-inbox/fathom/<account>/processed/
.jarvis/context/private/<user>/meeting-inbox/fathom/<account>/invalid/
```

Normalized private-context meeting notes:

```text
.jarvis/context/private/<user>/meetings/YYYY/Mon/dd-<slug>.md
.jarvis/context/private/<user>/<project>/meetings/YYYY/Mon/dd-<slug>.md
```

## Manual Inbox Mode

If you do not use `--auto-ingest`, Jarvis still archives the webhook payloads.
You can ingest them later:

```bash
jarvis meeting fathom webhook ingest-inbox --account personal --dest private-context
```

Inspect first as JSON:

```bash
jarvis meeting fathom webhook ingest-inbox --account personal --limit 1 --keep --json
```

## Direct API Mode

These commands do not trigger webhooks. They call Fathom's API directly.

```bash
jarvis meeting fathom list --account personal --limit 5 --json
jarvis meeting fathom ingest 146820564 --account personal --dest private-context
jarvis meeting fathom ingest-today --account personal --dest private-context
jarvis meeting fathom ingest-today --account personal --dest private-context --lookback-hours 36
jarvis meeting fathom ingest-today --account personal --dest private-context --all-unpulled --max-pages 50
jarvis meeting fathom poll --dest private-context --json
```

`ingest-today` is intended as a safety poll. By default it scans from local
midnight; use `--lookback-hours` for hourly cron jobs so late-night recordings
are not missed around the date boundary. It skips recordings already present in
private meeting context so it can run after webhook ingestion without creating
duplicate notes.

For the hourly fallback job, prefer `poll`: Jarvis polls every configured Fathom
account, stores a per-account watermark under `~/.jarvis/state/fathom/`, applies
a safety overlap, and still skips recordings already present in private meeting
context. Keep `ingest-today --all-unpulled` as an explicit backfill/repair
command when you need to scan account history without a date cutoff.

## Troubleshooting

### Webhook not arriving

Check:

1. the account label matches your config key,
2. the webhook URL in Fathom matches the stable Cloudflare hostname,
3. the webhook secret env var is loaded for the same account,
4. the receiver is still running,
5. Fathom has actually finished processing the meeting.

Local status:

```bash
jarvis meeting fathom webhook status --account personal --check-url --json
```

### API access not working

Check:

```bash
jarvis config show
jarvis meeting fathom list --account personal --limit 5 --json
```

### Receiver works but nothing was written

Check the inbox folders. If payloads are in `pending/`, either:

- auto-ingest was not enabled, or
- ingestion failed after archive.

Try manual inbox ingestion:

```bash
jarvis meeting fathom webhook ingest-inbox --account personal --json
```

## Recommended Daily Commands

Start the fully automated local stack:

```bash
jarvis meeting fathom start --account personal --auto-ingest --dest private-context --tunnel-name jarvis-fathom --no-attach
```

Check direct account access:

```bash
jarvis meeting fathom list --account personal --limit 5 --json
```

Reprocess any archived payloads manually:

```bash
jarvis meeting fathom webhook ingest-inbox --account personal --dest private-context
```

Run the direct API fallback poll:

```bash
jarvis meeting fathom poll --dest private-context --json
```
