"""Meta WhatsApp Cloud API webhook verification and local archiving."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from jarvis.config import get_whatsapp_app_secret, get_whatsapp_verify_token, load_config

from .storage import inbox_dir


def verify_meta_signature(
    raw_body: bytes,
    headers: Mapping[str, str],
    app_secret: str,
) -> bool:
    """Verify Meta's `X-Hub-Signature-256` HMAC header."""

    signature = headers.get("x-hub-signature-256", "")
    if not signature or not app_secret:
        return False
    if signature.startswith("sha256="):
        signature = signature.split("=", 1)[1]
    digest = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, digest)


def verify_challenge(params: Mapping[str, str], verify_token: str) -> str | None:
    """Return Meta's challenge string when a webhook verification request is valid."""

    mode = params.get("hub.mode", "")
    token = params.get("hub.verify_token", "")
    challenge = params.get("hub.challenge", "")
    if mode == "subscribe" and token and hmac.compare_digest(token, verify_token):
        return challenge
    return None


def looks_like_meta_whatsapp_payload(payload: object) -> bool:
    """Return True when a payload resembles a Meta WhatsApp webhook event."""

    if not isinstance(payload, dict):
        return False
    if payload.get("object") != "whatsapp_business_account":
        return False
    entries = payload.get("entry")
    return isinstance(entries, list) and bool(entries)


def archive_webhook_payload(
    raw_body: bytes,
    headers: Mapping[str, str],
    *,
    account: str | None,
    verified: bool,
) -> Path:
    """Persist a raw Meta webhook payload for later deterministic ingestion."""

    text = raw_body.decode("utf-8", errors="replace")
    try:
        payload: object = json.loads(text)
    except json.JSONDecodeError:
        payload = {"raw_text": text}

    resolved_account = _configured_account(account)
    state = "pending" if verified and looks_like_meta_whatsapp_payload(payload) else "invalid"
    target_dir = inbox_dir(resolved_account, state=state)
    path = target_dir / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex}.json"
    path.write_text(
        json.dumps(
            {
                "received_at": datetime.now(UTC).isoformat(),
                "account": resolved_account or "default",
                "provider": "meta",
                "verified": verified,
                "headers": {
                    "x-hub-signature-256": headers.get("x-hub-signature-256", ""),
                    "content-type": headers.get("content-type", ""),
                    "user-agent": headers.get("user-agent", ""),
                },
                "payload": payload,
                "raw_text": text,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def serve_whatsapp_webhook(
    *,
    port: int,
    account: str | None,
    verify_signatures: bool = True,
    on_verified: Callable[[Path], None] | None = None,
) -> None:
    """Run a local blocking HTTP server for Meta WhatsApp webhook intake."""

    resolved_account = _configured_account(account)
    app_secret = get_whatsapp_app_secret(resolved_account) if verify_signatures else ""
    verify_token = get_whatsapp_verify_token(resolved_account)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            query = parse_qs(urlparse(self.path).query)
            params = {key: values[0] for key, values in query.items() if values}
            challenge = verify_challenge(params, verify_token)
            if challenge is None:
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"invalid verification token")
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(challenge.encode("utf-8"))

        def do_POST(self) -> None:  # noqa: N802
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            headers = {key.lower(): value for key, value in self.headers.items()}
            verified = (
                verify_meta_signature(raw_body, headers, app_secret)
                if verify_signatures
                else True
            )
            archive_path = archive_webhook_payload(
                raw_body,
                headers,
                account=resolved_account,
                verified=verified,
            )
            if not verified:
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"invalid signature")
                return
            if on_verified is not None:
                try:
                    on_verified(archive_path)
                except Exception:
                    pass
            self.send_response(200)
            self.end_headers()
            self.wfile.write(str(archive_path).encode("utf-8"))

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _configured_account(account: str | None) -> str | None:
    if account:
        return account
    try:
        return load_config().whatsapp.default_account
    except Exception:
        return None
