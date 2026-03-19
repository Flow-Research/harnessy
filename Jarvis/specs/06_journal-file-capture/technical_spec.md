# Technical Specification: Journal File Capture

**Full-Content Journaling with AI Summary**

---

## 1. Overview

### Purpose

This document provides the technical blueprint for adding file-based content capture to Jarvis journal. The feature adds a `--file` flag that reads a file from disk, generates an AI summary paragraph, and stores both as a single journal entry. The Claude Code plugin is also updated to ask users whether to journal full content or a summary.

### Scope

- New `--file` / `-f` CLI flag on `jarvis journal write` and `jarvis j`
- New `CaptureMode.FILE` in the capture module
- AI prompt for file content summarization
- Plugin instruction update for Claude Code behavior
- CLI docs generation update

### Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| File reading | `pathlib.Path.read_text()` | Consistent with existing codebase, handles encoding |
| Path validation | `click.Path(exists=True)` | Click validates before function body, clean error messages |
| Summary AI model | Claude Sonnet (existing `call_ai`) | Reuses existing AI infrastructure, matches title generation |
| Summary format | Paragraph + `---` + full content | Clean visual separation, AnyType renders markdown |
| Flag precedence | `--file` > `--editor` > `--interactive` > inline | Most specific input source wins |

### References

- [Product Specification](./product_spec.md)
- [Journaling Technical Spec](../02_journaling/technical_spec.md)
- [Existing capture module](../../src/jarvis/journal/capture.py)

---

## 2. System Architecture

### Change Impact

This feature adds a new capture mode to the existing journal pipeline. No new modules are created; all changes extend existing files.

```
                          EXISTING (unchanged)
                          ──────────────────────
User ─► CLI ─► capture ─► draft ─► title AI ─► AnyType hierarchy ─► save ref
                 │
                 │  NEW
                 ├──► CaptureMode.FILE ─► read file from disk
                 │                              │
                 └──► _compose_file_entry() ────┘
                      │                          │
                      ├─ call_ai(summary prompt) │
                      │                          │
                      └─ return: summary + --- + content
```

### Files Modified

| File | Change | Lines Affected |
|------|--------|----------------|
| `src/jarvis/journal/capture.py` | Add `FILE` mode, `_capture_from_file()`, update `determine_capture_mode()` | ~40 lines added |
| `src/jarvis/journal/prompts.py` | Add `FILE_SUMMARY_SYSTEM`, `FILE_SUMMARY_PROMPT`, `format_file_summary_prompt()` | ~30 lines added |
| `src/jarvis/journal/cli.py` | Add `--file` option, `_compose_file_entry()` helper, file mode branch | ~35 lines added |
| `src/jarvis/cli.py` | Update `_generate_docs()` for journal write and j alias | ~6 lines added |
| `plugins/jarvis/commands/jarvis.md` | Add file journaling section to execution logic | ~40 lines added |
| `tests/journal/test_capture.py` | Add tests for FILE mode | ~60 lines added |

---

## 3. Detailed Design

### 3.1 Capture Module Changes

**File:** `src/jarvis/journal/capture.py`

#### CaptureMode Enum

```python
class CaptureMode(str, Enum):
    INLINE = "inline"
    EDITOR = "editor"
    INTERACTIVE = "interactive"
    FILE = "file"  # NEW
```

#### New Function: `_capture_from_file`

```python
def _capture_from_file(file_path: str) -> str | None:
    """Read content from a file path.

    Args:
        file_path: Path to the file to read

    Returns:
        File content or None if file doesn't exist or is empty
    """
    from pathlib import Path

    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        return None

    if not path.is_file():
        console.print(f"[red]Not a file: {file_path}[/red]")
        return None

    try:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            console.print(f"[yellow]File is empty: {file_path}[/yellow]")
            return None
        return content
    except (OSError, UnicodeDecodeError) as e:
        console.print(f"[red]Error reading file: {e}[/red]")
        return None
```

**Design notes:**
- `expanduser()` handles `~` in paths
- `resolve()` handles relative paths
- `UnicodeDecodeError` catch handles binary files gracefully
- Click's `Path(exists=True)` provides first-pass validation; this function adds file-type and encoding checks

#### Updated `capture_entry`

Add a case for `CaptureMode.FILE`:

