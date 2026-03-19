{{global}}

## Flow Network Delegation

### Current Team Structure (March 2026)

| Track | Lead | Focus |
|---|---|---|
| Agent / Jarvis | Rise + team | Agent runtime, Jarvis CLI, skills, personal operators |
| Bittensor / Blockchain | Gbolahan + Ojogo | Subnet mining, smart contracts, reward mechanics |
| Platform | TBD | WorkStream UI, earnings dashboard, onboarding |
| Julian | Julian | Architecture, orchestrator design, coordination, context |

### Delegation Principles

**Delegate:**
- Frontend React development (earnings dashboard, WorkStream UI)
- Bittensor subnet research and miner registration
- Test coverage expansion (POC at 56% backend, needs 99%)
- Operator agent implementation (once runtime loop exists)
- CI/CD and deployment automation

**Keep ownership of:**
- Core architecture decisions (orchestrator design, gateway, context separation)
- Economic model (reward distribution, value attribution, Flow Score)
- Agent framework design (runtime loop, skill-task mapping)
- Security-critical code (gateway policies, operator sandboxing)
- Protocol specifications and roadmap

### Coordination Pattern

- Agent team and Bittensor team work in parallel
- Integration points: orchestrator ↔ Bittensor API, operator ↔ task queue
- Weekly sync on blockers and architecture decisions
- All decisions recorded in `.jarvis/context/decisions.md`
