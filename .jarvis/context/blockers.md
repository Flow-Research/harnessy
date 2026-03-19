{{global}}

## Flow Network Blockers

### Current Blockers

1. **Bittensor subnet selection** — No subnet chosen yet. Need to research active subnets with clear AI/ML task formats, measurable quality, and reasonable reward rates. Blocks Phase 3.
2. **Jarvis agent runtime** — No `jarvis agent register/run` commands exist yet. Agent execution loop is prerequisite for operator agents. Blocks Phase 2.
3. **Jarvis global installation** — CLI only available via alias, not `uv tool install`. Minor friction for new contributors. (TD-003)

### Potential Blockers to Watch

- **Bittensor staking requirement** — Mining requires TAO stake. Amount varies by subnet. Need to budget.
- **Subnet task format variety** — Each subnet may define tasks differently. Decomposition function must be adaptable.
- **Operator compute costs** — If compute cost per task exceeds alpha token reward, economics fail. Must measure early.
- **Gateway complexity** — Security policy enforcement for operator agents could become complex. Start minimal.

### Resolved

- ~~Agent harness infrastructure~~ — Resolved via installation architecture (Phases 0-5). Skills, scripts, context vault all operational.
- ~~Stale context files~~ — Updated March 2026 to reflect POC focus.
