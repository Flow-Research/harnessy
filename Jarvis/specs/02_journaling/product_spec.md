# Product Specification: Jarvis Journaling

**AI-Powered Freeform Journaling for AnyType**

---

## 1. Executive Summary

### Product Vision

Jarvis Journaling extends the Jarvis personal assistant with a freeform journaling capability that integrates seamlessly with AnyType. Users capture thoughts from the CLI, entries are intelligently organized in AnyType, and AI provides on-demand deep dives and cross-entry insights.

### Value Proposition

For CLI-native power users who want to build a journaling habit, Jarvis Journaling removes friction by meeting them where they work (terminal), storing where they organize (AnyType), and adding intelligence that makes reflection more valuable (AI insights).

### Feature Name

**Jarvis Journaling** — Part of the broader Jarvis personal assistant ecosystem.

---

## 2. Problem Statement

### The Problem

Journaling tools today present several friction points:

- **Context switching**: GUI apps pull users away from their terminal workflow
- **No intelligence**: Traditional journals are passive storage—no insights, no patterns
- **Disconnected data**: Journal entries don't integrate with task management or knowledge bases
- **Inconsistent structure**: Manual organization leads to scattered, hard-to-find entries

The result: people intend to journal but don't, or journal inconsistently with little return on investment.

### Current State

AnyType users can manually create journal pages, but there's no:
- CLI-native capture flow
- Automatic organization by date
- AI-powered reflection or insight
- Integration with the broader Jarvis assistant

### Impact

- **Missed reflection**: Valuable thoughts go uncaptured
- **Lost patterns**: No way to see themes across entries over time
- **Habit failure**: Too much friction prevents consistent practice
- **Siloed data**: Journal doesn't connect to tasks, goals, or other personal data

---

## 3. Target Users

### Primary Persona: The Reflective Developer

**Demographics:**
- Software engineer or technical professional
- Lives in the terminal (IDE, git, CLI tools)
- Uses AnyType as personal knowledge base
- Already uses Jarvis for task scheduling

**Behaviors:**
- Wants to journal but struggles with consistency
- Values quick capture over elaborate ritual
- Interested in patterns and self-improvement
- Skeptical of "journaling apps" but open to integrated solutions

**Pain Points:**
- "I want to journal but I never remember to open the app"
- "My journal entries are all over the place—impossible to find anything"
- "I write the same things over and over but never notice the patterns"
- "I don't have time for 30-minute journaling sessions"

**Goals:**
- Capture thoughts in <60 seconds
- Build a consistent journaling habit
- Gain insights from accumulated entries
- Keep everything in AnyType as single source of truth

### Secondary Persona: The Quantified Self Enthusiast

- Tracks habits, moods, and productivity metrics
- Wants AI to surface patterns they'd miss manually
- Interested in cross-referencing journal with tasks and goals
- Values data export and queryability

---

## 4. User Stories & Requirements

### Epic 1: Journal Entry Capture

**US-1.1: Inline Quick Capture**
> As a user, I want to capture a quick thought without leaving my current context.

Acceptance Criteria:
- `jarvis journal write "Quick thought"` saves entry immediately
- AI generates summary title from content
- Entry saved to AnyType in correct hierarchy
- Confirmation displayed with entry path

**US-1.2: Editor-Based Entry**
> As a user, I want to write longer reflections in my preferred editor.

Acceptance Criteria:
- `jarvis journal write` (no text) opens $EDITOR
- User writes freely, saves, and closes editor
- Content captured and processed same as inline
- Empty content cancels without creating entry

**US-1.3: Interactive Multi-Line Entry**
> As a user, I want to write multi-line entries without leaving the terminal.

Acceptance Criteria:
- `jarvis journal write -i` or `--interactive` starts multi-line prompt
- User types freely, Ctrl+D (or Enter twice) to finish
- Same processing as other modes
- Clear instructions displayed for how to complete entry

