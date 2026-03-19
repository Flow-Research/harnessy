# Flow POC Kickoff Meeting

**Date:** 2026-03-14 (Saturday)
**Duration:** 122 minutes
**Recording:** https://fathom.video/share/du4ATWHE3qiHi4XuhyDve8UzskGLHkTR
**Facilitator:** Julian Duru

## Attendees

| Name | Role | Present |
|------|------|---------|
| Julian Duru | Project lead, architecture | Full |
| Gbolahan Adebayo | Bittensor/blockchain lead | Full (intermittent network) |
| Rise Man | Agent/Jarvis team lead | Full |
| Olayinka Koleaje (Tobi) | Agent team | Full |
| Abiola Adeshina | Agent team | Full |
| Blessing Mba (Nina) | TBD assignment | Full |
| Paul Oamen | Observer | Partial (joined late) |
| Nkang Precious | Observer | Partial |
| Ojogo | Bittensor team (with Gbolahan) | Not on call |

## Summary

Transition meeting from research/planning phase to active development. Reviewed the full system architecture, value flow, and component ownership. Agreed to start 2-week sprint cycles and fork OpenClaw to get first Jarvis agent running.

## Key Decisions

1. **Sprint cadence adopted:** 2-week sprints starting immediately. Track on AnyType Kanban.
2. **Start building now:** Consensus from all participants that enough research is done; clarity will come from building.
3. **First action:** Fork OpenClaw and get a baseline Jarvis agent running.
4. **Reward distribution strategy:** Start with centralized management (Flow captures alpha tokens, converts to familiar currency for users), evolve toward decentralized direct distribution later.
5. **Architecture flexibility:** Task distribution and claiming mechanisms should be designed to be easily swappable.
6. **Orchestrator scaling:** Single instance for POC; design with pool scaling in mind for later.
7. **Team balance:** Julian and Gbolahan to finalize team assignments by Monday, ensuring balance across agent and Bittensor tracks.

## Architecture Review

### Three Pillars of the System
Gbolahan walked through the system architecture:
1. **Agent protocol** (Jarvis) -- Personal AI agents doing work on behalf of users
2. **Platform** (WorkStream) -- User-facing layer for tracking agent activity and earnings
3. **Economic value source** (Bittensor) -- Where the money comes from

### Bittensor Participation Model
- Flow operates as a **miner** on Bittensor subnets (not subnet owner, not validator)
- Reasons: Subnet creation too complex for now; validator role doesn't align with compute model; mining lets us abstract complexity from users
- Currently 129 subnets on Bittensor, mostly AI/ML use cases
- Orchestrator mines **across multiple subnets**, not just one

### Value Flow
1. Bittensor subnet users submit tasks (pay via TAO/alpha tokens)
2. Subnet validators distribute tasks to miners
3. Our orchestrator (miner) receives tasks
4. Orchestrator decomposes into sub-tasks, posts to WorkStream
5. Personal operators claim and execute tasks
6. Orchestrator aggregates results, submits to subnet
7. Alpha token rewards flow back
8. Flow takes operational cut, distributes remainder to users

### Alpha Token Economics
- Not pegged to fiat -- fungible, swappable to TAO or USDC
- TAO ~$200 per token; alpha tokens vary ($7-9 depending on subnet)
- Supply capped at 21M per subnet with burn mechanics
- Value accrues based on subnet demand and burn/recycle dynamics

### Three Required Properties
Gbolahan identified three properties the system must guarantee:
1. **Reliable orchestrator** -- Always sources tasks and distributes them (liveness)
2. **Quality submissions** -- Operators produce work that passes subnet validation
3. **Sustainable incentives** -- Rewards exceed operator compute costs (e.g., if running costs $10/day, rewards must cover that + margin)

### Gateway Clarification
Rise explained the gateway concept:
- **Not a running service** -- It's a policy/configuration layer that defines how all Jarvis instances behave
- Covers: secure configuration, channel routing, session binding, operator-orchestrator integration
- Extends OpenClaw's generic gateway with Flow-specific additions (wallet connection, operator policies)
- Same gateway policies apply to all users, but users can customize within bounds

### WorkStream Design
- Conceptualized as a **mempool-like environment** (inspired by blockchain mempools)
- Tasks posted by orchestrator, operators claim from the pool
- Fair distribution mechanisms TBD (exclusive claim vs competitive, matching by capability)
- Architecture should remain flexible -- easy to change distribution strategy later

### Target Users
- Initial focus: People with AI/ML knowledge (students learning ML, trainable contributors)
- Tasks bounded to what Bittensor subnets provide (mostly AI training)
- Progressive expansion: As subnets diversify, so does the task pool
- Long-term: Creative freedom across sports, cooking, arts, etc.

## Roadmap Checklist (Grouped by Team)

### Agent/Jarvis Team (Rise)
- Gateway implementation (security config, channel routing, session binding)
- Security (protocol-wide agent security)
- X402 integration (payment protocol for personal operators)
- Orchestrator agent (mining service, also an agent on Jarvis framework)
- VM sandboxing (EigenCloud for verifiable compute + TEEs)

### Bittensor/Blockchain Team (Gbolahan + Ojogo)
- Subnet research and integration specification
- Orchestrator-Bittensor connection
- Task pipeline (decomposition algorithms, output aggregation)
- Smart contracts for reward distribution

### Platform Team (TBD)
- WorkStream UI (task visibility, earnings tracking)
- Roadmap pending -- team to produce their own roadmap

## Action Items

| Action | Owner | Deadline |
|--------|-------|----------|
| Post 2-week sprint commitments to WhatsApp group | Everyone | ASAP (same day preferred) |
| Fork OpenClaw and get baseline agent running | Rise / Agent team | Sprint 1 |
| Finalize team assignments and balance | Julian + Gbolahan | Monday Mar 16 |
| Clean up AnyType Kanban board | Julian + Gbolahan | Before Monday |
| Move sprint commitments to Kanban | Gbolahan | After commitments posted |
| Share AnyType invite links | Gbolahan | Same day |
| Download AnyType app | All team members | Same day |
| Bittensor subnet research | Gbolahan + Ojogo | Sprint 1 |
| Platform team roadmap | TBD (Bright mentioned) | Sprint 1 |

## Open Questions (Parked)

- Should each Jarvis instance mine independently vs centralized orchestrator? (Parked -- too complex for now, revisit at scale)
- Exact unit economics: What does an agent earn per day? (Must be answered empirically through building and testing)
- How does Jarvis map user skills to available subnet tasks? (Progressive -- bounded to available subnets initially)
- Task decomposition algorithms -- what functions/approaches? (TBD during implementation)
- Smart contract vs off-chain for reward splitting? (Leaning smart contract, TBD)

## Team Understanding Check

Julian conducted a round-the-table check on understanding:
- **Gbolahan:** Full clarity on architecture and roadmap
- **Rise:** Full clarity, ready to build
- **Tobi:** Reviewed design brief, got clarity during meeting (initially confused about Jarvis-WorkStream relationship)
- **Nina (Blessing):** Working through roadmap, on track but balancing with other work
- **Abiola:** Fair understanding -- grasps the orchestrator-to-operator flow and token distribution concept
- **Paul:** Joined late, no verbal update
