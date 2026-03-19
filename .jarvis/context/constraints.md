{{global}}

## Flow Network Constraints

### POC Constraints (Current — March 2026)

- Single orchestrator instance (no orchestrator pool)
- Single Bittensor subnet for initial validation
- Handful of test operators (not scaled deployment)
- Centralized reward distribution (Flow captures alpha tokens, converts, distributes)
- Local machine compute only (no cloud TEE yet)
- Wallet-based auth only (MetaMask, WalletConnect, Coinbase Wallet)

### Technical Constraints

- **Backend:** Python 3.11+ / FastAPI (POC). Rust P2P engine paused.
- **Frontend:** React 18 / Vite / wagmi (wallet connect)
- **Database:** PostgreSQL 15 (Docker) with SQLAlchemy 2.0 async
- **Blockchain:** Base Sepolia (testnet). Solidity / Foundry.
- **Jarvis CLI:** Python, `uv` for dependency management
- **Skills:** OpenCode plugin format, registered to `~/.agents/skills/`

### Performance Targets (POC)

- Agent task pickup: <5s from availability
- Task execution: varies by skill (target <60s for simple tasks)
- Orchestrator round-trip (task → decompose → assign → aggregate → submit): <5min
- Zero data loss on task results

### Timeline Constraints

- POC validation: 6-8 weeks from March 2026
- Must demonstrate positive unit economics (reward > compute cost) to proceed to Phase 2

### Flow Core (Rust) Constraints — Paused

- Rust stable toolchain, libp2p networking, RocksDB block storage
- Phase 3 ~95% complete. Resumes after POC validates economic model.
