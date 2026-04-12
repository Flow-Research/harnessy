"""Autonomous research orchestrator for jarvis wiki domains.

`WikiResearcher` is the thin Python coordinator that turns a research request
into:

1. A self-contained prompt the agent can act on
2. A spawned Claude agent (via `backend.research_session()`) with WebSearch,
   WebFetch, Read, Write, Glob, and Grep enabled
3. Validation of whatever the agent dropped into `raw/articles/`
4. A compile pass over the new files
5. Trace and findings written for the morning brief and ratchet to read

The intelligence (search, judgement, dedup, fetch) lives in the agent. This
module does file I/O, prompt construction, validation, and accounting.
"""

from __future__ import annotations

import json
import os
import string
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from jarvis.wiki.backends import WikiBackend, create_backend
from jarvis.wiki.compiler import WikiCompiler
from jarvis.wiki.log import LogAppender
from jarvis.wiki.models import LogEntry, LogEntryType, WikiDomain
from jarvis.wiki.program import Program, Topic, TopicDepth, load_program
from jarvis.wiki.seeds import (
    Seed,
    SeedPriority,
    load_seeds,
    mark_processed,
)

# Skill name used for trace files under ~/.agents/traces/<skill>/
TRACE_SKILL_NAME = "wiki-research"

# Path to the agent prompt template (string.Template format with $vars)
_PROMPT_TEMPLATE_PATH = Path(__file__).parent / "agents" / "research_agent_prompt.md"


