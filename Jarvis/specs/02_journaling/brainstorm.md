# Brainstorm: Jarvis Journaling

## Core Idea

A freeform journaling capability for Jarvis that saves entries to AnyType with intelligent structure, offers AI-powered deep dives on demand, and provides full retrieval and insight features via CLI.

## Problem Statement

Capturing thoughts and reflections should be frictionless. Current journaling tools either lack AI intelligence, don't integrate with personal knowledge bases, or require context-switching away from the terminal. The goal is to journal where you work (CLI), store where you organize (AnyType), and gain insights through AI—all in one seamless flow.

## Target User

Power users who:
- Prefer CLI-native workflows
- Use AnyType as their knowledge base / second brain
- Want AI assistance for reflection and pattern recognition
- Value daily practice without friction

## Solution Overview

### How It Works

1. **Freeform Capture** — Write freely using inline text, $EDITOR, or interactive prompt
2. **Smart Storage** — Entries saved to AnyType in structured hierarchy (Journal → Year → Month → Entry)
3. **AI Summary** — Title auto-generated as `<Day> - <AI-generated summary>`
4. **Deep Dive Option** — After saving, AI offers deeper analysis with user-specified format
5. **Context Persistence** — Everything stored in Jarvis context for cross-session continuity
6. **Retrieval & Insights** — List, read, search, and get AI-powered pattern analysis

### Entry Modes

| Mode | Command | Use Case |
|------|---------|----------|
| Inline | `jarvis journal write "Quick thought"` | Fast capture |
| Editor | `jarvis journal write` | Long-form reflection |
| Interactive | `jarvis journal write -i` | Multi-line without leaving terminal |

### AnyType Storage Structure

```
Journal (Collection)
└── 2026
    └── January
        ├── 24 - Morning Reflection on Project Goals
        ├── 24 - Late Night Thoughts on Balance
        └── 25 - Weekly Review
```

- Multiple entries per day allowed (different AI-generated summaries)
- Year/Month containers created automatically if they don't exist
- Entry linked to parent containers for proper hierarchy

### Deep Dive Flow

```
User writes entry
    ↓
Save to AnyType
    ↓
AI: "Would you like a deep dive?"
    ↓
If yes: "What format or focus?"
    ↓
User specifies (e.g., "explore the emotions", "action items", "Socratic questions")
    ↓
AI delivers deep dive
    ↓
Deep dive saved to Jarvis context (linked to entry)
```

### CLI Commands

```bash
jarvis journal write [text]     # Create entry (alias: jarvis j)
jarvis journal list             # Show recent entries
jarvis journal read <date|id>   # Display specific entry
jarvis journal search "query"   # Find entries by content
jarvis journal insights         # AI analysis across entries
```

## CLI Architecture Strategy

As Jarvis grows into a full personal assistant, commands follow a scalable pattern:

```
jarvis <domain> <action> [args]
```

### Discoverability

| Mechanism | Purpose |
|-----------|---------|
| `jarvis --help` | List all command groups |
| `jarvis <group> --help` | List subcommands |
| `jarvis commands --json` | Machine-readable manifest |
| Shell completions | Tab-complete support |
| Future: NL routing | "Jarvis, what did I journal about last week?" |

### Command Registry

Each module registers its commands with a central registry, enabling:
- Auto-generated help text
- JSON manifest for tooling/AI consumption
- Alias support (e.g., `jarvis j` → `jarvis journal write`)

## Context Persistence

Stored in Jarvis context (`~/.jarvis/journal/`):

- **Entry references** — AnyType object IDs and paths
- **Session context** — Conversation from deep dives
- **Metadata** — Timestamps, AI-extracted tags/themes
- **Cross-references** — Links to related tasks, notes, entries

Enables future capabilities:
- "What patterns do you see in my journaling?"
- Cross-referencing journal entries with tasks
- Mood/energy tracking over time

## Technical Foundation

### AnyType Integration

Extends existing `AnyTypeClient` with:
- `create_object()` — Create journal entries
- `get_or_create_collection()` — Find or create Journal/Year/Month containers
- `link_to_parent()` — Establish hierarchy relationships
- `search_by_type()` — Query journal entries

### AI Integration

Leverages existing `AIClient` with new prompts:
- **Summary generation** — Create concise entry titles
- **Deep dive** — Flexible analysis based on user format request
- **Insights** — Cross-entry pattern recognition

## Success Criteria

1. **Reliable storage** — Entries consistently saved in correct AnyType structure
2. **Insightful AI** — Deep dives feel genuinely valuable, not generic
3. **Daily usage** — Low enough friction that it becomes a habit
4. **Discoverability** — Commands are easy to find and remember

## Anti-Goals (What This Should NOT Be)

- A replacement for AnyType's native journaling/notes (it's a CLI companion)
- Overly structured or template-driven (freeform is the priority)
- Intrusive or nagging about journaling habits
- A standalone app—everything integrates with AnyType as source of truth

## Open Questions

- Should entries support attachments (images, files)?
- How to handle offline mode when AnyType isn't running?
- Should there be journal "types" (daily, gratitude, project-specific)?
- Integration with task scheduler (auto-journal completed tasks)?

## Inspiration

- "It's like Day One meets the terminal, with AI insight and AnyType as the brain"
- Goal: Move from "I should journal more" to "Journaling just happens"

---

*Brainstorm captured: 2026-01-24*
*Status: Ready for product specification*
