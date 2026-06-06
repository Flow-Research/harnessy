"""CLI tests for WhatsApp commands."""

import json
from types import SimpleNamespace

from click.testing import CliRunner

from jarvis.cli import cli
from jarvis.whatsapp.cli import whatsapp_cli
from jarvis.whatsapp.models import WhatsAppIngestResult, WhatsAppMessage, WhatsAppSendResult


class TestWhatsAppCli:
    """WhatsApp CLI commands should route to the expected service functions."""

    def test_setup_json(self) -> None:
        result = CliRunner().invoke(whatsapp_cli, ["setup", "--account", "personal", "--json"])

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["config_yaml"]["whatsapp"]["accounts"]["personal"]["provider"] == "meta"

    def test_webhook_status_command(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        account_cfg = SimpleNamespace(
            provider="meta",
            phone_number_id="phone_1",
            business_account_id="waba_1",
            api_version="v24.0",
            webhook_destination_url="https://example.com/wa",
        )
        cfg = SimpleNamespace(
            whatsapp=SimpleNamespace(
                accounts={"personal": account_cfg},
                default_account="personal",
            )
        )
        monkeypatch.setattr("jarvis.whatsapp.cli.load_config", lambda: cfg)
        monkeypatch.setattr(
            "jarvis.whatsapp.cli.get_whatsapp_account_config",
            lambda account: account_cfg,
        )
        monkeypatch.setattr(
            "jarvis.whatsapp.cli.get_whatsapp_access_token",
            lambda account: "token",
        )
        monkeypatch.setattr(
            "jarvis.whatsapp.cli.get_whatsapp_app_secret",
            lambda account: "secret",
        )
        monkeypatch.setattr(
            "jarvis.whatsapp.cli.get_whatsapp_verify_token",
            lambda account: "verify",
        )
        monkeypatch.setattr(
            "jarvis.whatsapp.cli.list_inbox_files",
            lambda account, state: [state],
        )

        result = runner.invoke(
            whatsapp_cli,
            ["webhook", "status", "--account", "personal", "--json"],
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["phone_number_id"] == "phone_1"
        assert parsed["pending_count"] == 1

    def test_webhook_serve_auto_ingest(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        seen: dict[str, object] = {}
        callback_holder: dict[str, object] = {}

        def fake_serve(**kwargs):  # type: ignore[no-untyped-def]
            seen.update(kwargs)
            callback_holder["callback"] = kwargs["on_verified"]

        ingested: dict[str, object] = {}

        def fake_ingest(path, **kwargs):  # type: ignore[no-untyped-def]
            ingested["path"] = path
            ingested.update(kwargs)

        monkeypatch.setattr("jarvis.whatsapp.cli.serve_whatsapp_webhook", fake_serve)
        monkeypatch.setattr("jarvis.whatsapp.cli.ingest_archived_whatsapp_payload", fake_ingest)

        result = CliRunner().invoke(
            whatsapp_cli,
            [
                "webhook",
                "serve",
                "--account",
                "personal",
                "--auto-ingest",
                "--dest",
                "team-inbox",
            ],
        )

        assert result.exit_code == 0
        assert seen["account"] == "personal"
        callback = callback_holder["callback"]
        assert callback is not None
        callback("/tmp/payload.json")
        assert ingested["destinations"] == ["team-inbox"]

    def test_ingest_inbox_command(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        message = WhatsAppMessage(
            message_id="wamid.1",
            account="personal",
            direction="inbound",
            sender="+2348012345678",
            recipient="+15551234567",
            message_type="text",
            text="hello",
        )

        def fake_ingest(**kwargs):  # type: ignore[no-untyped-def]
            return WhatsAppIngestResult(
                account="personal",
                destinations=kwargs["destinations"],
                messages=[message],
                written_paths=["/tmp/thread.json"],
            )

        monkeypatch.setattr("jarvis.whatsapp.cli.ingest_whatsapp_inbox", fake_ingest)
        result = CliRunner().invoke(
            whatsapp_cli,
            [
                "webhook",
                "ingest-inbox",
                "--account",
                "personal",
                "--dest",
                "memory",
                "--json",
            ],
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["messages"][0]["text"] == "hello"

    def test_send_command(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        message = WhatsAppMessage(
            message_id="wamid.out",
            account="personal",
            direction="outbound",
            recipient="+2348012345678",
            message_type="text",
            text="reply",
        )

        def fake_send(**kwargs):  # type: ignore[no-untyped-def]
            return WhatsAppSendResult(
                account=kwargs["account"],
                to=kwargs["to"],
                provider_response={"messages": [{"id": "wamid.out"}]},
                message=message,
                thread_id="wa-123",
            )

        monkeypatch.setattr("jarvis.whatsapp.cli.send_text_message", fake_send)
        result = CliRunner().invoke(
            whatsapp_cli,
            [
                "send",
                "--account",
                "personal",
                "--to",
                "+2348012345678",
                "--text",
                "reply",
                "--json",
            ],
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["message"]["message_id"] == "wamid.out"

    def test_docs_include_whatsapp_commands(self) -> None:
        result = CliRunner().invoke(cli, ["docs", "--json"])

        assert result.exit_code == 0
        docs = json.loads(result.output)
        whatsapp_docs = docs["commands"]["whatsapp"]
        assert whatsapp_docs["subcommands"]["webhook ingest-inbox"]["options"]["--dest"]
        assert whatsapp_docs["subcommands"]["send-template"]["options"]["--template"]