```python
elif mode == CaptureMode.FILE:
    return _capture_from_file(initial_text)  # initial_text carries file_path
```

**Design note:** The `initial_text` parameter is reused to carry the file path when mode is FILE. This avoids changing the function signature and is consistent with how EDITOR mode uses it to carry initial editor content.

#### Updated `determine_capture_mode`

```python
def determine_capture_mode(
    text: str | None,
    interactive: bool = False,
    force_editor: bool = False,
    file_path: str | None = None,  # NEW
) -> tuple[CaptureMode, str]:
```

New precedence (file_path checked first):

```python
if file_path:
    return CaptureMode.FILE, file_path

if force_editor:
    return CaptureMode.EDITOR, text or ""
# ... rest unchanged
```

---

### 3.2 Prompt Template

**File:** `src/jarvis/journal/prompts.py`

Add after the Title Generation section:

```python
# =============================================================================
# File Content Summary
# =============================================================================

FILE_SUMMARY_SYSTEM = """You are a technical writing assistant that creates concise
summaries of documents and files.

Guidelines:
- Write a single paragraph (3-5 sentences) summarizing the key content
- Capture the purpose, main points, and significance of the document
- Use clear, informative language
- Reference the document type when relevant (e.g., architecture doc, config, plan)
- Do not use bullet points - write a flowing paragraph

Output ONLY the summary paragraph, nothing else."""

FILE_SUMMARY_PROMPT = """Summarize the following file content in a single paragraph:

Filename: {filename}

---
{content}
---

Summary:"""
```

Add helper function:

```python
def format_file_summary_prompt(content: str, filename: str) -> str:
    """Format the file summary prompt with content and filename."""
    return FILE_SUMMARY_PROMPT.format(content=content, filename=filename)
```

**Design notes:**
- Including filename gives the AI document-type context (e.g., `roadmap.md` vs `config.yaml`)
- Single paragraph format keeps the summary clean above the separator
- No bullet points — this is a journal entry preamble, not a table of contents

---

### 3.3 CLI Command Changes

**File:** `src/jarvis/journal/cli.py`

#### New Click Option

```python
@journal_cli.command(name="write")
@click.argument("text", required=False, default=None)
@click.option("-e", "--editor", is_flag=True, help="Open editor for entry")
@click.option("-i", "--interactive", is_flag=True, help="Interactive multi-line input")
@click.option("-f", "--file", "file_path", default=None,
              type=click.Path(exists=True),
              help="Read entry content from a file (prepends AI summary)")
@click.option("--space", default=None, help="Space name or ID")
@click.option("--title", default=None, help="Custom title (skips AI generation)")
@click.option("--no-deep-dive", is_flag=True, help="Skip deep dive prompt")
def write_entry(
    text: str | None,
    editor: bool,
    interactive: bool,
    file_path: str | None,  # NEW
    space: str | None,
    title: str | None,
    no_deep_dive: bool,
) -> None:
```

**Note:** `click.Path(exists=True)` validates the file exists before the function body runs. If the file doesn't exist, Click provides: `Error: Invalid value for '-f' / '--file': Path 'xyz' does not exist.`

#### Updated `write_entry` Body

Add file_path to `determine_capture_mode()` call:

```python
mode, initial_text = determine_capture_mode(
    text=text,
    interactive=interactive,
    force_editor=editor,
    file_path=file_path,  # NEW
)
```

Add file mode info display:

```python
elif mode == CaptureMode.FILE:
    console.print(f"[dim]Reading from file: {file_path}[/dim]")
```

After content capture, compose file entry if in file mode:

```python
if not content:
    console.print("[yellow]No content entered. Entry cancelled.[/yellow]")
    return

# For file mode: generate summary and compose combined content
if mode == CaptureMode.FILE:
    content = _compose_file_entry(content, file_path)
```

#### New Helper: `_compose_file_entry`

```python
def _compose_file_entry(file_content: str, file_path: str) -> str:
    """Compose a journal entry from file content with AI summary.

    Generates an AI summary paragraph and prepends it above the full
    file content, separated by a horizontal rule.

    Args:
        file_content: The raw file content
        file_path: Path to the source file (for filename context)

    Returns:
        Combined content: summary + separator + full file content
    """
    from pathlib import Path

    filename = Path(file_path).name

    console.print("[dim]Generating summary...[/dim]")

    prompt = format_file_summary_prompt(file_content, filename)
    summary = call_ai(FILE_SUMMARY_SYSTEM, prompt, max_tokens=300)

    if summary:
        return f"{summary}\n\n---\n\n{file_content}"
    else:
        console.print("[yellow]Could not generate summary, using file content only.[/yellow]")
        return file_content
```

