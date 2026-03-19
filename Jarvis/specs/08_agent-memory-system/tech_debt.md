# Technical Debt Register — Epic 52: Agent Memory System

## TD-52-01: User Scope Write Isolation (Convention-Only)

| Field | Value |
|---|---|
| ID | TD-52-01 |
| Status | Open |
| Type | Security boundary |
| Scope | Phase 1 |
| Context | Phase 1 file-based memory has no filesystem enforcement preventing an agent from writing to another user's `private/<username>/` directory. Write isolation relies on agent convention. |
| Impact | Low risk in Phase 1 (single primary user, trusted agents). Higher risk if multiple contributors use the system concurrently with untrusted agents. |
| Proposed Resolution | Phase 2: Supabase RLS policies enforce scope-based write isolation. The MCP server validates scope ownership before writes. |
| Target Phase | Phase 2 |
| Links | [product_spec.md EC-06](./product_spec.md), [prd_review_summary.md](./prd_review_summary.md) |

## TD-52-02: Phase 4 Product Scopes Need Per-Project Extension Mechanism

| Field | Value |
|---|---|
| ID | TD-52-02 |
| Status | Open |
| Type | Design |
| Scope | Phase 4 |
| Context | The original spec included AA-specific product scope types (`cohort:`, `founder:`, `coach:`) for Phase 4. These were removed during the generalization (FN-TD-002 resolution, 2026-03-19) because they are domain-specific to the AA coaching platform. The `_scopes.yaml` format supports arbitrary scope types, but there is no defined extension mechanism for projects to declare custom scope types beyond the core `org`/`project`/`app`/`user` hierarchy. |
| Impact | Without an extension mechanism, projects that need domain-specific scopes will have to manually edit `_scopes.yaml` and create directories. The auto-detection in `flow-install` only generates the core hierarchy. |
| Proposed Resolution | Define a `custom_scope_types` section in `_scopes.yaml` that projects can populate. Update `flow-install` to preserve these during upgrades. Optionally support a `scopes.d/` directory for modular scope definitions. |
| Target Phase | Phase 4 |
| Links | [FN-TD-004](../../../.jarvis/context/technical-debt.md), [brainstorm.md addendum](./brainstorm.md) |
