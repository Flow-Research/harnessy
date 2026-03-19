# Product Specification: Journal File Capture

**Full-Content Journaling with AI Summary**

---

## 1. Executive Summary

### Product Vision

Extend Jarvis journal to capture full file contents as journal entries, with an AI-generated summary prepended. When working in Claude Code sessions, the assistant asks the user whether to journal full content or a brief summary, giving the user control over journal quality.

### Value Proposition

For users who create documents during work sessions (architecture docs, meeting notes, design specs), journal entries should capture the complete artifact rather than a lossy one-line summary. This preserves the full context for future reference and search, while the AI summary provides a quick scannable overview.

### Feature Name

**Journal File Capture** (`--file` flag + plugin instructions update)

---

## 2. Problem Statement

### The Problem

When Claude Code creates a document (e.g., `system-components.md`) and the user journals about it, the journal entry contains only a brief summary like:

> "Created comprehensive System Components document mapping all platform components..."

The actual file content (which may be hundreds of lines of architecture diagrams, process flows, ownership matrices) is lost from the journal. The user must separately navigate to the file to see what was actually produced.

### Current State

- `jarvis j "text"` writes the exact text passed as the journal entry
- The Jarvis CLI does NOT truncate content -- full text reaches AnyType
- The Claude Code plugin has NO instructions about summarizing vs. full content
- Claude's default LLM behavior is to summarize what it did rather than pass the raw content
- There is no way to read file content into a journal entry from the CLI

### Impact

- **Lost context**: Journal entries become shallow breadcrumbs instead of rich records
- **Duplicate navigation**: Users must find the original file to recall what was created
- **Search degradation**: Full-text search in AnyType misses content that was summarized away
- **Inconsistent quality**: Journal usefulness varies depending on what Claude decides to write

---

## 3. Target Users

### Primary: CLI-native knowledge workers

Users who:
- Work in Claude Code sessions and create documents as part of their workflow
- Use Jarvis journal as a work log / knowledge capture system
- Want journal entries to serve as searchable, complete records
- Value control over what goes into their journal

---

## 4. User Stories

### US-1: Journal a file from CLI
**As a** Jarvis user, **I want to** run `jarvis j --file ./my-doc.md` **so that** the full file content becomes my journal entry with a smart summary at the top.

**Acceptance Criteria:**
- `--file` / `-f` flag reads the file and uses its content as the journal body
- AI generates a 3-5 sentence summary paragraph prepended above a `---` separator
- The full file content follows below the separator, unmodified
- Title is AI-generated from the content (unless `--title` is provided)
- Backward compatible: `jarvis j "text"` still works as before

### US-2: Claude asks before journaling
**As a** user working in Claude Code, **when** I ask Claude to journal a file it created, **I want** Claude to ask me whether to include the full content or just a summary **so that** I control journal entry quality.

**Acceptance Criteria:**
- Claude always asks: "Full file content or just a summary?"
- "Full content" triggers `jarvis j --file path/to/file`
- "Summary only" triggers `jarvis j "brief summary text"`
- Claude never assumes which option the user wants

### US-3: Graceful fallback
**As a** user, **if** the AI summary generation fails, **I want** the full file content to still be journaled without a summary **so that** no content is lost.

---

## 5. Functional Requirements

### FR-1: `--file` CLI flag
| Attribute | Detail |
|-----------|--------|
| Flag | `--file` / `-f` |
| Type | File path (validated by Click) |
| Applies to | `jarvis journal write`, `jarvis j` |
| Precedence | Highest (overrides `--editor`, `--interactive`, inline text) |

### FR-2: Entry format (file mode)
```
[AI-generated summary paragraph, 3-5 sentences]

---

[Full file content, exactly as read from disk]
```

### FR-3: Plugin behavior
- When Claude creates/writes a file AND user asks to journal it, Claude MUST ask
- Two options presented: "Full content (--file)" or "Summary only"
- Decision rules documented in plugin instructions

### FR-4: Backward compatibility
- All existing capture modes (inline, editor, interactive) unchanged
- Existing `jarvis j "text"` behavior identical
- No changes to journal list, read, search, insights commands

---

## 6. Non-Functional Requirements

- **No content truncation**: Full file content must reach AnyType regardless of size
- **Error handling**: Missing file, empty file, binary file, encoding errors all handled gracefully
- **Performance**: AI summary generation adds ~2-3 seconds (acceptable, matches existing title generation)

---

## 7. Out of Scope

- Journaling multiple files in one entry
- Watching files for changes and auto-journaling
- Piping stdin content to journal
- File format conversion (e.g., converting code files to markdown)

---

## 8. Success Metrics

- Journal entries from file mode contain the complete document content
- AI summary accurately reflects the document's purpose and key points
- No regression in existing journal functionality

---

*Created: Feb 10, 2026*
*Epic: 06_journal-file-capture*
