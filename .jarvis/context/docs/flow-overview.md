# Flow: What We Are Building

**March 2026**

## The Short Version

Flow gives every person a personal AI agent that earns money on their behalf.

The agent finds work, executes tasks, builds a track record, and deposits earnings into its human's account. The human guides, approves, and takes on harder work as the agent matures. Over time, the pair moves into higher-paying, more complex assignments together.

## The Problem

**AI can now do real work.** Large language models write code, analyze data, synthesize research, classify images, and generate content at production quality. But most people have no way to economically benefit from this capability. AI remains a tool for those who already have high-paying jobs. Existing platforms like Remotasks and Toloka provide some access to AI-adjacent work (data labeling, annotation), but the tasks are narrow, the pay is low, and there is no skill progression or agent leverage.

**Demand for AI-powered execution is growing fast.** Bittensor runs 129 active subnets, each paying miners to complete AI and ML tasks. The network distributed over $50M in token rewards to miners in 2025. Beyond Bittensor, the broader market for outsourced AI-enabled operations is expanding as enterprises seek flexible execution capacity for cognitive work.

**Hundreds of millions of capable people have no path in.** Particularly in Africa and the Global South, talented individuals are locked out by the absence of on-ramps: no credentials, no platform access, no structured path from potential to paid work. Flow addresses the distribution and matching layer directly.

## What Flow Does

Flow routes external demand for AI work through a network of human-agent pairs.

1. An **Orchestrator** connects to external sources of paid work. The first source is Bittensor, a decentralized network where subnet operators pay miners to complete AI tasks. The Orchestrator registers as a miner, receives tasks, and earns token rewards for successful submissions.
2. The Orchestrator **decomposes** complex tasks into smaller units suitable for individual execution. A research synthesis task might become five separate sub-tasks: literature retrieval, summarization, fact-checking, citation formatting, and final assembly. Task decomposition is a core technical challenge. The POC starts with LLM-based splitting reviewed by humans. Decomposition strategies will evolve as we learn which patterns maximise validator acceptance rates.
3. These sub-tasks are posted to the **WorkStream**, a task exchange where personal agents discover and claim work.
4. Each user has a **Personal Operator**: a persistent AI agent, built on Jarvis (our agent runtime), that acts on the user's behalf. The operator claims tasks that match the user's skills and interests, executes them using AI capabilities and the user's context, and submits results.
5. The Orchestrator **aggregates** operator outputs, runs quality checks against the subnet's validation criteria, and assembles them into a complete submission. The QA layer returns flagged results for rework or reassigns them to a different operator before the aggregate is submitted externally.
6. Rewards flow back through the system. Flow takes a platform fee (target: 15-25%, comparable to managed service platforms). The remainder is distributed to the users whose operators completed the work. Users see earnings in local currency.

## The Personal Operator

The Personal Operator is a durable economic unit tied to a specific human being. It has its own identity, capabilities, and reputation. It takes work, requests human input when it needs help, and builds trust over time. As it completes more tasks successfully, it earns access to harder, more valuable assignments.

The human is the principal. The operator is the productive unit. The agent holds its own reputation, accrues a track record, and operates while the human sleeps. The human decides how much autonomy to grant, reviews work when needed, and benefits from the agent's growing capability.

For the user, this feels simple. The agent surfaces available work, completes what it can, flags what it cannot, and reports earnings.

**Sybil resistance:** One human, one operator. Identity verification at onboarding (initially phone-based, evolving to stronger mechanisms) prevents users from running multiple operators to game the reputation system. Operator data belongs to the user; the platform retains aggregate quality metrics.

## How Money Flows

```
External demand (Bittensor subnets, enterprise clients)
  -> Orchestrator receives tasks, earns token rewards
    -> Tasks decomposed and posted to WorkStream
      -> Personal Operators claim and execute sub-tasks
        -> Quality checks before aggregation
          -> Orchestrator submits to external source
            -> Rewards distributed: platform fee + user earnings
```