@dataclass
class ResearchSession:
    """Lifecycle state for a single research run."""

    session_id: str
    domain: str
    domain_root: Path
    topic: str  # "auto", "seeds-only", or a literal topic name
    mode: str  # "auto" | "seeds-only" | "explicit"
    max_sources: int
    started_at: datetime = field(default_factory=datetime.utcnow)
    prompt: str = ""
    agent_output: str = ""
    parsed: dict[str, Any] = field(default_factory=dict)
    files_created: list[Path] = field(default_factory=list)
    files_rejected: list[tuple[Path, str]] = field(default_factory=list)
    seeds_consumed: list[str] = field(default_factory=list)
    compile_stats: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class WikiResearcher:
    """Coordinator for autonomous research sessions on a single wiki domain."""

    def __init__(self, domain_root: Path, schema: WikiDomain) -> None:
        self.domain_root = domain_root
        self.schema = schema
        self._backend: WikiBackend | None = None

    @property
    def backend(self) -> WikiBackend:
        if self._backend is None:
            self._backend = create_backend(self.schema)
        return self._backend

    def research(
        self,
        topic: str | None = None,
        max_sources: int | None = None,
        seeds_only: bool = False,
        auto_compile: bool = True,
        dry_run: bool = False,
        max_turns: int = 25,
    ) -> ResearchSession:
        """Run one research session end-to-end.

        Args:
            topic: Specific topic to research; None means auto-select from
                program.md highest-priority topic with oldest last_researched
            max_sources: Override the program's max_sources_per_session
            seeds_only: Process only pending seeds, ignore program topics
            auto_compile: Run `WikiCompiler.compile()` after the agent finishes
            dry_run: Build and persist the prompt but don't spawn the agent
            max_turns: Agent turn budget

        Returns:
            ResearchSession with all artifacts populated.
        """
        program = load_program(self.domain_root, self.schema.domain)
        seeds_file = load_seeds(self.domain_root, self.schema.domain)

        # Resolve session parameters
        resolved_max_sources: int = (
            max_sources if max_sources is not None else program.cadence.max_sources_per_session
        )
        if seeds_only:
            mode = "seeds-only"
            chosen_topic = "(pending seeds only)"
        elif topic:
            mode = "explicit"
            chosen_topic = topic
        else:
            mode = "auto"
            chosen_topic = self._auto_pick_topic(program, seeds_file.pending)

        session = ResearchSession(
            session_id=_make_session_id(),
            domain=self.schema.domain,
            domain_root=self.domain_root,
            topic=chosen_topic,
            mode=mode,
            max_sources=resolved_max_sources,
        )
        session_dir = self._session_dir(session)
        session_dir.mkdir(parents=True, exist_ok=True)

        # Build the agent prompt
        session.prompt = self._build_prompt(session, program)
        (session_dir / "prompt.txt").write_text(session.prompt, encoding="utf-8")

        if dry_run:
            return session

        # Snapshot raw/articles/ so we can detect what the agent created
        raw_dir = self.domain_root / "raw" / "articles"
        raw_dir.mkdir(parents=True, exist_ok=True)
        before = {p.name for p in raw_dir.glob("*.md")}

        # Spawn the agent
        try:
            session.agent_output = self.backend.research_session(
                prompt=session.prompt,
                allowed_dirs=[
                    str(self.domain_root),
                ],
                max_turns=max_turns,
            )
        except Exception as exc:  # noqa: BLE001
            session.errors.append(f"agent_session_failed: {exc}")
            self._persist(session, session_dir, program)
            return session

        (session_dir / "output.txt").write_text(session.agent_output, encoding="utf-8")

        # Parse the trailing JSON contract
        session.parsed = _extract_trailing_json(session.agent_output) or {}
        if not session.parsed:
            session.errors.append("no_json_envelope_in_agent_output")

        (session_dir / "output.json").write_text(
            json.dumps(session.parsed, indent=2), encoding="utf-8"
        )

        # Detect actual file deltas (trust the filesystem, not the agent's claims)
        after = {p.name for p in raw_dir.glob("*.md")}
        new_files = sorted(after - before)
        for name in new_files:
            path = raw_dir / name
            ok, reason = _validate_research_file(path)
            if ok:
                session.files_created.append(path)
            else:
                session.files_rejected.append((path, reason))

        # Reconcile against the agent's claimed file list (warn on mismatch)
        claimed = set(session.parsed.get("files_created") or [])
        actual = {str(p) for p in session.files_created}
        if claimed and claimed != actual:
            session.errors.append(
                f"file_claim_mismatch: agent said {sorted(claimed)} "
                f"but filesystem shows {sorted(actual)}"
            )

        # Mark consumed seeds in seeds.md
        for entry in session.parsed.get("seeds_consumed") or []:
            seed_id = entry.get("id") if isinstance(entry, dict) else None
            result = entry.get("result", "ingested") if isinstance(entry, dict) else "ingested"
            if seed_id:
                if mark_processed(
                    self.domain_root,
                    self.schema.domain,
                    seed_id,
                    session=session.session_id,
                    result=str(result),
                ):
                    session.seeds_consumed.append(seed_id)

        # Run compile on the new files
        if auto_compile and session.files_created:
            compiler = WikiCompiler(self.domain_root, self.schema)
            session.compile_stats = compiler.compile(verbose=False)

        # Persist findings + log entry
        self._persist(session, session_dir, program)

        # Capture autoresearch traces (one per gate) for the autoflow ratchet
        try:
            self._capture_traces(session)
        except Exception as exc:  # noqa: BLE001
            session.errors.append(f"trace_capture_failed: {exc}")

        return session

    # ── prompt construction ─────────────────────────────────────────────────

    def _build_prompt(self, session: ResearchSession, program: Program) -> str:
        """Render the agent prompt template with session-specific values."""
        template = _PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
        substitutions = {
            "session_id": session.session_id,
            "domain_title": self.schema.title,
            "program_path": str(self.domain_root / "program.md"),
            "seeds_path": str(self.domain_root / "seeds.md"),
            "concepts_dir": str(self.domain_root / "wiki" / "concepts"),
            "index_path": str(self.domain_root / "wiki" / "index.md"),
            "raw_articles_dir": str(self.domain_root / "raw" / "articles"),
            "topic": session.topic,
            "max_sources": str(session.max_sources),
            "mode": session.mode,
            "date_stamp": date.today().isoformat(),
        }
        # Use string.Template for $var substitution to avoid clashing with
        # the JSON/YAML braces inside the prompt body.
        return string.Template(template).safe_substitute(**substitutions)

    # ── target selection ────────────────────────────────────────────────────

    def _auto_pick_topic(self, program: Program, pending_seeds: list[Seed]) -> str:
        """Pick the next research target when no explicit topic is given.

        Priority order: pending seeds (highest priority first) → program
        topics ranked by depth then oldest last_researched. Returns a
        descriptive label for logging; the agent does its own seed lookup.
        """
        # Pending seeds win — describe by count + first high-priority entry
        if pending_seeds:
            high = [s for s in pending_seeds if s.priority == SeedPriority.HIGH]
            anchor = high[0] if high else pending_seeds[0]
            anchor_label = (
                f"{anchor.kind.value} '{anchor.value[:60]}'"
                if len(anchor.value) > 60
                else f"{anchor.kind.value} '{anchor.value}'"
            )
            return f"pending seeds ({len(pending_seeds)} total, anchor: {anchor_label})"

        if not program.active_topics:
            return "(no topics in program.md)"

        depth_rank = {
            TopicDepth.HIGH: 0,
            TopicDepth.MEDIUM: 1,
            TopicDepth.LOW: 2,
        }

        def sort_key(t: Topic) -> tuple[int, date]:
            return (
                depth_rank.get(t.depth, 3),
                t.last_researched or date(1970, 1, 1),
            )

        return sorted(program.active_topics, key=sort_key)[0].name

    # ── persistence ─────────────────────────────────────────────────────────

    def _session_dir(self, session: ResearchSession) -> Path:
        return self.domain_root / ".state" / "research-sessions" / session.session_id

    def _persist(
        self,
        session: ResearchSession,
        session_dir: Path,
        program: Program,
    ) -> None:
        """Write findings.md, the flat findings file, and append the log entry."""
        findings = self._render_findings(session, program)
        (session_dir / "findings.md").write_text(findings, encoding="utf-8")

        flat_dir = self.domain_root / ".state" / "findings"
        flat_dir.mkdir(parents=True, exist_ok=True)
        flat_path = flat_dir / f"{date.today().isoformat()}-{session.session_id}.md"
        flat_path.write_text(findings, encoding="utf-8")

        # Append log entry
        n_files = len(session.files_created)
        n_concepts = (session.compile_stats or {}).get("concepts_created", 0)
        description = (
            f"{session.mode} research — topic: {session.topic[:60]} — "
            f"{n_files} sources, {n_concepts} new concepts"
        )
        if session.errors:
            description += f" ({len(session.errors)} errors)"
        LogAppender.append(
            self.domain_root,
            LogEntry(
                entry_type=LogEntryType.ENHANCE,  # closest existing type
                description=description,
                metadata={
                    "session_id": session.session_id,
                    "files_created": [str(p) for p in session.files_created],
                    "seeds_consumed": session.seeds_consumed,
                    "errors": session.errors,
                },
            ),
        )

    def _capture_traces(self, session: ResearchSession) -> None:
        """Append per-gate traces to ~/.agents/traces/wiki-research/traces.ndjson.

        The autoflow ratchet reads these to compute the multiplicative metric
        and decide whether prompt edits should be kept or reverted. We emit
        five gates per session, each shaped like the issue-flow trace format
        so the existing `_shared/run_metrics.py` aggregator can ingest them
        without modification.

        Refinement loop semantics for wiki research:
            - target_selection: 0 if a target was found, else 1
            - agent_session: 0 if no errors, else 1
            - file_validation: number of rejected files
            - compilation: 0 on clean compile, 1 on errors
            - dedup_check: 0 if no new duplicate_concept lint warnings, else 1
        """
        traces_root = (
            Path(
                os.environ.get(
                    "AGENTS_TRACES_ROOT",
                    str(Path.home() / ".agents" / "traces"),
                )
            )
            / TRACE_SKILL_NAME
        )
        traces_root.mkdir(parents=True, exist_ok=True)
        trace_file = traces_root / "traces.ndjson"

        compile_stats = session.compile_stats or {}
        compile_errors = len(compile_stats.get("errors", []) or [])
        new_duplicates = self._count_new_duplicate_lint_warnings(session)

        gates: list[tuple[str, int, str, dict[str, Any]]] = [
            (
                "target_selection",
                0 if session.topic and session.topic != "(no topics in program.md)" else 1,
                "approved" if session.topic else "rejected",
                {"topic": session.topic, "mode": session.mode},
            ),
            (
                "agent_session",
                0 if not session.errors else 1,
                "approved" if not session.errors else "rejected",
                {"errors": session.errors},
            ),
            (
                "file_validation",
                len(session.files_rejected),
                "approved" if not session.files_rejected else "rejected",
                {
                    "files_created": len(session.files_created),
                    "files_rejected": [r for _, r in session.files_rejected],
                },
            ),
            (
                "compilation",
                0 if compile_errors == 0 else 1,
                "approved" if compile_errors == 0 else "rejected",
                {
                    "concepts_created": compile_stats.get("concepts_created", 0),
                    "concepts_updated": compile_stats.get("concepts_updated", 0),
                    "concepts_aliased": compile_stats.get("concepts_aliased", 0),
                    "compile_errors": compile_errors,
                },
            ),
            (
                "dedup_check",
                new_duplicates,
                "approved" if new_duplicates == 0 else "rejected",
                {"new_duplicate_concepts": new_duplicates},
            ),
        ]

        ts = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        with trace_file.open("a") as fh:
            for name, loops, outcome, structured in gates:
                trace = {
                    "trace_id": f"tr_{session.session_id}_{name}",
                    "timestamp": ts,
                    "skill": TRACE_SKILL_NAME,
                    "phase": {"name": name},
                    "gate": {
                        "name": name,
                        "type": "quality",
                        "outcome": outcome,
                        "refinement_loops": loops,
                    },
                    "feedback": {"structured": structured, "unstructured": []},
                    "context": {
                        "domain": session.domain,
                        "session_id": session.session_id,
                        "topic": session.topic,
                        "mode": session.mode,
                    },
                }
                fh.write(json.dumps(trace, separators=(",", ":")) + "\n")

    def _count_new_duplicate_lint_warnings(self, session: ResearchSession) -> int:
        """Run lint after the session and count duplicate_concept warnings.

        This is a coarse signal: we don't snapshot the pre-session count, so
        any duplicate_concept warning attributed to a concept created in this
        session is treated as "new". Cheap to compute and good enough for the
        ratchet's monotonic-improvement signal.
        """
        if not session.files_created:
            return 0
        try:
            from jarvis.wiki.lint import WikiLinter

            linter = WikiLinter(self.domain_root, self.schema)
            report = linter.lint()
        except Exception:  # noqa: BLE001
            return 0

        # Concept slugs touched by this session (best-effort: derived from
        # source slug → newly-created concept attribution requires walking
        # the manifest, which we skip for now). We approximate by counting
        # any duplicate_concept warning whose article was modified after the
        # session started.
        cutoff = session.started_at.timestamp()
        touched_slugs: set[str] = set()
        concepts_dir = self.domain_root / "wiki" / "concepts"
        if concepts_dir.exists():
            for path in concepts_dir.glob("*.md"):
                try:
                    if path.stat().st_mtime >= cutoff:
                        touched_slugs.add(path.stem)
                except OSError:
                    continue

        count = 0
        for issue in report.issues:
            if issue.check != "duplicate_concept":
                continue
            if issue.article_slug in touched_slugs:
                count += 1
        return count

    def _render_findings(self, session: ResearchSession, program: Program) -> str:
        """Render a human-readable findings markdown summary for the brief."""
        del program  # reserved for future context use
        lines: list[str] = []
        lines.append("---")
        lines.append(f"session_id: {session.session_id}")
        lines.append(f"domain: {session.domain}")
        lines.append(f"topic: {session.topic}")
        lines.append(f"mode: {session.mode}")
        lines.append(f"started_at: {session.started_at.isoformat()}")
        lines.append(f"max_sources: {session.max_sources}")
        lines.append(f"files_created: {len(session.files_created)}")
        lines.append(f"seeds_consumed: {len(session.seeds_consumed)}")
        lines.append(f"errors: {len(session.errors)}")
        lines.append("---")
        lines.append("")
        lines.append(f"# Research Session — {session.session_id}")
        lines.append("")
        lines.append(f"**Topic**: {session.topic}")
        lines.append(f"**Mode**: {session.mode}")
        lines.append(f"**Max sources**: {session.max_sources}")
        lines.append("")

        if session.files_created:
            lines.append("## Files created")
            for p in session.files_created:
                lines.append(f"- `{p.name}`")
            lines.append("")
        else:
            lines.append("_No new files were created._")
            lines.append("")

        compile_stats = session.compile_stats or {}
        if compile_stats:
            lines.append("## Compile stats")
            lines.append(f"- {compile_stats.get('sources_compiled', 0)} sources compiled")
            lines.append(f"- {compile_stats.get('concepts_created', 0)} concepts created")
            lines.append(f"- {compile_stats.get('concepts_updated', 0)} concepts updated")
            lines.append(f"- {compile_stats.get('concepts_aliased', 0)} concepts aliased")
            lines.append("")

        urls_considered = session.parsed.get("urls_considered") or []
        if urls_considered:
            lines.append("## URLs considered")
            for entry in urls_considered:
                if not isinstance(entry, dict):
                    continue
                decision = entry.get("decision", "?")
                url = entry.get("url", "(no url)")
                reason = entry.get("reason", "")
                lines.append(f"- **{decision}** {url}")
                if reason:
                    lines.append(f"  - {reason}")
            lines.append("")

        if session.seeds_consumed:
            lines.append("## Seeds consumed")
            for sid in session.seeds_consumed:
                lines.append(f"- `{sid}`")
            lines.append("")

        notes = session.parsed.get("notes")
        if notes:
            lines.append("## Notes from the agent")
            lines.append("")
            lines.append(str(notes))
            lines.append("")

        if session.errors:
            lines.append("## Errors")
            for err in session.errors:
                lines.append(f"- {err}")
            lines.append("")
        if session.files_rejected:
            lines.append("## Rejected files")
            for path, reason in session.files_rejected:
                lines.append(f"- `{path.name}` — {reason}")
            lines.append("")

        return "\n".join(lines)


