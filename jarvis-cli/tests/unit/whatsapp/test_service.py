"""Tests for WhatsApp normalization, ingestion, and local threads."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from jarvis.whatsapp.models import WhatsAppMessage
from jarvis.whatsapp.service import (
    conversation_window_open,
    ingest_archived_whatsapp_payload,
    normalize_whatsapp_payload,
    send_text_message,
)
from jarvis.whatsapp.storage import (
    append_message_to_thread,
    load_archived_payload,
    load_thread,
    thread_id_for,
)


def _meta_payload(message: dict[str, object]) -> dict[str, object]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba_1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "phone_1",
                            },
                            "contacts": [
                                {"profile": {"name": "Ada"}, "wa_id": "2348012345678"}
                            ],
                            "messages": [message],
                        },
                    }
                ],
            }
        ],
    }


def _archive(path, payload: dict[str, object]) -> None:  # type: ignore[no-untyped-def]
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "account": "personal",
                "provider": "meta",
                "verified": True,
                "payload": payload,
            }
        ),
        encoding="utf-8",
    )


def _patch_private_root(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        "jarvis.whatsapp.storage._resolve_private_context_root",
        lambda: tmp_path,
    )


class TestNormalizeWhatsAppPayload:
    """Inbound Meta payloads should normalize common WhatsApp message types."""

    @pytest.mark.parametrize(
        ("message_type", "body", "expected"),
        [
            ("text", {"text": {"body": "hello"}}, "hello"),
            ("image", {"image": {"id": "img_1", "caption": "photo"}}, "photo"),
            ("audio", {"audio": {"id": "aud_1", "mime_type": "audio/ogg"}}, ""),
            ("document", {"document": {"id": "doc_1", "filename": "a.pdf"}}, ""),
            (
                "location",
                {"location": {"latitude": 6.5, "longitude": 3.3, "name": "Lagos"}},
                "Lagos",
            ),
            (
                "contacts",
                {"contacts": [{"name": {"formatted_name": "Ada Lovelace"}}]},
                "Ada Lovelace",
            ),
        ],
    )
    def test_message_types(self, message_type: str, body: dict[str, object], expected: str) -> None:
        payload = _meta_payload(
            {
                "from": "2348012345678",
                "id": f"wamid.{message_type}",
                "timestamp": "1700000000",
                "type": message_type,
                **body,
            }
        )

        messages = normalize_whatsapp_payload(payload, account="personal")

        assert len(messages) == 1
        assert messages[0].message_type == message_type
        assert messages[0].sender == "+2348012345678"
        assert messages[0].contact_name == "Ada"
        assert messages[0].text == expected

    def test_status_event(self) -> None:
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "phone_1"},
                                "statuses": [
                                    {
                                        "id": "wamid.1",
                                        "status": "delivered",
                                        "timestamp": "1700000000",
                                        "recipient_id": "2348012345678",
                                    }
                                ],
                            }
                        }
                    ]
                }
            ],
        }

        messages = normalize_whatsapp_payload(payload, account="personal")

        assert messages[0].direction == "status"
        assert messages[0].status == "delivered"
        assert messages[0].recipient == "+2348012345678"

    def test_uses_configured_default_account(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(
            "jarvis.whatsapp.service.load_config",
            lambda: SimpleNamespace(
                whatsapp=SimpleNamespace(default_account="personal")
            ),
        )
        payload = _meta_payload(
            {
                "from": "2348012345678",
                "id": "wamid.default",
                "timestamp": "1700000000",
                "type": "text",
                "text": {"body": "hello"},
            }
        )

        messages = normalize_whatsapp_payload(payload, account=None)

        assert messages[0].account == "personal"


class TestIngestArchivedWhatsAppPayload:
    """Inbox ingestion should be idempotent and move files by outcome."""

    def test_ingests_pending_payload_to_thread(self, monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
        _patch_private_root(monkeypatch, tmp_path)
        payload = _meta_payload(
            {
                "from": "2348012345678",
                "id": "wamid.1",
                "timestamp": "1700000000",
                "type": "text",
                "text": {"body": "hello"},
            }
        )
        path = tmp_path / "whatsapp" / "personal" / "inbox" / "pending" / "payload.json"
        _archive(path, payload)

        result = ingest_archived_whatsapp_payload(path, account="personal")

        assert len(result.messages) == 1
        assert result.processed_paths[0].endswith("/processed/payload.json")
        thread_id = thread_id_for("personal", "+2348012345678")
        thread = load_thread("personal", thread_id)
        assert thread.messages[0].text == "hello"
        assert thread.contact_name == "Ada"

    def test_duplicate_message_is_skipped(self, monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
        _patch_private_root(monkeypatch, tmp_path)
        message = WhatsAppMessage(
            message_id="wamid.1",
            account="personal",
            direction="inbound",
            sender="+2348012345678",
            recipient="+15551234567",
            timestamp=datetime.now(UTC),
            message_type="text",
            text="hello",
        )
        append_message_to_thread(message)
        payload = _meta_payload(
            {
                "from": "2348012345678",
                "id": "wamid.1",
                "timestamp": "1700000000",
                "type": "text",
                "text": {"body": "hello"},
            }
        )
        path = tmp_path / "whatsapp" / "personal" / "inbox" / "pending" / "payload.json"
        _archive(path, payload)

        result = ingest_archived_whatsapp_payload(path, account="personal")

        assert result.skipped_duplicates == 1
        assert result.processed_paths

    def test_invalid_pending_payload_moves_with_error(self, monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
        _patch_private_root(monkeypatch, tmp_path)
        path = tmp_path / "whatsapp" / "personal" / "inbox" / "pending" / "payload.json"
        _archive(path, {"object": "whatsapp_business_account", "entry": []})

        result = ingest_archived_whatsapp_payload(path, account="personal")

        assert result.invalid_paths[0].endswith("/invalid/payload.json")
        moved = tmp_path / "whatsapp" / "personal" / "inbox" / "invalid" / "payload.json"
        assert load_archived_payload(moved)["error"] == "No WhatsApp messages or statuses found"


class TestSendTextMessage:
    """Outbound free-form sends should respect the local service-window guard."""

    def test_rejects_without_recent_inbound(self, monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
        _patch_private_root(monkeypatch, tmp_path)

        with pytest.raises(ValueError):
            send_text_message(account="personal", to="+2348012345678", text="hello")

    def test_window_open_with_recent_inbound(self, monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
        _patch_private_root(monkeypatch, tmp_path)
        message = WhatsAppMessage(
            message_id="wamid.recent",
            account="personal",
            direction="inbound",
            sender="+2348012345678",
            recipient="+15551234567",
            timestamp=datetime.now(UTC) - timedelta(hours=1),
            message_type="text",
            text="hello",
        )
        append_message_to_thread(message)

        assert conversation_window_open("personal", "+2348012345678") is True
