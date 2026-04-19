---
name: jarvis-wiki
description: >
  Use when the user wants to manage their personal knowledge base: ingest a URL or file,
  compile wiki articles, ask questions about a domain, run lint, or open in Obsidian.
  Trigger on: "add to wiki", "compile wiki", "what does my wiki say", "lint wiki".
disable-model-invocation: false
allowed-tools: Read, Write, Bash, Glob, Grep, WebFetch
argument-hint: "[ingest <source> -d <domain> | compile -d <domain> | ask '<q>' -d <domain> | lint -d <domain> | status | open -d <domain>]"
---

# Jarvis Wiki Skill

Manages LLM-compiled personal knowledge base domains.

## Purpose

The wiki system maintains structured knowledge domains (e.g. seas, accelerate-africa).
Raw sources (articles, PDFs, notes) are compiled into wiki articles via LLM.
This skill allows the agent to manage the wiki without the user typing CLI commands.

## Steps

1. **Determine intent**: ingest / compile / ask / lint / status / open / search / enhance / export
2. **Identify domain**: check `jarvis wiki status --all` if ambiguous
3. **Run CLI**: execute `jarvis wiki <subcommand>` via Bash tool
4. **Verify**: read resulting wiki file or log entry to confirm success
5. **Report**: summarize what was created/updated

## Behavior Notes

- For `ingest` from a URL: `jarvis wiki ingest <url> -d <domain>`
- For `ask`: pass question as string, display answer inline
- For `compile`: use `--verbose` so the user sees progress
- For `lint`: display the report inline
- When domain is unclear: run `jarvis wiki status --all` first

## Example Invocations

```bash
jarvis wiki ingest https://example.com/article -d seas --compile-now
jarvis wiki compile -d seas --verbose
jarvis wiki ask "What trades did the March meeting discuss?" -d seas
jarvis wiki lint -d seas
jarvis wiki search "apprenticeship" -d seas
jarvis wiki open -d seas
jarvis wiki export -d seas -f zip
jarvis wiki status --all
```
