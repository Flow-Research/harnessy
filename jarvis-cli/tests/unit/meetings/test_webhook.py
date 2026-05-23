"""Tests for Fathom webhook verification and inbox helpers."""

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime

from jarvis.meetings.webhook import (
    archive_webhook_payload,
    load_archived_payload,
    verify_fathom_signature,
)


def _signed_headers(raw_body: bytes, secret: str, timestamp: int = 1_700_000_000) -> dict[str, str]:
    webhook_id = "msg_123"
    secret_value = secret[len("whsec_") :] if secret.startswith("whsec_") else secret
    decoded = base64.b64decode(secret_value)
    signed_content = b".".join([webhook_id.encode(), str(timestamp).encode(), raw_body])
    digest = hmac.new(decoded, signed_content, hashlib.sha256).digest()
    signature = base64.b64encode(digest).decode()
    return {
        "webhook-id": webhook_id,
        "webhook-timestamp": str(timestamp),
        "webhook-signature": f"v1,{signature}",
        "content-type": "application/json",
    }


class TestVerifyFathomSignature:
    """Webhook signatures should be accepted only when valid and timely."""

    def test_valid_signature(self) -> None:
        secret = "whsec_" + base64.b64encode(b"supersecret").decode()
        raw_body = b'{"recording_id": 123}'
        headers = _signed_headers(raw_body, secret)
        now = datetime.fromtimestamp(1_700_000_000, UTC)
        assert verify_fathom_signature(raw_body, headers, secret, now=now) is True

    def test_invalid_signature(self) -> None:
        secret = "whsec_" + base64.b64encode(b"supersecret").decode()
        raw_body = b'{"recording_id": 123}'
        headers = _signed_headers(raw_body, secret)
        headers["webhook-signature"] = "v1,bad"
        now = datetime.fromtimestamp(1_700_000_000, UTC)
        assert verify_fathom_signature(raw_body, headers, secret, now=now) is False


class TestArchiveWebhookPayload:
    """Webhook payloads should archive with metadata for later ingestion."""

    def test_archive_and_load_payload(self, monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(
            "jarvis.meetings.webhook._resolve_private_context_root",
            lambda: tmp_path,
        )
        payload = {"recording_id": 123, "default_summary": {}, "transcript": []}
        raw_body = json.dumps(payload).encode("utf-8")
        path = archive_webhook_payload(
            raw_body,
            {"webhook-id": "a", "webhook-timestamp": "1", "webhook-signature": "b"},
            account="work",
            verified=True,
        )
        loaded = load_archived_payload(path)
        assert loaded["account"] == "work"
        assert loaded["verified"] is True
        assert loaded["payload"]["recording_id"] == 123