**US-1.4: AI Title Generation**
> As a user, I want entries titled automatically so I don't break my writing flow.

Acceptance Criteria:
- AI generates concise summary (3-7 words) from entry content
- Title format: `<Day> - <AI Summary>` (e.g., "24 - Reflections on Project Deadline")
- Multiple entries per day get unique summaries
- Fallback to timestamp if AI unavailable

### Epic 2: AnyType Storage

**US-2.1: Hierarchical Organization**
> As a user, I want entries organized by date so they're easy to navigate in AnyType.

Acceptance Criteria:
- Entries stored in: `Journal → <Year> → <Month> → <Entry>`
- Year container created if doesn't exist (e.g., "2026")
- Month container created if doesn't exist (e.g., "January")
- Entry linked to month container as parent

**US-2.2: Journal Collection Discovery**
> As a user, I want Jarvis to find or create the Journal collection automatically.

Acceptance Criteria:
- Searches for existing "Journal" collection in selected space
- Creates Journal collection if not found
- Remembers Journal collection ID for future entries
- Works with user's existing Journal if present

**US-2.3: Entry Content Storage**
> As a user, I want my full journal entry preserved with metadata.

Acceptance Criteria:
- Full text stored in entry body/content
- Created timestamp recorded
- Entry type is Page or Note (configurable) [ASSUMPTION]
- Tags extracted by AI stored as entry tags [ASSUMPTION]

### Epic 3: AI Deep Dive

**US-3.1: Deep Dive Prompt**
> As a user, I want to optionally explore my entry more deeply with AI assistance.

Acceptance Criteria:
- After saving entry, AI asks: "Would you like a deep dive?"
- User can accept or decline
- Declining ends the session gracefully
- Prompt is non-intrusive (single question)

**US-3.2: Format Selection**
> As a user, I want to specify what kind of deep dive I want.

Acceptance Criteria:
- If user accepts, AI asks: "What format or focus?"
- User specifies freely (e.g., "explore emotions", "action items", "Socratic questions")
- AI adapts response to user's request
- Common formats suggested as examples

**US-3.3: Deep Dive Delivery**
> As a user, I want the deep dive to feel insightful and personalized.

Acceptance Criteria:
- AI references specific content from the entry
- Response matches requested format
- Tone is reflective, not preachy
- Length appropriate to request (not overwhelming)

**US-3.4: Deep Dive Persistence**
> As a user, I want deep dives saved so I can reference them later.

Acceptance Criteria:
- Deep dive content saved to Jarvis context
- Linked to original entry by AnyType object ID
- Retrievable via `jarvis journal read` command
- Stored in `~/.jarvis/journal/` directory

### Epic 4: Entry Retrieval

**US-4.1: List Recent Entries**
> As a user, I want to see my recent journal entries.

Acceptance Criteria:
- `jarvis journal list` shows recent entries
- Default: last 10 entries [ASSUMPTION]
- Displays: date, title, first line preview
- Option: `--limit N` to control count

**US-4.2: Read Specific Entry**
> As a user, I want to read a specific journal entry from the CLI.

Acceptance Criteria:
- `jarvis journal read <date>` shows entries for that date
- `jarvis journal read <id>` shows specific entry by ID
- Displays full entry content
- Shows deep dive if one exists

**US-4.3: Search Entries**
> As a user, I want to find entries containing specific words or themes.

Acceptance Criteria:
- `jarvis journal search "query"` finds matching entries
- Searches entry content and titles
- Returns list of matches with context snippets
- Results sorted by relevance or date [ASSUMPTION]

### Epic 5: Cross-Entry Insights

**US-5.1: Pattern Analysis**
> As a user, I want AI to identify patterns across my journal entries.

Acceptance Criteria:
- `jarvis journal insights` triggers cross-entry analysis
- AI reviews recent entries (configurable window)
- Surfaces: recurring themes, mood patterns, topic clusters
- Presents findings conversationally

**US-5.2: Time-Bounded Insights**
> As a user, I want to get insights for a specific time period.

