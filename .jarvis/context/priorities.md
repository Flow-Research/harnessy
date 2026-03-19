{{global}}

## Flow Network Priorities

### Project Priority (High to Low)

1. **Example Platform POC** — Validate value flow end-to-end (Bittensor → orchestrator → operators → rewards)
2. **Jarvis CLI** — Agent runtime commands (`agent register/run`), global installation
3. **Example Core (Rust)** — Paused until POC validates economic model
4. **Knowledge Base** — Brainstorming, no active development

### Roadmap Phase Priority

1. **Phase 2: Agent Runtime** — Core execution loop is prerequisite for everything else
2. **Phase 3: Bittensor Integration** — Must mine a subnet to validate the economic thesis
3. **Phase 4: Personal Operators** — Users need agents that work on their behalf
4. **Phase 5: Earnings & Measurement** — Validate unit economics, build trust with numbers
5. **Phase 6: Multi-Agent & Scale** — Only after single-agent POC is validated

### Task Type Priority (POC)

1. **End-to-end integration** — Get the full loop working, even if rough
2. **Architecture decisions** — Settle open questions (subnet selection, reward distribution, task decomposition)
3. **Core components** — Agent runtime, orchestrator, gateway, operator
4. **Testing + measurement** — Validate economics (earnings per agent, cost vs revenue)
5. **Documentation** — Keep architecture docs current as we learn

### When Priorities Conflict

- POC work takes precedence over all other projects
- Agent team and Bittensor team work in parallel, coordinate at integration points
- Build the simplest version that validates the value flow first, then iterate
- Layer 4 (Content) and Layer 5 (Advanced) are deferred — do not pull them forward