# ── module helpers ────────────────────────────────────────────────────────────


def _make_session_id() -> str:
    """Return a sortable, unique session id like `20260412-180530-ab12cd34`."""
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    short = uuid.uuid4().hex[:8]
    return f"{ts}-{short}"


def _extract_trailing_json(text: str) -> dict[str, Any] | None:
    """Extract the LAST top-level JSON object from agent output.

    Walks the string from the end looking for a balanced `{...}` block.
    Tolerates trailing whitespace and code fences.
    """
    if not text:
        return None
    s = text.strip()
    # Strip a closing markdown fence if present
    if s.endswith("```"):
        s = s[:-3].rstrip()
    end = s.rfind("}")
    if end == -1:
        return None
    depth = 0
    start = -1
    for i in range(end, -1, -1):
        ch = s[i]
        if ch == "}":
            depth += 1
        elif ch == "{":
            depth -= 1
            if depth == 0:
                start = i
                break
    if start == -1:
        return None
    snippet = s[start : end + 1]
    try:
        result = json.loads(snippet)
    except json.JSONDecodeError:
        return None
    return result if isinstance(result, dict) else None


def _validate_research_file(path: Path) -> tuple[bool, str]:
    """Sanity-check a file the agent claims it wrote into raw/articles/.

    Returns (ok, reason). A file is accepted if it exists, is non-trivial,
    and has the required provenance frontmatter keys (source_url and
    research_session). Files outside the raw/articles/ tree are rejected by
    the caller (they never get added to session.files_created in the first
    place).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"unreadable: {exc}"
    if len(text) < 200:
        return False, f"too short ({len(text)} bytes)"
    if not text.startswith("---"):
        return False, "missing frontmatter"
    if "source_url:" not in text[:1000]:
        return False, "missing source_url in frontmatter"
    if "research_session:" not in text[:1000]:
        return False, "missing research_session in frontmatter"
    return True, "ok"