Acceptance Criteria:
- `jarvis journal insights --since "2 weeks ago"` filters analysis window
- `jarvis journal insights --month January` for monthly review
- Clear indication of how many entries were analyzed

### Epic 6: CLI Architecture

**US-6.1: Command Group Structure**
> As a user, I want journal commands organized logically.

Acceptance Criteria:
- All journal commands under `jarvis journal` group
- Subcommands: `write`, `list`, `read`, `search`, `insights`
- Consistent with Jarvis command patterns
- Help text for each command

**US-6.2: Command Aliases**
> As a user, I want shortcuts for frequent actions.

Acceptance Criteria:
- `jarvis j` aliases to `jarvis journal write`
- Aliases registered in command registry
- Documented in help output

**US-6.3: Command Discoverability**
> As a user, I want to easily discover available commands.

Acceptance Criteria:
- `jarvis journal --help` shows all subcommands
- `jarvis commands --json` includes journal commands
- Shell completions include journal subcommands

### Epic 7: Context Persistence

**US-7.1: Entry Reference Storage**
> As a system, I need to track journal entries for cross-session continuity.

Acceptance Criteria:
- Entry references stored in `~/.jarvis/journal/entries.json`
- Includes: AnyType object ID, path, date, title
- Updated on each new entry
- Queryable for retrieval commands

**US-7.2: Session Context Storage**
> As a system, I need to store deep dive conversations.

Acceptance Criteria:
- Deep dive content stored per entry
- Includes: user request, AI response, timestamp
- Linked to entry by ID
- Supports multiple deep dives per entry

**US-7.3: Metadata Extraction**
> As a system, I should extract and store useful metadata.

Acceptance Criteria:
- AI extracts themes/tags from entries
- Mood indicators stored if detectable [ASSUMPTION]
- Metadata enables future insight features
- Stored alongside entry references

---

## 5. Feature Prioritization

### MVP (Must Have)

| Feature | Rationale |
|---------|-----------|
| Inline quick capture | Core entry point, fastest path |
| Editor-based entry | Essential for longer reflections |
| Interactive entry mode | CLI-native multi-line support |
| AI title generation | Removes friction, key differentiator |
| AnyType hierarchical storage | Foundation for organization |
| Journal collection discovery | Must work out of box |
| Deep dive prompt + delivery | Core AI value proposition |
| List recent entries | Essential for reviewing |
| Read specific entry | Complete the read/write cycle |
| Context persistence | Enables retrieval features |

### Post-MVP (Should Have)

| Feature | Rationale |
|---------|-----------|
| Search entries | Discoverability at scale |
| Cross-entry insights | Long-term AI value |
| Deep dive persistence | Build on deep dives over time |
| Command aliases | Power user efficiency |
| Metadata extraction | Enables future features |

### Future (Nice to Have)

| Feature | Rationale |
|---------|-----------|
| Journal types (daily, gratitude, project) | Structured journaling options |
| Attachment support | Images, files with entries |
| Offline mode | Queue entries when AnyType unavailable |
| Task integration | Auto-journal completed tasks |
| Voice capture | Dictation to journal |

---

## 6. User Experience

### Core Interaction Flow

```
┌─────────────────────────────────────────────────────────────┐
│                   Journal Entry Flow                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   Capture   │───▶│    Save     │───▶│  Deep Dive  │     │
│  │   Entry     │    │  to AnyType │    │   Offer     │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│        │                   │                   │            │
│        ▼                   ▼                   ▼            │
│  "Today I realized    "Saved: January/     "Would you like  │
│   something..."       24 - Realization      a deep dive?"   │
│                       About Growth"                          │
│                                                     │        │
│                                          ┌──────────┴──────┐ │
│                                          ▼                 ▼ │
│                                   ┌──────────┐    ┌─────────┐│
│                                   │   Yes    │    │   No    ││
│                                   │  Format? │    │  Done   ││
│                                   └────┬─────┘    └─────────┘│
│                                        ▼                     │
│                                   ┌──────────┐               │
│                                   │ Deliver  │               │
│                                   │ Insights │               │
│                                   └──────────┘               │
└─────────────────────────────────────────────────────────────┘
```

