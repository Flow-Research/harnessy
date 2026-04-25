---
name: TDD is the working style for this project
description: User expects test-first development; write failing tests before implementation, not retroactive tests after.
type: feedback
---

Always write tests before the implementation they cover. Run them, see them fail, then make them pass.

**Why:** User explicitly corrected mid-Phase-2 of the Cloudflare Artifacts skill-registry work after I shipped the registry abstraction (Phase 1) and the publisher Worker (Phase 2) with only post-hoc smoke tests. They expect this as the default working style on Harnessy.

**How to apply:**
- For any new module/function/endpoint: write the failing test first in the appropriate `tests/` directory, then the implementation.
- For multi-phase work, end each phase with green tests committed alongside the code, not as a follow-up.
- Acceptable test runners in this repo: `node:test` for JS (no extra deps, works on Node 18+), `pytest` for Python (already in use under `jarvis-cli/tests/` and `tools/flow-install/tests/`).
- If the user asks to skip tests for something exploratory, that's an explicit override — otherwise default to test-first.
