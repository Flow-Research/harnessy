{{global}}

## Flow Network Goals

### Current Sprint (March 2026 — 2-week cycles)

**Sprint 1 Objectives (Roadmap Phase 1 + Phase 2 start):**
- [x] Installation architecture — skills, scripts, context vault, AGENTS.md (Phases 0-5 done)
- [x] Fix stale context files and consolidate roadmap
- [ ] Resolve Jarvis CLI global installation (`uv tool install`)
- [ ] Fork OpenClaw and get a baseline Jarvis agent running
- [ ] Implement `jarvis agent register` — writes to Supabase `agent_registry`
- [ ] Implement agent heartbeat loop
- [ ] Begin Bittensor subnet research — select first target subnet

**Sprint 2 Objectives (Roadmap Phase 2 + Phase 3 start):**
- [ ] Implement `jarvis agent run` — execution loop (fetch task → load skill → execute → report)
- [ ] Skill-task mapping configuration
- [ ] Implement gateway (security config, channel routing, session binding)
- [ ] Register as miner on chosen Bittensor subnet
- [ ] Task decomposition function (subnet task → sub-tasks)

### POC Goals (6-8 weeks from March 2026)

- [ ] Orchestrator mines at least one Bittensor subnet end-to-end
- [ ] Personal operators claim and execute decomposed tasks from WorkStream
- [ ] Gateway enforces security policies across all agent instances
- [ ] Alpha token rewards flow back to operator wallets
- [ ] Users can track earnings through a basic platform UI
- [ ] **Measure:** average earnings per agent per day, task completion rate, submission quality
- [ ] **Validate three properties:** (1) reliable orchestrator, (2) quality submissions, (3) sustainable incentives

### Phase Milestones

| Phase | Goal | Timeline |
|---|---|---|
| Phase 1: Foundation | Clean workspace, global Jarvis install, stale fixes | This week |
| Phase 2: Agent Runtime | Register, heartbeat, task queue, execution loop | Weeks 1-2 |
| Phase 3: Bittensor | Mine 1 subnet, capture rewards | Weeks 2-3 |
| Phase 4: Operators | Personal operator agents claim and execute tasks | Weeks 3-4 |
| Phase 5: Earnings | Contribution tracking, earnings ledger, basic UI | Weeks 4-6 |
| Phase 6: Scale | Multi-agent, GitHub integration, multi-subnet | Weeks 6-8+ |

### Flow Core (Rust) Goals — Paused
- [ ] Complete Phase 3 remaining items (LiveQuery integration)
- [ ] Begin Phase 4: Agent Framework (SLRPA components)
- Resumes after POC validates the economic model