### CLI Interface Design

```bash
# Quick capture
$ jarvis journal write "Had a breakthrough on the API design today"

✓ Saved to Journal/2026/January
  └─ 24 - Breakthrough on API Design

Would you like a deep dive? [y/N]: n

# Editor mode
$ jarvis journal write

# Opens $EDITOR with empty file
# User writes, saves, closes

✓ Saved to Journal/2026/January
  └─ 24 - Reflections on Work-Life Balance

Would you like a deep dive? [y/N]: y
What format or focus? (e.g., emotions, action items, Socratic questions)
> explore the underlying feelings

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Deep Dive: Exploring Feelings
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You mentioned feeling "stretched thin" and "uncertain about priorities."
These seem connected—when priorities are unclear, everything feels urgent,
which creates that stretched feeling.

A few threads worth pulling:
• What would clarity on priorities actually look like for you?
• The "stretched thin" feeling—is it about time, energy, or both?
• You used "should" three times. Whose expectations are those?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# List recent entries
$ jarvis journal list

📔 Recent Journal Entries
━━━━━━━━━━━━━━━━━━━━━━━━━

  Jan 24  24 - Breakthrough on API Design
          "Had a breakthrough on the API design today..."

  Jan 24  24 - Reflections on Work-Life Balance
          "I've been thinking about how I spend my time..."

  Jan 23  23 - Weekly Planning Session
          "Starting the week with clear intentions..."

# Search entries
$ jarvis journal search "API"

🔍 Found 3 entries matching "API"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Jan 24  24 - Breakthrough on API Design
          "...the API design finally clicked when I..."

  Jan 20  20 - Frustrations with External APIs
          "...spent hours debugging the API response..."

  Jan 15  15 - Planning the New API
          "...sketching out what the API should look like..."

# Cross-entry insights
$ jarvis journal insights --since "2 weeks"

💡 Insights from 12 entries (Jan 10 - Jan 24)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Recurring Themes:
• Work-life balance mentioned in 5 entries
• API design is a current focus (4 entries)
• Energy levels lowest mid-week

Patterns:
• You journal most on Mondays and Fridays
• Positive entries often mention "clarity" or "breakthrough"
• Stress correlates with "should" and "need to" language

Observation:
Your entries this week show more resolution than last week.
The API breakthrough seems to have lifted broader mood.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Error States

| Scenario | Handling |
|----------|----------|
| AnyType not running | "AnyType desktop must be running. Please start it and try again." |
| Journal collection not found | Auto-create with confirmation: "Creating Journal collection in [Space]" |
| Empty entry submitted | "Entry is empty. Nothing saved." (graceful exit) |
| AI unavailable | Fallback title: "24 - Journal Entry" with warning |
| Entry save fails | "Failed to save entry. Your text has been saved to ~/.jarvis/journal/drafts/" |

---

## 7. Technical Requirements

### Platform & Runtime

- **Language**: Python 3.11+ (matches existing Jarvis)
- **Package Manager**: uv
- **Local Execution**: Runs alongside AnyType desktop

### Dependencies

| Dependency | Purpose | Status |
|------------|---------|--------|
| `anytype-client` | AnyType API operations | Existing |
| `anthropic` | Claude API for AI features | Existing |
| `click` | CLI framework | Existing |
| `rich` | Terminal formatting | Existing |
| `pydantic` | Data models | Existing |

### AnyType Integration Extensions

New methods required for `AnyTypeClient`:

| Method | Purpose |
|--------|---------|
| `create_object(space_id, type, name, content, parent_id)` | Create journal entries |
| `get_or_create_collection(space_id, name)` | Find or create Journal collection |
| `get_or_create_container(space_id, parent_id, name)` | Create Year/Month containers |
| `search_by_type(space_id, type_name, query)` | Query journal entries |
| `get_children(space_id, parent_id)` | List entries in container |

### AI Integration Extensions

New prompts for `AIClient`:

| Prompt | Purpose |
|--------|---------|
| `journal_title_prompt` | Generate concise title from content |
| `deep_dive_prompt` | Flexible analysis based on user format |
| `insights_prompt` | Cross-entry pattern recognition |
| `metadata_extraction_prompt` | Extract themes and tags |

### Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    User     │────▶│   Jarvis    │────▶│   Claude    │
│   (entry)   │     │  (journal)  │     │  (AI)       │
└─────────────┘     └─────────────┘     └─────────────┘
                          │                    │
                          ▼                    │
                    ┌─────────────┐            │
                    │  AnyType    │◀───────────┘
                    │  (storage)  │     (title, tags)
                    └─────────────┘
                          │
                          ▼
                    ┌─────────────┐
                    │ ~/.jarvis/  │
                    │  journal/   │
                    │ (context)   │
                    └─────────────┘
```