#### Updated Imports

```python
from jarvis.journal.prompts import (
    FILE_SUMMARY_SYSTEM,
    TITLE_GENERATION_SYSTEM,
    format_file_summary_prompt,
    format_title_prompt,
)
```

---

### 3.4 Docs Generation Update

**File:** `src/jarvis/cli.py`

Update `_generate_docs()` in two places:

**Journal write options** (~line 1132):
```python
"options": {
    "TEXT": "Entry text (optional, opens editor if not provided)",
    "--editor, -e": "Open editor for entry",
    "--interactive, -i": "Interactive multi-line input",
    "--file, -f": "Read entry content from a file (prepends AI summary)",  # NEW
    "--title": "Custom title (skips AI generation)",
    "--no-deep-dive": "Skip deep dive prompt",
},
"examples": [
    'jarvis journal write "Had a great day"',
    "jarvis journal write --editor",
    "jarvis journal write -i",
    'jarvis journal write --file ./notes.md --title "Meeting Notes"',  # NEW
],
```

**`j` alias options** (~line 1181):
```python
"options": {
    "TEXT": "Entry text",
    "--title": "Custom title",
    "--file, -f": "Read content from file with AI summary",  # NEW
},
"examples": [
    'jarvis j "Quick thought for today"',
    'jarvis j "Meeting notes" --title "Team Sync"',
    "jarvis j --file ./design.md",  # NEW
],
```

---

### 3.5 Plugin Instruction Update

**File:** `/Users/julian/Documents/Code/Claude Plugins/plugins/jarvis/commands/jarvis.md`

#### Add to Command Mapping table (after line 179):

```markdown
| Journal a file's content | `jarvis j --file path/to/file.md` |
```

#### Add new subsection after "### 3. Normal Command Execution" (after line 185):

```markdown
### 4. File Journaling (When Claude Creates/Writes Documents)

When you create or write a document file for the user (e.g., a spec, design doc,
meeting notes, architecture document), and the user asks to journal about it,
you MUST ask before writing the journal entry:

**Always use AskUserQuestion with these options:**
- **Full content** - Uses `jarvis j --file path/to/file.md` which reads the
  entire file, generates a summary paragraph at the top, and saves everything
- **Summary only** - Uses `jarvis j "Your summary text here"` with just a
  short description of what was created

**Decision rules:**
- NEVER assume which option the user wants — always ask
- If the user says "full content" or "the whole thing", use `--file`
- If the user says "just a summary" or "brief note", write a concise summary as inline text
- You can add `--title "Title Here"` in either case to skip AI title generation

**Example flows:**

File journaling with full content:
```
jarvis j --file ./system-components.md --title "System Components Design"
```

File journaling with summary only:
```
jarvis j "Designed system component architecture covering auth, data pipeline, and API gateway"
```
```

---

## 4. Entry Format Specification

When `--file` is used, the journal entry stored in AnyType has this format:

```
┌─────────────────────────────────────────────────────┐
│  AI-GENERATED SUMMARY (3-5 sentences, paragraph)    │
│                                                     │
│  This architecture document defines the system      │
│  component structure for the AA Platform, covering  │
│  user-facing applications, data infrastructure,     │
│  and operational tooling. It establishes ownership   │
│  matrices and process flows for feature development  │
│  and bug resolution.                                │
│                                                     │
│  ─────────────────────────────────────────────────  │
│                                                     │
│  FULL FILE CONTENT (exactly as read from disk)      │
│                                                     │
│  # AA Platform: System Components                   │
│  ## System Component Map                            │
│  ...                                                │
│  (entire file, unmodified)                          │
└─────────────────────────────────────────────────────┘
```

**Title:** AI-generated from the combined content (summary + file), or user-provided via `--title`.

**Local reference preview:** First 200 characters of the combined content (captures the summary, which is the most useful preview text).

---

## 5. Error Handling

