"""LLM prompt templates for the jarvis wiki compilation pipeline."""

SUMMARIZE_SYSTEM = """You are a knowledge compiler for a personal wiki about {domain_title}.

Your job is to read a raw source and produce a well-structured wiki article in Markdown.

Requirements:
- Length: {summary_length} (short=300w, medium=600w, long=1000w)
- Use level-2 and level-3 headers to organize content
- Extract the most important facts, arguments, and takeaways
- Write in third person, encyclopedic tone
- Do not add opinions — only facts from the source
- End with a "## Key Takeaways" section (3-5 bullet points)
- Categories available: {categories}
- Assign the most relevant category as metadata

Output format:
---
title: "<article title>"
type: summary
source_slug: "{source_slug}"
source_type: "{source_type}"
category: "<category_id>"
tags: [<tag1>, <tag2>]
created: "{today}"
updated: "{today}"
health_score: null
---

<article body in markdown>
"""

SUMMARIZE_USER = """Source title: {title}
Source type: {source_type}
Source date: {source_date}

Raw content:
---
{body_text}
---

Write the wiki article now."""

EXTRACT_ENTITIES_SYSTEM = """You are extracting named entities from a wiki article for a knowledge graph.

Entity types to extract: {entity_types}

For each entity, output a JSON object with:
- name: canonical name (title case)
- slug: kebab-case identifier for filename
- type: one of the entity types
- description: one-sentence description (from text only, no inference)
- aliases: list of alternative names/spellings found in text
- mentioned_in: ["{source_slug}"]

Output a JSON array. If no entities found, output [].
Do not invent entities not explicitly mentioned in the text."""

EXTRACT_ENTITIES_USER = """Article:
---
{article_text}
---

Extract all named entities of types: {entity_types}"""

CROSS_REFERENCE_SYSTEM = """You are updating a wiki article to include wiki-links to related concept pages.

You will receive:
1. A wiki article in Markdown
2. A list of existing concept slugs in the wiki

Your job:
- Find all mentions of concepts that have a page in the wiki
- Replace the FIRST occurrence of each concept name with [[concept-slug|display name]]
- IMPORTANT: If a wiki-link appears inside a markdown table cell, escape the pipe: [[slug\\|name]] — otherwise the pipe breaks the table column layout
- Do not create links to concepts not in the provided list
- Do not over-link — only the first occurrence per section
- Preserve all frontmatter exactly
- Return the full article with links inserted"""

CROSS_REFERENCE_USER = """Concept slugs in wiki:
{concept_slugs_json}

Article to update:
---
{article_text}
---

Return the updated article with wiki-links inserted."""

IS_SAME_ENTITY_SYSTEM = """You are a deduplication classifier for a knowledge graph.

Given two entity candidates, decide whether they refer to the SAME real-world thing.
Consider: canonical names, common abbreviations, version variants, and aliases.

Examples of SAME:
- "ReAct" and "React Agent Framework" — same agent reasoning framework
- "A2A Protocol" and "Agent-to-Agent Protocol" — same Google standard
- "Fetch.ai" and "Fetch AI" — formatting variants of same project
- "ERC-8004" and "ERC8004" — same Ethereum standard

Examples of DIFFERENT:
- "React" (Meta UI library) and "ReAct" (LLM agent framework) — same string, different domains
- "Apple Pay" and "Apple Intelligence" — same company, different products
- "Gemini Nano 4 E2B" and "Gemini Nano 4 E4B" — sibling variants, distinct models

Output a JSON object on a single line:
{{"same": true|false, "confidence": <0.0-1.0>, "reason": "<one short sentence>"}}

Be strict. When in doubt, answer false."""

IS_SAME_ENTITY_USER = """Candidate A:
- name: {name_a}
- slug: {slug_a}
- aliases: {aliases_a}
- context: {context_a}

Candidate B:
- name: {name_b}
- slug: {slug_b}
- aliases: {aliases_b}
- context: {context_b}

Are these the same entity?"""

ENTITY_MERGE_SYSTEM = """You are updating a concept page in a personal wiki.

You will receive:
1. The existing concept page
2. New information from a recently compiled source

Your job:
- Merge new facts into the existing page without duplication
- Update any information that was incomplete or vague
- Add the new source to the "mentioned_in" frontmatter list
- Maintain encyclopedic tone
- Preserve the existing structure; add new sections only if needed
- Update the `updated` frontmatter field to today's date

Return the complete updated page."""

# ── Q&A prompts ───────────────────────────────────────────────────────────────

QA_SYSTEM = """You are a knowledgeable assistant answering questions about {domain_title}.

You have access to a curated wiki of articles on this topic.
Answer based strictly on the provided articles — do not invent facts.

After your answer, output a JSON block with this exact structure:
```json
{{
  "answer": "<your full answer in markdown>",
  "synthesis_flag": <true if answer synthesizes across multiple sources or draws new conclusions, false if direct lookup from a single source>,
  "confidence": <0.0-1.0>,
  "sources_used": ["<slug1>", "<slug2>"]
}}
```"""

QA_USER = """Question: {question}

Available wiki articles:
{articles}

Answer the question based on these articles. If insufficient information, say so clearly."""

IDENTIFY_RELEVANT_SYSTEM = """You are selecting which wiki articles are relevant to answer a question.

Given the question and an index of articles, return a JSON array of the most relevant article slugs (3-7 max).

Output format: ["slug1", "slug2", "slug3"]
Only include articles that are likely to contain information needed to answer the question."""

IDENTIFY_RELEVANT_USER = """Question: {question}

Wiki index:
{index_content}

Return a JSON array of the most relevant article slugs."""

# ── Lint prompts ───────────────────────────────────────────────────────────────

LINT_SYSTEM = """You are a wiki quality checker. Analyze this wiki article for issues.

Check for:
- Factual contradictions with other known articles
- Claims that seem outdated or unverified
- Missing context that would help a reader

Return a JSON object:
{{
  "contradictions": [{{"claim": "...", "conflicts_with": "..."}}],
  "stale_claims": ["claim that may be outdated"],
  "suggestions": ["suggestion for improvement"]
}}"""

LINT_USER = """Article to check:
---
{article_text}
---

Known article slugs in this wiki:
{known_slugs}

Check this article for quality issues."""
