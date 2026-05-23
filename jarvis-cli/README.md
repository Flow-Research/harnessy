# Jarvis - AI Assistant for AnyType

A CLI tool for task scheduling and journaling that integrates with [AnyType](https://anytype.io/).

## Features

- **Task Management** - Create tasks with natural language due dates, priorities, and tags
- **Smart Scheduling** - AI-powered workload analysis and schedule rebalancing
- **Journaling** - Freeform journaling with AI-generated titles and insights
- **Context System** - Two-tier personalization (global + project-specific)
- **AnyType Folder Sync** - Incrementally sync local folder trees into AnyType Collections, Pages, and file objects

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- AnyType desktop app running locally (default: `localhost:31009`)
- Anthropic API key (for AI features)

## Installation

### Installed CLI from this workspace (recommended)

```bash
# From the Harnessy workspace root
uv tool install --force ./jarvis-cli

# Run the installed CLI
jarvis --help
```

### Using uv in a local checkout

```bash
git clone https://github.com/Flow-Research/harnessy.git
cd harnessy/jarvis-cli
uv sync
uv run jarvis --help
```

### GitHub install (after publishing `harnessy`)

```bash
uv tool install --force "git+https://github.com/Flow-Research/harnessy.git#subdirectory=jarvis-cli"
jarvis --help
```

### Using pip

```bash
git clone https://github.com/Flow-Research/harnessy.git
cd harnessy/jarvis-cli
pip install -e .

jarvis --help
```

### Shell Alias (optional)

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
alias jarvis="uv run --directory /path/to/jarvis python -m jarvis"
```

### Shell Completion (optional)

For zsh, add to `~/.zshrc`:
```bash
eval "$(_JARVIS_COMPLETE=zsh_source jarvis)"
```

For bash, add to `~/.bashrc`:
```bash
eval "$(_JARVIS_COMPLETE=bash_source jarvis)"
```

## Configuration

### Environment Variables

```bash
# Required for AI features
export ANTHROPIC_API_KEY="your-api-key"
```

### Two-Tier Context System

Jarvis uses a two-tier context system for AI personalization:

| Level | Location | Purpose |
|-------|----------|---------|
| **Global** | `~/.jarvis/context/` | User-wide preferences (all projects) |
| **Folder** | `./.jarvis/context/` | Project-specific overrides |

Folder context **overrides** global context. Use `{{global}}` in folder files to **include** global content.

```bash
# Initialize global context (~/.jarvis/context/)
jarvis init --global

# Initialize project context (./.jarvis/context/)
jarvis init --folder

# Check loaded context
jarvis context status

# Edit context files
jarvis context edit preferences        # Edit folder context
jarvis context edit goals --global     # Edit global context
```

### Context Files

| File | Purpose |
|------|---------|
| `preferences.md` | Work hours, task preferences |
| `patterns.md` | Weekly/daily work patterns |
| `constraints.md` | Hard rules that can't be violated |
| `priorities.md` | Current priority hierarchy |
| `goals.md` | Short and long-term goals |
| `projects.md` | Active projects |
| `focus.md` | Current focus areas |

## Usage

For the dedicated step-by-step local Fathom webhook automation guide, see:

- [`.jarvis/context/docs/operations/fathom-local-automation.md`](../.jarvis/context/docs/operations/fathom-local-automation.md)

### AnyType Folder Sync

Jarvis can sync a local file or folder tree into an AnyType Collection. Local
directories become AnyType Collections, supported text files become Pages, and
other files upload as native AnyType file objects by default. Sync state is
stored under `~/.jarvis/sync/state/`, so reruns update changed pages/files and
skip unchanged files. Preset runs use the preset name; ad-hoc runs use a stable
hash of source path plus destination so separate folder syncs do not share
state.

```bash
# Preview a sync without connecting to AnyType or writing state
jarvis sync run \
  --source ./notes \
  --destination "root_obj:space_id" \
  --dry-run

# Apply a sync to an AnyType Collection
jarvis sync run \
  --source ./notes \
  --destination "anytype://object?objectId=root_obj&spaceId=space_id"

# Skip the write confirmation for automation
jarvis sync run --source ./notes --destination "root_obj:space_id" --yes

# Add another text extension for one run
jarvis sync run \
  --source ./repo \
  --destination "root_obj:space_id" \
  --include-extension py \
  --dry-run

# Upload non-text files as native AnyType file objects (default)
jarvis sync run \
  --source ./notes \
  --destination "root_obj:space_id" \
  --unsupported-mode upload \
  --yes

# Represent non-text files as metadata placeholder pages instead
jarvis sync run \
  --source ./notes \
  --destination "root_obj:space_id" \
  --unsupported-mode stub \
  --yes

# Save and reuse a preset
jarvis sync preset add
jarvis sync run --preset flow-context --dry-run
jarvis sync run --preset flow-context --prune --yes
```

By default, sync includes `.md`, `.markdown`, `.txt`, and `.text` files, and
ignores `.git`, `.DS_Store`, and `node_modules`. Use repeated
`--include-extension` flags to add other text formats and repeated `--ignore`
flags for additional traversal skips. `--prune` deletes AnyType objects that
were previously synced by the preset and no longer exist locally. Real writes
validate that the destination object is an AnyType Collection before creating or
updating pages.

Files outside the text extension list, or included files that are not valid
UTF-8 text, are handled by `--unsupported-mode`. The default is
`--unsupported-mode upload`, which uploads those files through AnyType's Files
API and attaches the resulting file objects to the matching Collection. Use
`warn` to report and skip them, `error` to fail the run when any unsupported
file is found, or `stub` to create/update metadata placeholder Pages when you
want the AnyType tree to show the local folder structure without uploading the
binary content.

### Meeting Ingestion

Jarvis can normalize meeting transcripts and summaries into a concise,
summary-first meeting artifact, then route that artifact into one or more
destinations:

- `private-context`
- `wiki`
- `journal`

Generic ingestion works with files, stdin, URLs, and object-backed sources:

```bash
# Generic transcript or notes file
jarvis meeting ingest ./meeting-notes.md

# Piped transcript text
cat transcript.txt | jarvis meeting ingest - --resolver stdin --dest private-context

# Saved Fathom JSON/webhook payload
jarvis meeting ingest ./fathom-payload.json --no-enrich-ai --json
```

Written meeting artifacts keep the durable parts: summaries, key decisions,
action items, open questions, participants, project tags, and source metadata.
Full transcripts can be used for enrichment and routing, but they are not dumped
into private context, wiki, or journal notes by default.

### Fathom Setup

Jarvis supports both:

- direct Fathom API pulls
- local webhook development with an inbox workflow

If you only use one Fathom account, environment variables are enough:

```bash
export FATHOM_API_KEY="..."
export FATHOM_WEBHOOK_SECRET="whsec_..."
```

If you use multiple Google/Fathom identities, configure named accounts in
`~/.jarvis/config.yaml` and keep the secrets in environment variables:

```yaml
version: 1
active_backend: anytype

fathom:
  default_account: work
  accounts:
    work:
      email: "you@company.com"
      api_key_env_var: "FATHOM_API_KEY_WORK"
      webhook_secret_env_var: "FATHOM_WEBHOOK_SECRET_WORK"
    personal:
      email: "you@gmail.com"
      api_key_env_var: "FATHOM_API_KEY_PERSONAL"
      webhook_secret_env_var: "FATHOM_WEBHOOK_SECRET_PERSONAL"
```

```bash
export FATHOM_API_KEY_WORK="..."
export FATHOM_WEBHOOK_SECRET_WORK="whsec_..."
export FATHOM_API_KEY_PERSONAL="..."
export FATHOM_WEBHOOK_SECRET_PERSONAL="whsec_..."
```

The account names under `fathom.accounts` are arbitrary labels. Your CLI
commands must use those exact labels:

```yaml
fathom:
  accounts:
    personal: ...
    aa: ...
```

```bash
# Correct if the config key is `aa`
jarvis meeting fathom list --account aa

# This will fail unless `work` exists in the config
jarvis meeting fathom list --account work
```

Check the resolved config with:

```bash
jarvis config show
```

If you want Jarvis to automate the multi-account setup interactively, run:

```bash
jarvis config fathom-setup
```

That command will:

- normalize missing env var names in `~/.jarvis/config.yaml`
- let you enter or skip API keys and webhook secrets per account
- write a managed env file for the provided secrets
- optionally wire that env file into your shell profile so the setup stays active

### Fathom API Workflow

These commands query Fathom's API directly. They do **not** trigger webhooks.

List recent meetings for an account:

```bash
jarvis meeting fathom list --account work --limit 10
```

Ingest a Fathom meeting by recording ID:

```bash
jarvis meeting fathom ingest 123456789 --account work --dest private-context
```

Route the same meeting into a wiki domain:

```bash
jarvis meeting fathom ingest 123456789 \
  --account work \
  --dest private-context \
  --dest wiki \
  --wiki-domain accelerate-africa
```

### Fathom Webhook Workflow

If you want one command to launch both the webhook receiver and the public
tunnel in tmux, use:

```bash
jarvis meeting fathom start --account work --auto-ingest --dest private-context
```

That creates a tmux session with:

- one window running the webhook receiver
- one window running `cloudflared tunnel --url http://127.0.0.1:<port>`

By default, the command attaches to the tmux session immediately. Use
`--no-attach` if you want it to launch in the background only.

If you want both processes visible at once, use panes instead of windows:

```bash
jarvis meeting fathom start --account work --auto-ingest --dest private-context --layout panes
```

Tmux navigation:

- window layout: `Ctrl-b` then `n` / `p`
- pane layout: `Ctrl-b` then arrow keys

If one pane exits immediately, tmux now keeps the pane visible so you can read
the process error instead of losing it instantly.

Inspect before launching:

```bash
jarvis meeting fathom start --account work --dry-run --json
```

The local webhook flow is intentionally simple:

1. Run a local receiver.
2. Expose it publicly with a tunnel.
3. Let Fathom send signed webhook payloads.
4. Archive those payloads locally into an inbox.
5. Ingest the inbox into Jarvis destinations.

If you want a fully automated end-to-end flow, enable auto-ingest on the
receiver. Then each verified webhook is archived and immediately normalized
into your chosen destinations.

Run the local receiver:

```bash
jarvis meeting fathom webhook serve --account work --port 8765
```

Run the local receiver with automatic markdown ingestion:

```bash
jarvis meeting fathom webhook serve \
  --account work \
  --port 8765 \
  --auto-ingest \
  --dest private-context
```

With `--auto-ingest`, the flow becomes:

1. Fathom sends a webhook to your public tunnel URL.
2. Jarvis verifies the webhook signature.
3. Jarvis archives the raw payload into the local inbox.
4. Jarvis immediately normalizes that payload into the canonical meeting format.
5. Jarvis writes the markdown meeting artifact to the configured destination(s).
6. The archived inbox file is moved from `pending/` to `processed/`.

Expose it with `cloudflared`:

```bash
cloudflared tunnel --url http://127.0.0.1:8765
```

Use the resulting public HTTPS URL as the Fathom webhook destination for the
matching account.

After webhook payloads arrive, ingest the archived inbox:

```bash
jarvis meeting fathom webhook ingest-inbox --account work --dest private-context
```

Or emit structured JSON for inspection/automation:

```bash
jarvis meeting fathom webhook ingest-inbox --account work --json
```

Webhook payloads are archived under the private context tree so retries and
re-ingestion are easy to inspect locally.

### Fathom Troubleshooting

If a meeting does not seem to arrive end-to-end, check these in order:

1. The CLI account label matches `fathom.accounts.<name>` in `~/.jarvis/config.yaml`.
2. The correct API key env var is loaded for that account.
3. The correct webhook secret env var is loaded for that account.
4. The tunnel URL currently configured in Fathom matches the live public URL.
5. The local webhook receiver is still running.
6. Fathom has finished processing the meeting.

Useful checks:

```bash
# Verify account wiring and token/secret visibility
jarvis config show

# Check direct API access (does not trigger webhooks)
jarvis meeting fathom list --account personal --limit 5 --json

# Manually ingest archived webhook payloads if you are not using --auto-ingest
jarvis meeting fathom webhook ingest-inbox --account personal --json
```

### Task Management

```bash
# Quick task creation
jarvis t "Buy groceries" --due tomorrow
jarvis t "Review PR" -d friday -p high -t work

# With multiple tags
jarvis t "Fix bug #123" -p high -t urgent -t bugs

# Open editor for description
jarvis task create "Q1 Planning" --due "jan 31" -p high -e

# Verbose output
jarvis t "Important task" --due tomorrow -v
```

### Schedule Management

```bash
# Analyze workload for next 14 days
jarvis analyze

# Generate AI rescheduling suggestions
jarvis suggest

# Apply suggestions interactively
jarvis apply

# Apply all suggestions without prompting
jarvis apply --yes

# Full schedule rebalance
jarvis rebalance
```

### Journaling

```bash
# Quick journal entry (AI generates title)
jarvis j "Today I learned about async/await patterns..."

# With custom title
jarvis j "Entry text" --title "My Custom Title"

# Open editor for longer entries
jarvis journal write --editor

# Interactive multi-line mode
jarvis journal write --interactive

# List recent entries
jarvis journal list

# Read specific entry (by list number)
jarvis journal read 1

# Search entries
jarvis journal search "python"

# AI insights across entries
jarvis journal insights --days 30
```

### Space Management

```bash
# List available AnyType spaces
jarvis spaces

# Select a different space
jarvis spaces --select
```

## Example Session

```bash
$ jarvis analyze

📊 Schedule Analysis (Next 14 Days)

  Mon 27  ████████████  8 tasks  ⚠️  Overloaded
  Tue 28  ██████        4 tasks  ✓
  Wed 29  ████          2 tasks  ○  Light
  ...

$ jarvis suggest

💡 3 Suggestions Generated

1. "Write API docs"
   Mon 27 → Wed 29
   Reason: Balances workload, no deadline pressure

$ jarvis j "Shipped the new feature today!"

╭─────────────── Journal ───────────────╮
│ Entry saved!                          │
│                                       │
│ 24 - Feature Launch Victory           │
│ Journal/2026/January                  │
╰───────────────────────────────────────╯
```

## Development

### Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ -v --cov=src/jarvis --cov-report=term-missing

# Run specific test file
uv run pytest tests/task/test_cli.py -v
```

### Code Quality

```bash
# Linting
uv run ruff check src/

# Type checking
uv run mypy src/jarvis/

# Format code
uv run ruff format src/
```

## Project Structure

```
src/jarvis/
├── cli.py              # Main CLI entry point
├── anytype_client.py   # AnyType API wrapper
├── context_reader.py   # Two-tier context loading
├── analyzer.py         # Workload analysis
├── ai_client.py        # Anthropic API client
├── models.py           # Pydantic models
├── state.py            # Global state management
├── journal/            # Journaling subsystem
│   ├── cli.py          # Journal CLI commands
│   ├── hierarchy.py    # Journal → Year → Month structure
│   ├── capture.py      # Entry capture modes
│   └── ...
└── task/               # Task management subsystem
    ├── cli.py          # Task CLI commands
    ├── service.py      # Task creation service
    ├── date_parser.py  # Natural language date parsing
    └── editor.py       # Editor integration

~/.jarvis/                    # Global Jarvis data
├── config.json               # Settings (selected space, etc.)
├── .jarvis/context/          # Project context files
├── journal/                  # Journal state
└── pending.json              # Pending suggestions
```

## Troubleshooting

### AnyType Connection Issues

Ensure AnyType desktop app is running and the gRPC server is enabled:
- Default endpoint: `localhost:31009`
- Check AnyType settings for API/gRPC configuration

### API Key Issues

```bash
# Verify API key is set
echo $ANTHROPIC_API_KEY

# Or set it inline
ANTHROPIC_API_KEY=your-key jarvis suggest
```

## License

MIT