| Scenario | Handler | Behavior |
|----------|---------|----------|
| File doesn't exist | `click.Path(exists=True)` | Click aborts with clear error before function runs |
| Path is a directory | `_capture_from_file()` | Returns None, prints error, entry cancelled |
| File is empty | `_capture_from_file()` | Returns None, prints warning, entry cancelled |
| Binary file (encoding error) | `_capture_from_file()` | Catches `UnicodeDecodeError`, returns None |
| AI summary fails | `_compose_file_entry()` | Falls back to file content without summary |
| AnyType connection fails | Existing `get_connected_client()` | Existing error handling, draft preserved |

---

## 6. Flag Interaction Matrix

| Flags Used | Behavior |
|------------|----------|
| `--file path.md` | Read file, generate summary, journal combined content |
| `--file path.md --title "Title"` | Same, but skip AI title generation |
| `--file path.md --no-deep-dive` | Same, but skip deep dive offer |
| `--file path.md -e` | `--file` wins (highest precedence) |
| `--file path.md "inline text"` | `--file` wins, inline text ignored |
| `-e "text"` | Editor opens with text pre-filled (existing behavior) |
| `"text"` | Inline mode (existing behavior) |
| (no args) | Editor opens (existing behavior) |

---

## 7. Testing Plan

### Test File: `tests/journal/test_capture.py` (extend existing)

#### New Tests for `_capture_from_file`

| Test | Input | Expected |
|------|-------|----------|
| `test_file_reads_content` | Valid file with content | Returns file content string |
| `test_file_not_found` | Non-existent path | Returns None |
| `test_file_is_directory` | Directory path | Returns None |
| `test_file_empty` | Empty file | Returns None |
| `test_file_encoding_error` | Binary file | Returns None |
| `test_file_expands_home` | Path with `~` | Reads from expanded path |
| `test_file_strips_whitespace` | File with leading/trailing whitespace | Returns stripped content |

#### New Tests for `determine_capture_mode` with `file_path`

| Test | Input | Expected |
|------|-------|----------|
| `test_file_path_sets_file_mode` | `file_path="/tmp/f.md"` | `(FILE, "/tmp/f.md")` |
| `test_file_path_beats_editor` | `file_path="/tmp/f.md", force_editor=True` | `(FILE, "/tmp/f.md")` |
| `test_file_path_beats_text` | `file_path="/tmp/f.md", text="inline"` | `(FILE, "/tmp/f.md")` |
| `test_no_file_path_unchanged` | `file_path=None, text="hi"` | `(INLINE, "hi")` — existing behavior |

#### New Tests for `capture_entry` with FILE mode

| Test | Input | Expected |
|------|-------|----------|
| `test_file_mode_dispatches` | `CaptureMode.FILE, "path"` | Calls `_capture_from_file("path")` |

### Integration Testing

**Manual verification steps:**

1. Create a test file: `echo "# Test Doc\n\nSome content" > /tmp/test-journal.md`
2. Run: `jarvis j --file /tmp/test-journal.md --title "Test File Capture" --no-deep-dive`
3. Verify AnyType entry contains: summary paragraph + `---` + full file content
4. Run: `jarvis j "Normal entry"` — verify existing behavior unchanged
5. Run: `jarvis j --file /nonexistent.md` — verify Click error message
6. Run: `jarvis journal list` — verify file-based entry appears in list

---

## 8. Implementation Order

| Step | Task | Depends On |
|------|------|------------|
| 1 | Add `CaptureMode.FILE` and `_capture_from_file` to `capture.py` | — |
| 2 | Add file summary prompt to `prompts.py` | — |
| 3 | Add `--file` flag and `_compose_file_entry` to `cli.py` | Steps 1, 2 |
| 4 | Update `_generate_docs()` in `cli.py` | Step 3 |
| 5 | Add tests to `tests/journal/test_capture.py` | Steps 1, 3 |
| 6 | Update plugin instructions in `jarvis.md` | Step 3 |

Steps 1 and 2 can be done in parallel. Step 6 is independent of tests.

---

## 9. Out of Scope

Per the product spec, these are explicitly excluded:

- Multiple files in one entry
- File watching / auto-journaling
- Stdin piping
- File format conversion
- Changes to journal list, read, search, or insights commands

---

*Created: Feb 10, 2026*
*Epic: 06_journal-file-capture*
*Based on: [Product Specification](./product_spec.md)*
