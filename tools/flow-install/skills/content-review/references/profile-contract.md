# Review Profile Contract

A review profile injects project, campaign, publication, or partner context at runtime. The skill source must stay generic; profile files hold strategy-specific truth.

## Minimal Profile

```yaml
name: project-or-campaign-name
audience:
  primary: general
  assumed_knowledge: mixed
context_files:
  - path/to/strategy.md
source_files:
  - path/to/research-or-notes.md
voice:
  preferred:
    - direct
    - specific
    - grounded
  avoid:
    - hype
    - robotic phrasing
claims:
  require_sources_for:
    - numbers
    - dates
    - legal claims
    - funding claims
    - customer or partner claims
    - market claims
    - technical performance claims
required_framings:
  - current canonical phrase or idea
forbidden_framings:
  - stale or incorrect phrase
```

## Field Guidance

- `name`: Label for reporting only. Do not use it as implicit strategy context.
- `audience.primary`: Main reader group for this review.
- `audience.assumed_knowledge`: Use `beginner`, `mixed`, or `expert`.
- `context_files`: Strategy, positioning, status, voice, roadmap, or meeting files used for alignment.
- `source_files`: Research notes, source packs, transcripts, or cited materials used for fact checking.
- `voice.preferred`: Qualities to preserve or introduce.
- `voice.avoid`: Phrases, tones, or writing habits to remove.
- `claims.require_sources_for`: Claim categories that must have source support.
- `required_framings`: Current canonical ideas that should appear when relevant.
- `forbidden_framings`: Stale, inaccurate, risky, or off-strategy framings.

## Runtime Rules

- A missing profile is a blocker unless the user supplies equivalent context in the prompt.
- Missing context files are blockers.
- Missing source files are blockers only when the draft depends on them.
- If a profile conflicts with a source file, report the conflict and prefer the profile for positioning, but prefer primary/current sources for factual claims.
- If the user asks for patch mode, patch only the draft, not profile or source files.
