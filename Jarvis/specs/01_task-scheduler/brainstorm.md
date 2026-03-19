# Brainstorm: AnyType Task Scheduler

## Core Idea

An intelligent AnyType task scheduler that automatically analyzes workload and proposes optimized rescheduling — reducing the mental load of deciding when to do what.

## Problem Statement

Manual task scheduling is cognitively draining. Mental energy is spent reorganizing tasks when that energy could go toward actually doing them. The current process requires constant manual intervention to balance workload, respect priorities, and avoid overloaded days.

## Target User

AnyType power users who:
- Manage many tasks across different projects
- Want intelligent automation without losing control
- Value reduced cognitive overhead in daily planning

## Solution Overview

### How It Works

1. **Daily Scheduled Analysis** — Runs automatically each day, analyzing the task landscape
2. **Intelligent Suggestions** — AI reasons about optimal scheduling based on multiple factors
3. **Human Approval** — Presents proposed changes for review before applying anything
4. **Pattern Learning** — Learns user patterns over time to improve future suggestions

### Scheduling Factors (Priority Order)

1. **Workload Balancing** (primary) — Spread tasks evenly across days to avoid overload
2. **Priority/Urgency** — Higher-priority work takes precedence
3. **Deadlines** — Work backward from due dates
4. **Dependencies** — Respect task relationships
5. **Time Preferences** — Match task types to optimal times of day

### Hard Rules

- **`bar_movement` tasks are untouchable** — Tasks with this tag are never moved
- **No silent changes** — Always show proposed changes and require approval

## Context Management

A `context/` folder at project root provides the "scheduling brain" that informs AI reasoning:

```
context/
├── preferences.md          # Personal rules ("I prefer deep work in mornings")
├── patterns.md             # Work patterns ("Fridays are for admin tasks")
├── constraints.md          # Hard constraints ("No meetings on Wednesdays")
├── priorities.md           # Priority hierarchy ("Client work > internal projects")
└── learnings.md            # System-generated insights (grows over time)
```

Context is both **static** (user preferences) and **dynamic** (accumulated learnings).

## Technical Foundation

### AnyType Integration

- **API**: Official AnyType API via [developers.anytype.io](https://developers.anytype.io/)
- **Python Client**: [`anytype-client`](https://pypi.org/project/anytype-client/) for programmatic access
- **MCP Server**: [`anytype-mcp`](https://playbooks.com/mcp/anyproto/anytype-mcp) for AI assistant integration
- **Authentication**: Local challenge-response (requires AnyType desktop app running)

### Architecture Vision

- **Monorepo structure** for multiple AnyType automations
- **AI reasoning** (Claude) for intelligent scheduling decisions
- **Local execution** with AnyType desktop app
- **Scheduled runs** (daily) with on-demand override capability

## User Interaction Model

**Hybrid approach:**
- System automatically generates suggestions
- User reviews proposed changes
- User approves, rejects, or modifies before any changes are applied

## Success Criteria

1. **Even workload distribution** — No days with 10 tasks while others have 2
2. **Low override rate** — Suggestions are accepted most of the time
3. **Zero missed deadlines** — Important dates are respected
4. **Reduced mental load** — User spends less time thinking about "when should I do this?"
5. **Trust** — System feels reliable and predictable

## Anti-Goals (What This Should NOT Be)

- A fully autonomous system that makes changes without approval
- A replacement for human judgment on complex priorities
- Something that touches `bar_movement` tagged tasks
- Over-engineered complexity that adds friction instead of removing it

## Open Questions

- How to handle tasks without due dates?
- What's the optimal approval UI (CLI, notification, dashboard)?
- How to bootstrap the learning system with initial preferences?
- Should there be a "confidence threshold" for auto-suggestions?

## Inspiration

- "It's like a smart calendar assistant, but for task scheduling in AnyType"
- Goal: Move from "I need to figure out my schedule" to "The schedule figures itself out"

---

*Brainstorm captured: 2025-01-23*
*Status: Ready for product specification*