---

## 8. Context System Extension

### Journal-Specific Storage

```
~/.jarvis/
├── config.json           # Existing: space selection, etc.
├── pending.json          # Existing: task suggestions
└── journal/
    ├── entries.json      # Entry references and metadata
    ├── deep_dives/       # Deep dive content by entry ID
    │   ├── <entry_id_1>.json
    │   └── <entry_id_2>.json
    └── drafts/           # Recovery for failed saves
```

### Entry Reference Schema

```json
{
  "entries": [
    {
      "id": "anytype_object_id",
      "space_id": "space_id",
      "path": "Journal/2026/January",
      "title": "24 - Breakthrough on API Design",
      "date": "2026-01-24",
      "created_at": "2026-01-24T14:32:00Z",
      "tags": ["work", "technical"],
      "has_deep_dive": true
    }
  ]
}
```

### Deep Dive Schema

```json
{
  "entry_id": "anytype_object_id",
  "created_at": "2026-01-24T14:35:00Z",
  "user_request": "explore the underlying feelings",
  "ai_response": "You mentioned feeling stretched thin...",
  "format": "emotional exploration"
}
```

---

## 9. Non-Functional Requirements

### Performance

| Metric | Target |
|--------|--------|
| Inline capture to confirmation | <3 seconds |
| Editor mode save to confirmation | <3 seconds |
| Title generation | <2 seconds |
| Deep dive generation | <10 seconds |
| List 10 entries | <2 seconds |
| Search 100 entries | <5 seconds |
| Insights generation | <15 seconds |

### Reliability

- Entry content never lost (save to drafts on failure)
- Graceful degradation without AI (basic titles, no deep dive)
- Atomic AnyType operations (rollback on partial failure)

### Security

- Entry content sent to Claude API for processing
- No external storage beyond AnyType and local context
- API keys via environment variables

### Usability

- Maximum 2 prompts before entry is saved
- Clear progress indicators for AI operations
- Consistent command patterns with existing Jarvis commands

---

## 10. Success Metrics

### Primary Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Daily active journaling** | 5+ days/week | Days with at least one entry |
| **Deep dive acceptance rate** | >40% | Deep dives accepted ÷ offers |
| **Entry completion rate** | >90% | Entries saved ÷ entries started |

### Secondary Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to entry | <60 seconds | Capture to save time |
| Insight engagement | Weekly use | Insights command runs per week |
| Search usage | Growing | Search commands per month |

### Qualitative Success

- User reports journaling more consistently than before
- Deep dives described as "actually insightful"
- User prefers CLI capture over other journaling methods
- Entries are findable when user needs them

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| AnyType hierarchy creation fails | Medium | High | Validate API capabilities, fallback to flat storage |
| AI titles are poor quality | Medium | Medium | Allow manual title override, improve prompts iteratively |
| Deep dives feel generic | Medium | High | Strong prompts, reference specific entry content |
| Users forget to journal | High | Medium | Future: optional daily reminders (opt-in) |
| Context storage grows large | Low | Low | Implement rotation/archival strategy |
| Offline journaling needed | Medium | Medium | Future: queue entries for later sync |

