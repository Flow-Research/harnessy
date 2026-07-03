"""Local Fathom webhook receiver and inbox helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

from jarvis.config import get_fathom_webhook_secret

from .fathom import looks_like_fathom_payload

_USERNAME = os.environ.get("FLOW_USER", os.environ.get("USER", "default"))


def verify_fathom_signature(
    raw_body: bytes,
    headers: Mapping[str, str],
    secret: str,
    *,
    tolerance_seconds: int = 300,
    now: datetime | None = None,
) -> bool:
    """Verify the Fathom webhook signature against the raw request body."""

    webhook_id = headers.get("webhook-id", "")
    webhook_timestamp = headers.get("webhook-timestamp", "")
    webhook_signature = headers.get("webhook-signature", "")
    if not webhook_id or not webhook_timestamp or not webhook_signature:
        return False

    try:
        timestamp = int(webhook_timestamp)
    except ValueError:
        return False

    current = now or datetime.now(UTC)
    if abs(int(current.timestamp()) - timestamp) > tolerance_seconds:
        return False

    secret_value = secret[len("whsec_") :] if secret.startswith("whsec_") else secret
    try:
        decoded_secret = base64.b64decode(secret_value)
    except Exception:
        return False

    signed_content = b".".join([webhook_id.encode(), webhook_timestamp.encode(), raw_body])
    digest = hmac.new(decoded_secret, signed_content, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()

    for candidate in _parse_signature_header(webhook_signature):
        if hmac.compare_digest(candidate, expected):
            return True
    return False


def _parse_signature_header(value: str) -> list[str]:
    parts: list[str] = []
    for token in value.split(","):
        cleaned = token.strip()
        if not cleaned:
            continue
        if cleaned.startswith(("v1=", "v0=")):
            cleaned = cleaned.split("=", 1)[1].strip()
        parts.append(cleaned)
    return parts


def fathom_inbox_dir(account: str | None, state: str = "pending") -> Path:
    """Resolve the local inbox directory for archived Fathom payloads."""

    account_name = account or "default"
    root = _resolve_private_context_root() / "meeting-inbox" / "fathom" / account_name / state
    root.mkdir(parents=True, exist_ok=True)
    return root


def archive_webhook_payload(
    raw_body: bytes,
    headers: Mapping[str, str],
    *,
    account: str | None,
    verified: bool,
) -> Path:
    """Persist a webhook payload and metadata for later ingestion."""

    text = raw_body.decode("utf-8", errors="replace")
    payload: object
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = {"raw_text": text}

    state = "pending" if verified and looks_like_fathom_payload(payload) else "invalid"
    target_dir = fathom_inbox_dir(account, state=state)
    filename = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex}.json"
    path = target_dir / filename
    path.write_text(
        json.dumps(
            {
                "received_at": datetime.now(UTC).isoformat(),
                "account": account or "default",
                "verified": verified,
                "headers": {
                    "webhook-id": headers.get("webhook-id", ""),
                    "webhook-timestamp": headers.get("webhook-timestamp", ""),
                    "webhook-signature": headers.get("webhook-signature", ""),
                    "content-type": headers.get("content-type", ""),
                },
                "payload": payload,
                "raw_text": text,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def list_inbox_files(account: str | None, state: str = "pending") -> list[Path]:
    """List archived payload files for an account and state."""

    return sorted(fathom_inbox_dir(account, state=state).glob("*.json"))


def load_archived_payload(path: Path) -> dict[str, object]:
    """Load an archived webhook payload wrapper from disk."""

    return json.loads(path.read_text(encoding="utf-8"))


def move_inbox_file(path: Path, account: str | None, state: str) -> Path:
    """Move an archived inbox file into a new state directory."""

    destination = fathom_inbox_dir(account, state=state) / path.name
    if destination.exists():
        destination = destination.with_name(f"{destination.stem}-{uuid4().hex}{destination.suffix}")
    path.replace(destination)
    return destination


def serve_fathom_webhook(
    *,
    port: int,
    account: str | None,
    verify_signatures: bool = True,
    tolerance_seconds: int = 300,
    on_verified: Callable[[Path], None] | None = None,
) -> None:
    """Run a local blocking HTTP server for Fathom webhook intake."""

    secret = get_fathom_webhook_secret(account) if verify_signatures else ""

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            headers = {key.lower(): value for key, value in self.headers.items()}
            verified = (
                verify_fathom_signature(
                    raw_body,
                    headers,
                    secret,
                    tolerance_seconds=tolerance_seconds,
                )
                if verify_signatures
                else True
            )
            archive_path = archive_webhook_payload(
                raw_body,
                headers,
                account=account,
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


def _resolve_private_context_root() -> Path:
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        user_ctx = parent / ".jarvis" / "context" / "private" / _USERNAME
        if user_ctx.is_dir():
            user_ctx.mkdir(parents=True, exist_ok=True)
            return user_ctx
    fallback = cwd / ".jarvis" / "context" / "private" / _USERNAME
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback
