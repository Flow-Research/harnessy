# Brainstorm Transcript — Agent Memory System

Q1: What kind of memory system are you looking for? Agent development memory, platform product memory, or both?
A1: We want both. But the product feature can come later. For now we are focused on the Agent development. The architecture should be designed so it can later evolve into a platform product feature for coaching (founders, coaches, orgs, cohorts).

Q2: What is the desired memory model? Flat per-entity storage, or a hierarchical/composable model where scopes inherit from parent scopes?
A2: Yes, hierarchical/composable. Memory scopes that compose: a user's context includes their project's context, which includes their org's context. Per user, per organization, per any level that can be created as an abstraction on the network.

Q3: Should the memory system be locked to a specific storage backend, or should it support pluggable backends?
A3: We want an abstraction that can implement the memory against any kind of backend, or combination of backends. A MemoryProvider interface with capability-based routing so different backends serve different query types.

Q4: Should we use an existing framework like Mem0 (managed cloud) or build our own?
A4: I want to avoid vendor dependency. We should study Mem0's open-source design patterns (scope resolution, memory types, deduplication) and build our own on existing infrastructure (Supabase). The hybrid approach: learn from Mem0's architecture, implement in our stack with our exact hierarchy model.

Q5: For Phase 1 (file-based), who are the initial consumers?
A5: We should design it from day one to be used by any team member or agent. Not just Julian with Claude Code and Jarvis -- multi-user support designed in from the start.

Q6: Should Phase 1 include the TypeScript MemoryProvider interface as code, or just the file conventions?
A6: Phase 1 = file conventions only. Define the scoped directory structure, naming conventions, and frontmatter schema. The TypeScript abstraction ships in Phase 2 with the MCP server.

Q7: What memory types do we need? We discussed: fact, decision, pattern, preference, event.
A7: Remove "pattern" -- it's vague and overlaps with decision and preference. Start with four types: fact, decision, preference, event.

Q8: What scope types do we need for the hierarchy?
A8: Start with org/project/app/user. Add product scopes (cohort, founder, coach) when we get to Phase 4 (product memory).

Q9: Should memories have temporal validity metadata in Phase 1?
A9: Yes, include basic temporal metadata -- created_at and status (active/superseded) in frontmatter. Keep it simple, no complex date ranges.

Q10: What phasing approach should we follow?
A10: Start with Phase 1 (scoped files), don't skip any phases. Phase 1 validates the scope hierarchy model before committing to a database schema. Then Phase 2 (MCP + Supabase), Phase 3 (summarization + temporal), Phase 4 (product coaching memory).

Q11: How does an agent determine its scope chain? And how does it determine what scope a new memory applies to?
A11: Hybrid auto-detection + override. Agent reads _scopes.yaml from the memory root, which contains glob patterns mapping file paths to scopes. Agent matches its working directory to resolve the scope chain. User scope is always appended from system username. For writing, store at the narrowest scope where the memory is universally true -- default to current scope, promote explicitly when broader.

Q12: Memory file granularity -- one file per scope per type, or one file per individual memory?
A12: One file per scope per type (e.g., org/decisions.md, project/facts.md). Each memory is an entry within that file. Keeps file count manageable.

Q13: Should AGENTS.md reference scoped memory files directly, or should the memory system be a separate context source?
A13: Memory system should be a separate context source that agents discover independently. AGENTS.md does not reference individual memory files. Agents discover the memory system via _scopes.yaml.

Q14: Scope registry format -- YAML or markdown?
A14: Whatever makes most sense. YAML (_scopes.yaml) was recommended since it's machine-parseable and supports glob patterns.

Q15: Contributor onboarding -- pnpm setup or jarvis init?
A15: pnpm setup for now (already implemented). Let's evaluate jarvis init as a future migration path when Jarvis is standard tooling across projects.

Clarity Check: "Do we have enough clarity to proceed?"
Answer: Yes. All open questions from the initial brainstorm are resolved. Scope detection, memory placement, file granularity, AGENTS.md integration, registry format, and onboarding are all decided. Remaining open questions (entry format within files, conflict resolution semantics) will be resolved in the tech spec.