---

## 12. Release Strategy

### Phase 1: Core Capture (MVP)

- Inline, editor, and interactive entry modes
- AI title generation
- AnyType hierarchical storage
- Deep dive prompt and delivery
- Basic list and read commands
- Context persistence

### Phase 2: Retrieval & Insights

- Search functionality
- Cross-entry insights
- Deep dive persistence
- Enhanced metadata extraction

### Phase 3: Power Features

- Command aliases
- Shell completions
- Journal types
- Task scheduler integration

---

## 13. Open Questions

### Resolved in This Spec

| Question | Resolution |
|----------|------------|
| Entry input modes | Inline, editor, and interactive all supported |
| Storage structure | Journal → Year → Month → Entry |
| Title format | `<Day> - <AI Summary>` |
| Deep dive persistence | Stored in ~/.jarvis/journal/deep_dives/ |

### Remaining Questions

| Question | Owner | Due |
|----------|-------|-----|
| Should entries support attachments? | Tech Spec | Future |
| Offline queueing architecture | Tech Spec | Future |
| Journal types (daily, gratitude, etc.) | Product | Post-MVP |
| Auto-journal completed tasks integration | Product | Post-MVP |

---

## 14. Dependencies & Integrations

### Required

| Dependency | Purpose | Status |
|------------|---------|--------|
| AnyType Desktop | API host, storage backend | Available |
| AnyType API | CRUD for journal entries | Available |
| Claude API | Title generation, deep dives, insights | Available |
| Existing Jarvis infrastructure | CLI, AnyType client, AI client | Available |

### Internal Integration

| Component | Integration Point |
|-----------|-------------------|
| Task Scheduler | Future: journal about completed tasks |
| Context System | Extend with journal-specific storage |
| Command Registry | Register journal commands |

---

## 15. Appendix

### A. Glossary

| Term | Definition |
|------|------------|
| **Journal Entry** | A single freeform text captured via Jarvis journal |
| **Deep Dive** | AI-powered analysis of an entry based on user-specified format |
| **Insights** | AI-generated patterns and themes across multiple entries |
| **Entry Reference** | Local pointer to an AnyType journal object |
| **Container** | AnyType object serving as parent (Year, Month folders) |

### B. CLI Command Reference

```
jarvis journal write [TEXT]         Write a journal entry (alias: jarvis j)
  -i, --interactive                 Multi-line interactive mode
  -e, --editor                      Force editor mode

jarvis journal list                 List recent entries
  --limit N                         Number of entries (default: 10)

jarvis journal read <DATE|ID>       Read a specific entry

jarvis journal search "QUERY"       Search entries
  --limit N                         Max results

jarvis journal insights             AI analysis across entries
  --since "TIMEFRAME"               Analysis window (e.g., "2 weeks")
  --month MONTH                     Specific month
```

### C. AI Prompt Guidelines

**Title Generation:**
- Concise: 3-7 words
- Capture essence, not details
- Avoid generic titles like "Journal Entry" or "Thoughts"
- Include emotional tone when relevant

**Deep Dive:**
- Reference specific content from entry
- Match requested format exactly
- Ask questions rather than lecture
- Be warm but not effusive

**Insights:**
- Surface non-obvious patterns
- Use specific examples from entries
- Avoid platitudes
- Be honest about limited data

### D. Related Documents

- `brainstorm.md` — Original ideation document
- `technical_spec.md` — Detailed technical architecture (next phase)
- `specs/01_task-scheduler/product_spec.md` — Related Jarvis feature

---

*Product Specification v1.0*
*Created: 2026-01-24*
*Status: Ready for technical specification*
