# Text Hygiene for Generated Human-Readable Artifacts

After creating or updating Markdown/text intended for a human reader, run:

```bash
jarvis text-hygiene clean <generated-file-or-folder> --report
```

Use this for README files, PRDs, design specs, technical specs, review reports,
life plans, daily briefs, and content drafts. The cleaner removes configured
AI-speak phrase and regex patterns while skipping YAML frontmatter, fenced code
blocks, and inline code.

Personal patterns live at:

```text
.jarvis/context/private/${FLOW_USER:-${USER}}/style/ai-speak-patterns.yaml
```

For check-only gates, use:

```bash
jarvis text-hygiene check <generated-file-or-folder>
```
