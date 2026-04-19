# Wiki Content Standard

## Purpose

Codify formatting rules for Jarvis wiki content so that LLM-compiled articles, index pages, and concept pages render correctly across Obsidian, VS Code preview, GitHub, and any standard markdown renderer.

## Rules

### 1. Wiki-links in Markdown Tables

**Problem:** Obsidian wiki-links use `[[slug|display name]]` where `|` separates slug from display text. Markdown tables also use `|` as the column delimiter. Unescaped wiki-links inside table cells break the table layout.

**Rule:** Always escape the pipe character with a backslash inside wiki-links that appear in table cells.

```markdown
# Wrong — breaks the table
| [[erc-8004|ERC-8004]] | description |

# Correct — renders properly
| [[erc-8004\|ERC-8004]] | description |
```

**Applies to:**
- `index_builder.py` — auto-generated index tables
- Any LLM prompt that asks the model to produce wiki-links inside tables
- Manual edits to wiki articles that include tables with links

### 2. Wiki-link Format in Article Bodies

Wiki-links in running prose (outside tables) use the standard unescaped format:

```markdown
The [[erc-8004|ERC-8004]] standard defines agent identity primitives.
```

No escaping needed — the `|` is unambiguous outside table context.

### 3. Concept Page Frontmatter

Every concept page must include YAML frontmatter with at minimum:

```yaml
---
title: "Concept Name"
type: concept
entity_type: concept | person | organization | location
mentioned_in:
  - source-slug-1
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

### 4. Summary Page Frontmatter

Every summary must link back to its raw source:

```yaml
---
title: "Article Title"
type: summary
source_slug: "raw-source-slug"
source_type: "article | paper | note"
---
```

### 5. Cross-Reference Linking

When the compilation pipeline inserts wiki-links via cross-referencing:
- Link only the **first occurrence** of each concept per section
- Do not link concepts in headings or frontmatter
- Do not create links to concepts that don't have a page in the wiki

## Enforcement

- `index_builder.py` enforces Rule 1 programmatically
- `lint.py` checks for broken wiki-links and orphaned pages
- LLM prompts in `prompts.py` should reference these rules when generating content with wiki-links in tables
