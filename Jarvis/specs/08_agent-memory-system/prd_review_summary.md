# PRD Review Summary — Agent Memory System

## PRD Review Complete

All perspectives signed off: ✅

PRD SHA256: 27520f737d14abd9dbbb0e97c62e0de05370954b95a1011728a60ef6b97190a8

## Review Panel

| # | Perspective | Findings | Status |
|---|---|---|---|
| 1 | Product Manager | 6 findings (2 Major, 3 Minor, 1 Info) | ✅ Signed off after fixes |
| 2 | End User | 5 findings (1 Critical, 1 Major, 2 Minor, 1 Info) | ✅ Signed off after fixes |
| 3 | Engineering | 7 findings (2 Major, 4 Minor, 1 Info) | ✅ Signed off after fixes |
| 4 | Security/Privacy | 4 findings (1 Major, 2 Minor, 1 Info) | ✅ Signed off after fixes |
| 5 | QA | 6 findings (2 Major, 3 Minor, 1 Info) | ✅ Signed off after fixes |

## Must-Fix Items Addressed

| ID | Severity | Issue | Resolution |
|---|---|---|---|
| EU-01 | Critical | No discovery mechanism for agents to find memory system | MR-01 updated: AGENTS.md will contain a "Memory System" section pointing to `_scopes.yaml`. Added AC-14. |
| PM-01 | Major | Primary success metric unmeasurable | Replaced with ">90% of sessions agent correctly references memory-stored decision" with baseline and measurement protocol. |
| PM-03 | Major | No write trigger convention | Added US-07 (agent recognizes when to write) and US-08 (seed from existing context). AGENTS.md section will include write trigger convention. |
| EN-01 | Major | User scope position in hierarchy ambiguous | Added SR-08: user scope is a separate chain merged at highest priority. `[user] + [app → project → org]`. |
| EN-02 | Major | `_scopes.yaml` schema undefined | Added concrete schema example to section 8 with all fields documented (id, type, parent, path, match, user_scope). |
| EU-02 | Major | Agent write UX undefined | Added "Memory Write Template" section with exact markdown template and write convention. |
| SP-01 | Major | No write isolation enforcement in Phase 1 | EC-06 updated to acknowledge Phase 1 convention-based approach as tech debt (TD-52-01). Enforcement deferred to Phase 2 RLS. |
| QA-01 | Major | Scope resolution not testable | AC-06 remains as the testable criterion. Tech spec will define the scope resolution as a deterministic function. |
| QA-02 | Major | No write acceptance criteria | Added AC-11 (write correctness), AC-12 (supersession), AC-13 (user scope isolation), AC-14 (AGENTS.md documentation). |

## Additional Improvements (Minor findings addressed)

- PM-02: Memory quality dimension noted -- success metric SM-02 should be complemented with active-entry retention rate
- PM-04: Added US-08 for seeding memories from existing context (migration story)
- PM-06: Phase 4 noted as requiring its own PRD before implementation
- EU-03: Conflict resolution clarified in scope resolution semantics
- EU-04: User scope priority explicitly defined in SR-08
- EN-03: Entry delimiter format clarified in write template section
- EN-06: Frontmatter-per-entry confirmed as the chosen approach
- EN-07: `memory_type` in frontmatter kept as denormalized metadata; filename is canonical source
- SP-02: Added AC-13 for user scope isolation verification
- SP-03: Added note about PII in data security section (noted for Phase 4 privacy assessment)
- QA-03: Concurrent writes clarified as append-only (both entries preserved)
- QA-04: Fallback behavior defined (read existing root `.jarvis/context/*.md` files)
- QA-05: Added AC-12 for supersession logic verification

## Tech Debt Logged

| ID | Description | Phase |
|---|---|---|
| TD-52-01 | User scope write isolation enforced by convention only (no filesystem ACL). Requires Supabase RLS in Phase 2. | Phase 2 fix |
