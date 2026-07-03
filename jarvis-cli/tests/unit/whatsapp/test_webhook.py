"""Tests for WhatsApp webhook verification and archiving."""

import hashlib
import hmac
import json

from jarvis.whatsapp.storage import load_archived_payload
from jarvis.whatsapp.webhook import (
    archive_webhook_payload,
    verify_challenge,
    verify_meta_signature,
)


def _signed_headers(raw_body: bytes, app_secret: str) -> dict[str, str]:
    digest = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return {
        "x-hub-signature-256": f"sha256={digest}",
        "content-type": "application/json",
    }


def _payload() -> dict[str, object]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba_1",
                "changes": [{"field": "messages", "value": {"messages": []}}],
            }
        ],
    }


def _patch_private_root(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        "jarvis.whatsapp.storage._resolve_private_context_root",
        lambda: tmp_path,
    )


class TestVerifyMetaSignature:
    """Meta signatures should match the raw request body and app secret."""

    def test_valid_signature(self) -> None:
        raw_body = json.dumps(_payload()).encode("utf-8")
        headers = _signed_headers(raw_body, "app-secret")

        assert verify_meta_signature(raw_body, headers, "app-secret") is True

    def test_invalid_signature(self) -> None:
        raw_body = json.dumps(_payload()).encode("utf-8")
        headers = _signed_headers(raw_body, "app-secret")

        assert verify_meta_signature(raw_body, headers, "wrong-secret") is False


class TestVerifyChallenge:
    """Meta GET verification should return the challenge only for matching tokens."""

    def test_valid_challenge(self) -> None:
        challenge = verify_challenge(
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "local-token",
                "hub.challenge": "challenge-123",
            },
            "local-token",
        )

        assert challenge == "challenge-123"

    def test_invalid_challenge(self) -> None:
        challenge = verify_challenge(
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "bad-token",
                "hub.challenge": "challenge-123",
            },
            "local-token",
        )

        assert challenge is None


class TestArchiveWebhookPayload:
    """Webhook payloads should archive raw data into pending or invalid inboxes."""

    def test_archive_valid_payload(self, monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
        _patch_private_root(monkeypatch, tmp_path)
        payload = _payload()
        raw_body = json.dumps(payload).encode("utf-8")

        path = archive_webhook_payload(
            raw_body,
            _signed_headers(raw_body, "app-secret"),
            account="personal",
            verified=True,
        )

        assert path.parent.name == "pending"
        loaded = load_archived_payload(path)
        assert loaded["provider"] == "meta"
        assert loaded["payload"]["object"] == "whatsapp_business_account"

    def test_archive_invalid_signature_payload(
        self, monkeypatch, tmp_path
    ) -> None:  # type: ignore[no-untyped-def]
        _patch_private_root(monkeypatch, tmp_path)

        path = archive_webhook_payload(
            b'{"object":"whatsapp_business_account"}',
            {},
            account="personal",
            verified=False,
        )

        assert path.parent.name == "invalid"
