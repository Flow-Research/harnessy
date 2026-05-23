"""CLI tests for meeting ingestion commands."""

import json
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from click.testing import CliRunner

from jarvis.config import ConfigError
from jarvis.meetings.cli import meeting_cli
from jarvis.meetings.models import MeetingIngestResult, MeetingRecord


def _meeting_record() -> MeetingRecord:
    return MeetingRecord(
        title="QBR 2025 Q1",
        meeting_date=date(2025, 3, 1),
        source_ref="fathom:123456789",
        source_type="fathom",
        fingerprint="fathom:123456789:2025-03-01T17:01:30Z",
        project="aa",
        tags=["fathom"],
        participants=["Alice Johnson", "Bob Lee"],
        summary="Reviewed pipeline and budget allocation.",
        detailed_summary="## Summary\n\nReviewed pipeline and budget allocation.",
        decisions=["Delay hiring until June"],
        action_items=["Alice Johnson: Send revised proposal"],
        open_questions=[],
        transcript="[00:05:32] Alice Johnson: Let's revisit the budget allocations.",
        raw_markdown="## Summary\n\nReviewed pipeline and budget allocation.",
    )


class TestMeetingCli:
    """Meeting CLI commands should route to the expected ingestion flows."""

    def test_ingest_command_parses_fathom_json_file(self) -> None:
        runner = CliRunner()
        payload = {
            "recording_id": 123456789,
            "meeting_title": "QBR 2025 Q1",
            "created_at": "2025-03-01T17:01:30Z",
            "recording_start_time": "2025-03-01T16:01:12Z",
            "default_summary": {
                "markdown_formatted": "## Summary\n\nReviewed pipeline and budget allocation."
            },
            "transcript": [
                {
                    "speaker": {"display_name": "Alice Johnson"},
                    "text": "Let's revisit the budget allocations.",
                    "timestamp": "00:05:32",
                }
            ],
        }
        with runner.isolated_filesystem():
            with open("meeting.json", "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
            result = runner.invoke(
                meeting_cli,
                ["ingest", "meeting.json", "--no-enrich-ai", "--json"],
            )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["meeting"]["title"] == "QBR 2025 Q1"
        assert parsed["meeting"]["source_type"] == "fathom"

    def test_fathom_list_command(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        seen: dict[str, object] = {}

        def fake_list_fathom_meetings(**kwargs):  # type: ignore[no-untyped-def]
            seen.update(kwargs)
            return [
                {
                    "recording_id": 123456789,
                    "meeting_title": "QBR 2025 Q1",
                    "created_at": "2025-03-01T17:01:30Z",
                }
            ]

        monkeypatch.setattr(
            "jarvis.meetings.cli.list_fathom_meetings",
            fake_list_fathom_meetings,
        )
        result = runner.invoke(meeting_cli, ["fathom", "list", "--account", "work", "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed[0]["recording_id"] == 123456789
        assert seen["account"] == "work"

    def test_fathom_ingest_command(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        meeting = _meeting_record()
        seen: dict[str, object] = {}

        def fake_ingest_fathom_meeting(*args, **kwargs):  # type: ignore[no-untyped-def]
            seen.update(kwargs)
            return MeetingIngestResult(
                meeting=meeting,
                destinations=["private-context"],
                written_paths=["/tmp/meeting.md"],
            )

        monkeypatch.setattr(
            "jarvis.meetings.cli.ingest_fathom_meeting",
            fake_ingest_fathom_meeting,
        )
        result = runner.invoke(
            meeting_cli,
            ["fathom", "ingest", "123456789", "--account", "work", "--json"],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["meeting"]["title"] == "QBR 2025 Q1"
        assert parsed["written_paths"] == ["/tmp/meeting.md"]
        assert seen["account"] == "work"

    def test_fathom_ingest_today_command(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        meeting = _meeting_record()
        seen: dict[str, object] = {}

        def fake_ingest_fathom_meetings_since(**kwargs):  # type: ignore[no-untyped-def]
            seen.update(kwargs)
            return [
                MeetingIngestResult(
                    meeting=meeting,
                    destinations=["private-context"],
                    written_paths=["/tmp/today.md"],
                )
            ]

        monkeypatch.setattr(
            "jarvis.meetings.cli.ingest_fathom_meetings_since",
            fake_ingest_fathom_meetings_since,
        )
        result = runner.invoke(
            meeting_cli,
            [
                "fathom",
                "ingest-today",
                "--account",
                "work",
                "--date",
                "2026-05-22",
                "--json",
            ],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["ingested"][0]["written_paths"] == ["/tmp/today.md"]
        assert seen["account"] == "work"
        assert str(seen["created_after"]).startswith("2026-05-22T00:00:00")

    def test_fathom_ingest_today_lookback_hours_command(
        self, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        meeting = _meeting_record()
        seen: dict[str, object] = {}

        def fake_ingest_fathom_meetings_since(**kwargs):  # type: ignore[no-untyped-def]
            seen.update(kwargs)
            return [
                MeetingIngestResult(
                    meeting=meeting,
                    destinations=["private-context"],
                    written_paths=["/tmp/recent.md"],
                )
            ]

        monkeypatch.setattr(
            "jarvis.meetings.cli.ingest_fathom_meetings_since",
            fake_ingest_fathom_meetings_since,
        )
        result = runner.invoke(
            meeting_cli,
            [
                "fathom",
                "ingest-today",
                "--account",
                "work",
                "--lookback-hours",
                "36",
                "--json",
            ],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["lookback_hours"] == 36.0
        assert parsed["ingested"][0]["written_paths"] == ["/tmp/recent.md"]
        created_after = datetime.fromisoformat(str(seen["created_after"]))
        expected = datetime.now().astimezone() - timedelta(hours=36)
        assert abs((created_after - expected).total_seconds()) < 5

    def test_fathom_ingest_today_all_unpulled_command(
        self, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        meeting = _meeting_record()
        seen: dict[str, object] = {}

        def fake_ingest_fathom_meetings_since(**kwargs):  # type: ignore[no-untyped-def]
            seen.update(kwargs)
            return [
                MeetingIngestResult(
                    meeting=meeting,
                    destinations=["private-context"],
                    written_paths=["/tmp/unpulled.md"],
                )
            ]

        monkeypatch.setattr(
            "jarvis.meetings.cli.ingest_fathom_meetings_since",
            fake_ingest_fathom_meetings_since,
        )
        result = runner.invoke(
            meeting_cli,
            [
                "fathom",
                "ingest-today",
                "--account",
                "work",
                "--all-unpulled",
                "--max-pages",
                "50",
                "--json",
            ],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["created_after"] is None
        assert parsed["all_unpulled"] is True
        assert parsed["ingested"][0]["written_paths"] == ["/tmp/unpulled.md"]
        assert seen["created_after"] is None
        assert seen["max_pages"] == 50

    def test_fathom_ingest_today_rejects_multiple_scopes(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            meeting_cli,
            [
                "fathom",
                "ingest-today",
                "--date",
                "2026-05-22",
                "--all-unpulled",
            ],
        )
        assert result.exit_code != 0
        assert "mutually exclusive" in result.output

    def test_fathom_poll_command_uses_all_configured_accounts(
        self, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        meeting = _meeting_record()
        cfg = SimpleNamespace(
            fathom=SimpleNamespace(
                accounts={"personal": SimpleNamespace(), "work": SimpleNamespace()},
                default_account="personal",
            )
        )
        calls: list[dict[str, object]] = []
        saved: dict[str, object] = {}

        def fake_ingest_fathom_meetings_since(**kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return [
                MeetingIngestResult(
                    meeting=meeting,
                    destinations=["private-context"],
                    written_paths=[f"/tmp/{kwargs['account']}.md"],
                )
            ]

        monkeypatch.setattr("jarvis.meetings.cli.load_config", lambda reload=False: cfg)
        monkeypatch.setattr(
            "jarvis.meetings.cli.get_fathom_api_key",
            lambda account=None: "key",
        )
        monkeypatch.setattr("jarvis.meetings.cli.load_poll_state", lambda path=None: {})
        monkeypatch.setattr(
            "jarvis.meetings.cli.save_poll_state",
            lambda state, path=None: (
                saved.setdefault("state", state),
                "/tmp/poll-state.json",
            )[1],
        )
        monkeypatch.setattr(
            "jarvis.meetings.cli.ingest_fathom_meetings_since",
            fake_ingest_fathom_meetings_since,
        )
        result = runner.invoke(
            meeting_cli,
            [
                "fathom",
                "poll",
                "--auto-route",
                "--dest",
                "private-context",
                "--dest",
                "memory",
                "--json",
            ],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert [account["account"] for account in parsed["accounts"]] == [
            "personal",
            "work",
        ]
        assert [call["account"] for call in calls] == ["personal", "work"]
        assert all(call["auto_route"] is True for call in calls)
        assert all(call["destinations"] == ["private-context", "memory"] for call in calls)
        state = saved["state"]
        assert isinstance(state, dict)
        assert set(state["accounts"]) == {"personal", "work"}

    def test_fathom_poll_command_uses_watermark_overlap(
        self, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        seen: dict[str, object] = {}
        poll_state = {
            "version": 1,
            "accounts": {
                "work": {"last_successful_poll_at": "2026-05-23T07:00:00+01:00"}
            },
        }

        def fake_ingest_fathom_meetings_since(**kwargs):  # type: ignore[no-untyped-def]
            seen.update(kwargs)
            return []

        monkeypatch.setattr("jarvis.meetings.cli.load_poll_state", lambda path=None: poll_state)
        monkeypatch.setattr("jarvis.meetings.cli.save_poll_state", lambda state, path=None: path)
        monkeypatch.setattr(
            "jarvis.meetings.cli.ingest_fathom_meetings_since",
            fake_ingest_fathom_meetings_since,
        )
        result = runner.invoke(
            meeting_cli,
            [
                "fathom",
                "poll",
                "--account",
                "work",
                "--overlap-hours",
                "6",
                "--json",
            ],
        )
        assert result.exit_code == 0
        assert seen["created_after"] == "2026-05-23T01:00:00+01:00"

    def test_fathom_poll_command_continues_after_account_error(
        self, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        cfg = SimpleNamespace(
            fathom=SimpleNamespace(
                accounts={"personal": SimpleNamespace(), "work": SimpleNamespace()},
                default_account="personal",
            )
        )
        calls: list[str] = []
        saved: dict[str, object] = {}

        def fake_ingest_fathom_meetings_since(**kwargs):  # type: ignore[no-untyped-def]
            account = str(kwargs["account"])
            calls.append(account)
            if account == "personal":
                raise RuntimeError("temporary outage")
            return []

        monkeypatch.setattr("jarvis.meetings.cli.load_config", lambda reload=False: cfg)
        monkeypatch.setattr(
            "jarvis.meetings.cli.get_fathom_api_key",
            lambda account=None: "key",
        )
        monkeypatch.setattr("jarvis.meetings.cli.load_poll_state", lambda path=None: {})
        monkeypatch.setattr(
            "jarvis.meetings.cli.save_poll_state",
            lambda state, path=None: (
                saved.setdefault("state", state),
                "/tmp/poll-state.json",
            )[1],
        )
        monkeypatch.setattr(
            "jarvis.meetings.cli.ingest_fathom_meetings_since",
            fake_ingest_fathom_meetings_since,
        )
        result = runner.invoke(
            meeting_cli,
            ["fathom", "poll", "--json"],
        )
        assert result.exit_code == 1
        parsed = json.loads(result.output)
        assert calls == ["personal", "work"]
        assert parsed["accounts"][0]["error"] == "temporary outage"
        state = saved["state"]
        assert isinstance(state, dict)
        assert state["accounts"]["personal"]["last_error"] == "temporary outage"
        assert state["accounts"]["work"]["last_error"] is None

    def test_fathom_poll_command_skips_default_accounts_without_api_keys(
        self, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        cfg = SimpleNamespace(
            fathom=SimpleNamespace(
                accounts={"aa": SimpleNamespace(), "personal": SimpleNamespace()},
                default_account="personal",
            )
        )
        calls: list[str] = []

        def fake_get_fathom_api_key(account=None):  # type: ignore[no-untyped-def]
            if account == "aa":
                raise ConfigError("missing aa key", backend="fathom")
            return "key"

        def fake_ingest_fathom_meetings_since(**kwargs):  # type: ignore[no-untyped-def]
            calls.append(str(kwargs["account"]))
            return []

        monkeypatch.setattr("jarvis.meetings.cli.load_config", lambda reload=False: cfg)
        monkeypatch.setattr(
            "jarvis.meetings.cli.get_fathom_api_key",
            fake_get_fathom_api_key,
        )
        monkeypatch.setattr("jarvis.meetings.cli.load_poll_state", lambda path=None: {})
        monkeypatch.setattr("jarvis.meetings.cli.save_poll_state", lambda state, path=None: path)
        monkeypatch.setattr(
            "jarvis.meetings.cli.ingest_fathom_meetings_since",
            fake_ingest_fathom_meetings_since,
        )

        result = runner.invoke(meeting_cli, ["fathom", "poll", "--json"])

        assert result.exit_code == 0
        assert calls == ["personal"]

    def test_fathom_webhook_create_command_no_save(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        seen: dict[str, object] = {}

        class FakeClient:
            def __init__(self, account=None):  # type: ignore[no-untyped-def]
                seen["account"] = account

            def create_webhook(self, **kwargs):  # type: ignore[no-untyped-def]
                seen.update(kwargs)
                return {
                    "id": "wh_123",
                    "url": kwargs["destination_url"],
                    "secret": "whsec_secret",
                }

        monkeypatch.setattr("jarvis.meetings.cli.FathomClient", FakeClient)
        result = runner.invoke(
            meeting_cli,
            [
                "fathom",
                "webhook",
                "create",
                "--account",
                "work",
                "--destination-url",
                "https://fathom.example.com",
                "--no-save",
                "--json",
            ],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["id"] == "wh_123"
        assert parsed["secret"] == "****"
        assert parsed["saved"] is False
        assert seen["triggered_for"] == ["my_recordings"]
        assert seen["include_transcript"] is True

    def test_fathom_webhook_delete_command_uses_saved_id(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        account_cfg = SimpleNamespace(
            webhook_id="wh_123",
            webhook_destination_url="https://fathom.example.com",
            webhook_secret_env_var="FATHOM_WEBHOOK_SECRET_WORK",
        )
        cfg = SimpleNamespace(
            fathom=SimpleNamespace(accounts={"work": account_cfg}, default_account="work")
        )
        seen: dict[str, object] = {}

        class FakeClient:
            def __init__(self, account=None):  # type: ignore[no-untyped-def]
                seen["account"] = account

            def delete_webhook(self, webhook_id):  # type: ignore[no-untyped-def]
                seen["webhook_id"] = webhook_id

        monkeypatch.setattr("jarvis.meetings.cli.load_config", lambda reload=False: cfg)
        monkeypatch.setattr(
            "jarvis.meetings.cli.save_config",
            lambda config: seen.setdefault("saved", config),
        )
        monkeypatch.setattr("jarvis.meetings.cli.FathomClient", FakeClient)
        result = runner.invoke(
            meeting_cli,
            ["fathom", "webhook", "delete", "--account", "work", "--json"],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["deleted"] == "wh_123"
        assert parsed["cleared_saved"] is True
        assert account_cfg.webhook_id is None
        assert seen["webhook_id"] == "wh_123"

    def test_fathom_webhook_status_command(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        account_cfg = SimpleNamespace(
            webhook_id="wh_123",
            webhook_destination_url="https://fathom.example.com",
            webhook_secret_env_var="FATHOM_WEBHOOK_SECRET_WORK",
        )
        cfg = SimpleNamespace(
            fathom=SimpleNamespace(accounts={"work": account_cfg}, default_account="work")
        )
        monkeypatch.setattr("jarvis.meetings.cli.load_config", lambda reload=False: cfg)
        monkeypatch.setattr(
            "jarvis.meetings.cli.get_fathom_webhook_secret",
            lambda account: "whsec",
        )
        monkeypatch.setattr("jarvis.meetings.cli.list_inbox_files", lambda account, state: [state])
        result = runner.invoke(
            meeting_cli,
            ["fathom", "webhook", "status", "--account", "work", "--json"],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["webhook_id"] == "wh_123"
        assert parsed["webhook_secret_configured"] is True
        assert parsed["pending_count"] == 1

    def test_fathom_webhook_serve_command(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        seen: dict[str, object] = {}

        def fake_serve_fathom_webhook(**kwargs):  # type: ignore[no-untyped-def]
            seen.update(kwargs)

        monkeypatch.setattr("jarvis.meetings.cli.serve_fathom_webhook", fake_serve_fathom_webhook)
        result = runner.invoke(
            meeting_cli,
            [
                "fathom",
                "webhook",
                "serve",
                "--account",
                "work",
                "--port",
                "9999",
                "--no-verify-signatures",
            ],
        )
        assert result.exit_code == 0
        assert seen["account"] == "work"
        assert seen["port"] == 9999
        assert seen["verify_signatures"] is False

    def test_fathom_webhook_serve_command_auto_ingest(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        seen: dict[str, object] = {}
        callback_holder: dict[str, object] = {}

        def fake_serve_fathom_webhook(**kwargs):  # type: ignore[no-untyped-def]
            seen.update(kwargs)
            callback_holder["callback"] = kwargs.get("on_verified")

        ingested: dict[str, object] = {}

        def fake_ingest_archived_fathom_payload(path, **kwargs):  # type: ignore[no-untyped-def]
            ingested["path"] = path
            ingested.update(kwargs)

        monkeypatch.setattr("jarvis.meetings.cli.serve_fathom_webhook", fake_serve_fathom_webhook)
        monkeypatch.setattr(
            "jarvis.meetings.cli.ingest_archived_fathom_payload",
            fake_ingest_archived_fathom_payload,
        )
        result = runner.invoke(
            meeting_cli,
            [
                "fathom",
                "webhook",
                "serve",
                "--account",
                "work",
                "--auto-ingest",
                "--auto-route",
                "--dest",
                "private-context",
            ],
        )
        assert result.exit_code == 0
        assert seen["account"] == "work"
        callback = callback_holder["callback"]
        assert callback is not None
        callback("/tmp/payload.json")
        assert ingested["account"] == "work"
        assert ingested["auto_route"] is True
        assert ingested["destinations"] == ["private-context"]

    def test_fathom_webhook_ingest_inbox_command(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        meeting = _meeting_record()
        seen: dict[str, object] = {}

        def fake_ingest_fathom_inbox(**kwargs):  # type: ignore[no-untyped-def]
            seen.update(kwargs)
            return [
                MeetingIngestResult(
                    meeting=meeting,
                    destinations=["private-context"],
                    written_paths=["/tmp/inbox-meeting.md"],
                )
            ]

        monkeypatch.setattr("jarvis.meetings.cli.ingest_fathom_inbox", fake_ingest_fathom_inbox)
        result = runner.invoke(
            meeting_cli,
            [
                "fathom",
                "webhook",
                "ingest-inbox",
                "--account",
                "work",
                "--auto-route",
                "--json",
            ],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed[0]["written_paths"] == ["/tmp/inbox-meeting.md"]
        assert seen["account"] == "work"
        assert seen["auto_route"] is True

    def test_fathom_start_command_dry_run_json(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        monkeypatch.setattr(
            "jarvis.meetings.cli.load_config",
            lambda: type(
                "Cfg",
                (),
                {
                    "fathom": type(
                        "F",
                        (),
                        {"accounts": {"work": object()}, "default_account": "work"},
                    )()
                },
            )(),
        )
        monkeypatch.setattr("jarvis.meetings.cli.require_command", lambda name: None)
        result = runner.invoke(
            meeting_cli,
            [
                "fathom",
                "start",
                "--account",
                "work",
                "--auto-route",
                "--dest",
                "private-context",
                "--dest",
                "memory",
                "--dry-run",
                "--json",
            ],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["session_name"] == "fathom-work"
        assert "--auto-route" in parsed["webhook_command"]
        assert "--dest private-context --dest memory" in parsed["webhook_command"]
        assert "cloudflared tunnel" in parsed["tunnel_command"]
        assert parsed["layout"] == "windows"

    def test_fathom_start_command_named_tunnel_dry_run_json(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        monkeypatch.setattr(
            "jarvis.meetings.cli.load_config",
            lambda: type(
                "Cfg",
                (),
                {
                    "fathom": type(
                        "F",
                        (),
                        {"accounts": {"work": object()}, "default_account": "work"},
                    )()
                },
            )(),
        )
        monkeypatch.setattr("jarvis.meetings.cli.require_command", lambda name: None)
        result = runner.invoke(
            meeting_cli,
            [
                "fathom",
                "start",
                "--account",
                "work",
                "--tunnel-name",
                "jarvis-fathom",
                "--dry-run",
                "--json",
            ],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["tunnel_name"] == "jarvis-fathom"
        assert parsed["tunnel_command"] == "cloudflared tunnel run jarvis-fathom"

    def test_fathom_start_command_launches_tmux(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        monkeypatch.setattr(
            "jarvis.meetings.cli.load_config",
            lambda: type(
                "Cfg",
                (),
                {
                    "fathom": type(
                        "F",
                        (),
                        {"accounts": {"work": object()}, "default_account": "work"},
                    )()
                },
            )(),
        )
        monkeypatch.setattr("jarvis.meetings.cli.require_command", lambda name: None)
        seen: dict[str, object] = {}

        def fake_start_fathom_tmux_stack(plan, attach=False):  # type: ignore[no-untyped-def]
            seen["plan"] = plan
            seen["attach"] = attach

        monkeypatch.setattr(
            "jarvis.meetings.cli.start_fathom_tmux_stack",
            fake_start_fathom_tmux_stack,
        )
        result = runner.invoke(
            meeting_cli,
            ["fathom", "start", "--account", "work"],
        )
        assert result.exit_code == 0
        assert seen["attach"] is True

    def test_fathom_start_command_pane_layout(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        monkeypatch.setattr(
            "jarvis.meetings.cli.load_config",
            lambda: type(
                "Cfg",
                (),
                {
                    "fathom": type(
                        "F",
                        (),
                        {"accounts": {"work": object()}, "default_account": "work"},
                    )()
                },
            )(),
        )
        monkeypatch.setattr("jarvis.meetings.cli.require_command", lambda name: None)
        seen: dict[str, object] = {}

        def fake_start_fathom_tmux_stack(plan, attach=False):  # type: ignore[no-untyped-def]
            seen["layout"] = plan.layout

        monkeypatch.setattr(
            "jarvis.meetings.cli.start_fathom_tmux_stack",
            fake_start_fathom_tmux_stack,
        )
        result = runner.invoke(
            meeting_cli,
            ["fathom", "start", "--account", "work", "--layout", "panes"],
        )
        assert result.exit_code == 0
        assert seen["layout"] == "panes"

    def test_fathom_start_command_no_attach(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        monkeypatch.setattr(
            "jarvis.meetings.cli.load_config",
            lambda: type(
                "Cfg",
                (),
                {
                    "fathom": type(
                        "F",
                        (),
                        {"accounts": {"work": object()}, "default_account": "work"},
                    )()
                },
            )(),
        )
        monkeypatch.setattr("jarvis.meetings.cli.require_command", lambda name: None)
        seen: dict[str, object] = {}

        def fake_start_fathom_tmux_stack(plan, attach=False):  # type: ignore[no-untyped-def]
            seen["attach"] = attach

        monkeypatch.setattr(
            "jarvis.meetings.cli.start_fathom_tmux_stack",
            fake_start_fathom_tmux_stack,
        )
        result = runner.invoke(
            meeting_cli,
            ["fathom", "start", "--account", "work", "--no-attach"],
        )
        assert result.exit_code == 0
        assert seen["attach"] is False
