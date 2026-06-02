---
name: content-review
description: "Review articles, posts, and publishing drafts against supplied research, facts, audience needs, editorial quality, and a caller-provided strategy profile. Use when content needs fact-checking, anti-robotic-language cleanup, coherence review, accessible explanations for general audiences, or alignment with project/campaign context provided at runtime."
disable-model-invocation: true
allowed-tools: Read, Write, ApplyPatch, Grep, Glob, Bash
argument-hint: "<article-path> --profile <profile.yaml> [--mode report|edited|patch]"
---

# Content Review

## Purpose

Review publishable content before it goes out. The skill checks factual grounding, source quality, coherence, audience accessibility, terminology, math/numerical clarity, voice, and alignment with the strategy context supplied at runtime.

The skill is project-agnostic. It must not infer the project, product, partner, audience, voice, or canonical framing from the repository name or from this skill's source. Load those details only from an explicit profile, explicit context files, or the user's prompt.

## Inputs

- Article draft path or pasted draft text.
- Review profile path, or explicit context/source files plus target audience.
- Optional output mode:
  - `report` returns only the review report.
  - `edited` returns a revised draft plus review report. This is the default.
  - `patch` edits the source file and writes/updates the review report.
- Optional destination for review artifacts.

- Template paths are resolved from `${AGENTS_SKILLS_ROOT}/content-review/`.

## References

Load these only when needed:

- `${AGENTS_SKILLS_ROOT}/content-review/references/editorial-standard.md` for the review rubric.
- `${AGENTS_SKILLS_ROOT}/content-review/references/profile-contract.md` for runtime profile shape.
- `${AGENTS_SKILLS_ROOT}/content-review/templates/review-report.md` when writing a review artifact.

## Steps

1. Confirm the review has an explicit profile or explicit context files. If neither is supplied, stop and ask for them. Do not choose project context implicitly.
2. Read the draft and the supplied profile/context. Record the exact files consulted in the report.
3. Identify the intended audience and assumed knowledge level. If absent, default to `general` and `mixed`.
4. Extract claims that need verification:
   - numbers, dates, prices, metrics, and timelines
   - customer, partner, legal, regulatory, funding, or market claims
   - technical performance, benchmark, architecture, security, or compatibility claims
   - claims about current status, releases, leadership, pricing, policies, or availability
5. Ground claims against supplied sources first. Use web research for external or time-sensitive facts, and cite sources used. If a claim cannot be verified, mark it as `needs source`, `soften`, or `remove`.
6. Review strategy alignment strictly against the supplied profile:
   - required framings are present when relevant
   - forbidden or stale framings are removed
   - terminology matches the profile
   - uncertainty is stated where the profile says the position is unsettled
7. Review audience digestion:
   - identify the one-sentence main message; if it is missing or buried, rewrite the opening around it
   - explain unfamiliar terms before relying on them
   - expand acronyms on first use unless the profile says the audience already knows them
   - replace jargon stacks with plain-language explanations or short examples
   - reduce insider shorthand
   - walk through calculations step by step before presenting conclusions
   - make any formula readable by defining each variable in ordinary language
   - for threads, slides, carousels, or short-form posts, ensure each numbered item can be understood without waiting several items for context
   - make the thesis and transitions clear
   - preserve nuance without requiring private context
8. Remove robotic or generic language:
   - replace hype, filler, and vague abstractions with concrete statements
   - avoid over-polished announcement voice unless the profile explicitly asks for it
   - preserve the author's intent and factual meaning
9. Produce the requested output:
   - `report`: review report only
   - `edited`: edited draft plus review report
   - `patch`: apply a narrow patch to the draft and write/refresh the review report
10. Before marking the content ready, state publish blockers separately from non-blocking improvements.

## Decision Trace Protocol

When this skill is used repeatedly, capture recurring quality issues as feedback for future improvement. Do not expose trace internals in user-facing content unless asked.

Quality gates:

- `factual_grounding_gate`: pass only when high-risk factual claims are sourced, softened, or removed.
- `audience_clarity_gate`: pass only when a general or mixed audience can follow the article without hidden context.
- `terminology_accessibility_gate`: pass only when jargon and acronyms are explained before they are used to carry the argument.
- `numerical_clarity_gate`: pass only when calculations, percentages, formulas, and comparisons are explained in steps an average reader can follow.
- `main_message_gate`: pass only when the reader can state the content's main point after the opening section or first numbered item.
- `strategy_alignment_gate`: pass only when alignment is based on the supplied profile, not unstated assumptions.

## Output

Default output is:

1. Edited draft.
2. Review report with:
   - consulted context and sources
   - fact-check findings
   - strategy-alignment findings
   - clarity/coherence findings
   - terminology/acronym findings
   - numerical clarity findings
   - main-message finding
   - voice edits
   - publish blockers
   - recommended next action

Never automatically publish content. Never patch source files unless `patch` mode is explicitly requested.
