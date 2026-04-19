---
description: Manage wiki knowledge bases — ingest, compile, ask, lint, search, open, export
argument-hint: "[ingest|compile|ask|lint|search|status|open|export|enhance] [args]"
---

# /wiki

Routes to the jarvis-wiki skill. Dispatches subcommands to `jarvis wiki <subcommand>`.

## Routing

- `/wiki ingest <url|path> -d <domain>` → ingest raw source
- `/wiki compile -d <domain>` → compile raw sources to wiki
- `/wiki ask "<question>" -d <domain>` → Q&A against wiki
- `/wiki lint -d <domain>` → health checks
- `/wiki search "<query>" -d <domain>` → grep wiki content
- `/wiki enhance -d <domain>` → improve articles
- `/wiki status [--all]` → show domain status
- `/wiki open -d <domain>` → open in Obsidian
- `/wiki export -d <domain>` → package wiki
- `/wiki` (no args) → show status for all domains