The first external demand source is Bittensor. Subnet users submit AI tasks and pay in alpha tokens (a subnet-specific currency convertible to TAO, the network's base token). Flow mines these subnets, captures rewards, and distributes value downstream. Bittensor is the bootstrap: it provides paid demand from day one without requiring Flow to build its own buyer base. Enterprise clients, other decentralized networks, and internal marketplace demand are future channels.

**Currency conversion:** Alpha token rewards follow a conversion chain: alpha tokens to TAO (on-chain swap), TAO to USDC (via centralized or decentralized exchange), USDC to local currency (via licensed fiat off-ramp partners). Realistic total conversion friction is 5-8%, absorbed into the platform fee. Crypto-to-fiat regulation varies by jurisdiction; we are starting with markets where mobile money rails and licensed crypto exchanges already operate (Kenya, Ghana, South Africa).

## Rough Unit Economics

These are estimates. The POC exists to test them.


| Variable                              | Estimate         | Source / Assumption                                               |
| ------------------------------------- | ---------------- | ----------------------------------------------------------------- |
| Alpha token reward per task           | $3-15            | Varies by subnet; mid-range subnets on Bittensor                  |
| Compute cost per task (LLM inference) | $0.10-0.50       | Based on Claude/GPT API pricing at current task complexity        |
| QA cost per task (human spot-check)   | $0.05-0.20       | Team-performed at POC scale; automated at production scale        |
| Tasks per operator per day            | 10-50            | Depends on task complexity and operator autonomy                  |
| Platform fee                          | 15-25%           | Includes conversion costs; in line with managed service platforms |
| Gross earnings per operator per day   | $5-50            | Wide range reflects subnet and task-type variance                 |
| Net to user (after platform fee)      | ~70-80% of gross | Target                                                            |


The $5-50/day range is deliberately wide. The POC's purpose is to narrow it. The go/no-go threshold: if median operator gross earnings fall below $5/day at 20+ tasks/day, the model does not work for our target users and we must pivot subnet selection or task strategy. For context, $5/day is approximately 2x the median daily wage for informal work in Nigeria and Kenya. The target is $15-25/day within 90 days of operator activation.

## What Users Experience

The target experience (not the current state; see "Current State" below for what exists today):

Our first target user is a university-educated young professional in Lagos or Nairobi with a smartphone, stable mobile internet, and English proficiency. They have skills (data analysis, writing, research) but limited access to platforms where those skills are valued. They are comfortable with mobile apps and digital payments.

This user opens Flow, meets their personal assistant (Jarvis), sets up a profile based on their skills and interests, and starts receiving matched work. The first tasks are small and well-scoped. Completion is fast. Earnings arrive within hours of task validation.

Over time, the system learns what the user is good at. Tasks get harder, more interesting, and better paid. The user's reputation grows. Their operator becomes more capable and more autonomous. The user delegates more, reviews less, and takes on work they could not have attempted alone.

## Quality Assurance

Quality is the mechanism that makes the entire value chain work. If operator outputs fail subnet validation, rewards are zero.

**Pre-submission QA:**

- Each sub-task result is validated against the subnet's published acceptance criteria before aggregation
- Automated checks (format compliance, completeness, coherence scoring) catch low-quality outputs early
- The QA layer returns flagged results for rework or reassigns them to a different operator

**Operator reputation:**

- Operators that consistently produce accepted work earn higher reputation scores
- Higher reputation unlocks access to higher-value tasks and greater autonomy
- Operators with declining quality are throttled to simpler tasks or paused

**Human-in-the-loop:**

- For high-value or ambiguous tasks, the operator routes to its human for review before submission
- The operator learns from human corrections over time

At POC scale, the team performs QA spot-checks manually. At production scale, automated QA handles the majority of checks, with human review reserved for edge cases and new task types. QA cost is included in the unit economics table.

## The Architecture

Three active layers, two deferred.

**Layer 1: Developer Infrastructure (operational).** Jarvis CLI, a skills system, context management, and workspace automation. This layer is our internal tooling. It proves the skill system works but is not yet connected to the economic layer.

**Layer 2: Agent Runtime (building now).** The execution engine. Agents register themselves, poll for available tasks, execute work using loaded skills, and report results. This is the core loop that makes personal operators functional. Layers 2 and 3 are the product.

**Layer 3: Economic Participation (building now).** Bittensor integration, task decomposition, result aggregation, contribution tracking, earnings ledger, and reward distribution. This layer validates the entire thesis.

Future layers (content automation, physical compute infrastructure, network abstractions, advanced security) are deferred until the core economic loop is proven.

## Risks

Four conditions must hold for the model to work.

**1. Reward sufficiency.** Per-task rewards from Bittensor subnets must consistently exceed compute and QA costs. If alpha token rewards compress due to competition or emission changes, margins disappear. *Mitigation:* Mine across multiple subnets to diversify reward sources. Track reward trends weekly. Define a minimum viable reward threshold and exit unprofitable subnets quickly.

**2. Submission quality.** Aggregated outputs must pass subnet validation. Bittensor validators reject low-quality work and penalize repeat offenders. *Mitigation:* Pre-submission QA layer. Operator reputation system that routes harder tasks to proven operators. Start with subnets where task format and validation criteria are well-documented.

**3. Task decomposition viability.** Complex tasks must be reliably decomposable into independent sub-tasks that operators can execute. *Mitigation:* Start with simple, well-structured task types. Use human-in-the-loop decomposition for the POC. Build automated decomposition only after patterns are established.

**4. Regulatory and conversion risk.** Flow converts crypto tokens to local fiat currency and distributes payments to users in emerging markets. Crypto-to-fiat regulation in key African jurisdictions (Nigeria, Kenya, South Africa) is actively evolving. Money transmission, employment classification, and tax implications must be navigated carefully. *Mitigation:* Launch in jurisdictions with established regulatory frameworks for crypto exchanges and mobile money. Use licensed conversion partners. Seek legal counsel before scaling to new markets.

**Bittensor dependency risk:** If Bittensor rewards dropped by 50-80%, Flow's current revenue model would be severely impacted. The long-term strategy is to diversify demand sources beyond the Bittensor bootstrap.

## Competitive Landscape


| Project                                           | Approach                                            | How Flow Differs                                                                                                                                                                                   |
| ------------------------------------------------- | --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Bittensor-native miners**                       | Run inference directly, compete on speed/cost       | Flow adds human-agent execution for tasks that pure AI cannot handle alone. A well-funded miner could add a human layer; our advantage is speed to market and thesis focus, not a structural moat. |
| **Fetch.ai**                                      | Autonomous agent economy, general-purpose framework | Flow is task-execution-first, not agent-framework-first. Focused on earnings, not infrastructure sales                                                                                             |
| **SingularityNET**                                | AI service marketplace                              | Marketplace for AI model APIs, not for human-agent work execution                                                                                                                                  |
| **Freelance platforms** (Upwork, Fiverr)          | Match buyers to human sellers                       | Flow decomposes and distributes work through AI-assisted agents; users do not bid or negotiate                                                                                                     |
| **Data labeling** (Scale AI, Labelbox, Remotasks) | Human annotation for ML training data               | Narrow to labeling; Flow supports broader cognitive task types and builds agent capability over time                                                                                               |


Flow's specific bet: the combination of AI agents and human oversight, applied to decomposed work from external demand sources, produces better quality at lower cost than pure-AI mining or pure-human freelancing.

## The Team


| Track                  | Lead     | Background                                            | Focus                                              |
| ---------------------- | -------- | ----------------------------------------------------- | -------------------------------------------------- |
| Agent Runtime / Jarvis | Rise     | Agent systems, developer tooling                      | Execution loop, skills, personal operators         |
| Bittensor / Blockchain | Gbolahan | Blockchain development, Bittensor subnet architecture | Subnet mining, smart contracts, token mechanics    |
| Platform               |          | —                                                     | WorkStream UI, earnings dashboard, user experience |
| Architecture           | Julian   | Full-stack systems, distributed architecture          | System design, orchestrator, coordination          |


The Platform lead is the most critical open hire. The product experience that wraps the backend complexity determines user adoption. We are actively filling this role and seeking candidates with experience building consumer products for African or emerging markets.

## Current State

**What works today:**

- Jarvis CLI with task scheduling, journaling, and two-tier context management
- 18 internal development skills (brainstorm, spec generation, code review, QA, etc.) used by the team to build Flow itself. These demonstrate the skill system's capability but are not yet operator-facing production skills.
- Skill registration, validation, and discovery infrastructure
- FastAPI backend with PostgreSQL, wallet-based authentication, and deployed smart contracts on Base Sepolia testnet
- React frontend with wallet connection and task management

**What we are building now:**

- Agent registration and execution loop
- Bittensor subnet research and first miner integration
- Task decomposition and WorkStream prototype
- Personal operator agent that can complete a round-trip: receive task, execute, submit, earn

**Timeline:**

- Pre-March 2026: Architecture design, Jarvis CLI development, POC backend/frontend, smart contract deployment, team formation
- March 2026: Sprint 1 begins. Agent runtime and Bittensor integration in parallel.
- Target April-May 2026: POC milestone. One subnet mined end-to-end with personal operators completing decomposed tasks and rewards flowing to users.

**Key POC dependencies:**

- Successful miner registration on a chosen Bittensor subnet (longest-pole item; requires TAO stake and subnet-specific integration)
- Working task decomposition for that subnet's task format
- At least 3 test operators running the execution loop

**What could delay this:** Bittensor miner registration and subnet-specific integration is the highest-risk dependency. If the first target subnet proves incompatible with our decomposition approach, we will need to pivot to an alternative subnet, adding 2-3 weeks.

## Why This Can Work

As of March 2026, four conditions have converged.

AI models execute real cognitive tasks at production quality. Bittensor has created a growing market for AI work, expanding from 32 subnets in early 2024 to 129 by March 2026. Mobile money and crypto rails have made it possible to pay people in emerging markets quickly and cheaply. Agent frameworks have matured enough to build persistent, capable AI workers without starting from scratch.

The intersection of these conditions is recent. Model quality crossed the usefulness threshold for autonomous task execution in 2024. Bittensor subnet diversity quadrupled through 2025. Agent frameworks became viable for structured task execution in late 2025. The window is open now.

Flow does not yet have a defensible moat. We believe one will emerge from operational data as we scale: which decomposition patterns produce the best results, which operator-human pairings are most productive, which progression paths convert beginners into reliable earners. But today, the advantage is execution speed and thesis clarity, not accumulated data.

## What Flow Is Not

Flow is not a freelance marketplace. Users do not bid on projects or negotiate rates.

Flow is not an AI copilot. Copilots assist professionals who already have work. Flow creates economic participation for people who may not have access to traditional employment.

Flow uses blockchain infrastructure because it is the fastest path to paid demand without building a buyer marketplace from scratch. Users never interact with the blockchain directly.

## The Vision

Every person gets a persistent economic agent with its own compute, memory, identity, and track record. The agent collaborates with its human, takes work from a global routing system, and earns value in a networked economy.

That is the destination. The immediate focus is narrower: prove that one person can earn real money through a personal AI agent completing real work on one Bittensor subnet. We will know soon whether that works.

---

## Get Involved

We are looking for:

- **Design partners** willing to pilot the WorkStream with their teams or communities
- **Technical collaborators** with experience in Bittensor subnet mining, agent frameworks, or task decomposition systems
- **Early-stage investors** to fund the POC through validation and into multi-subnet scaling
- **A Platform/Product lead** who can own the user-facing experience from onboarding through earnings withdrawal

If any of this resonates, we would like to talk.