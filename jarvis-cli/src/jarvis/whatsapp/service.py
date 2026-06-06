"""WhatsApp channel normalization, ingestion, outbound send, and destination writers."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from jarvis.config import load_config
from jarvis.services.journal_service import JournalService

from .client import MetaWhatsAppClient
from .models import WhatsAppIngestResult, WhatsAppMessage, WhatsAppSendResult
from .storage import (
    append_message_to_thread,
    canonical_phone,
    list_inbox_files,
    mark_inbox_file_invalid,
    move_inbox_file,
    safe_account_name,
    thread_id_for,
    whatsapp_root,
)
from .storage import load_archived_payload as load_archived_whatsapp_payload

DEFAULT_DESTINATIONS = ["team-inbox"]
SUPPORTED_DESTINATIONS = {"team-inbox", "private-context", "journal", "memory"}


def normalize_whatsapp_payload(
    payload: dict[str, Any],
    *,
    account: str | None,
) -> list[WhatsAppMessage]:
    """Normalize Meta WhatsApp webhook payloads into Jarvis channel messages."""

    normalized: list[WhatsAppMessage] = []
    configured_account = _configured_account(account)
    account_name = safe_account_name(configured_account)
    entries = payload.get("entry")
    if not isinstance(entries, list):
        return normalized

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        changes = entry.get("changes")
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else {}
            business_number = str(
                metadata.get("display_phone_number")
                or metadata.get("phone_number_id")
                or ""
            )
            contact_names = _contact_names(value.get("contacts"))
            normalized.extend(
                _normalize_inbound_messages(
                    value.get("messages"),
                    account=account_name,
                    business_number=canonical_phone(business_number) if business_number else "",
                    contact_names=contact_names,
                )
            )
            normalized.extend(
                _normalize_statuses(
                    value.get("statuses"),
                    account=account_name,
                    business_number=canonical_phone(business_number) if business_number else "",
                )
            )
    return normalized


def ingest_whatsapp_inbox(
    *,
    account: str | None = None,
    destinations: list[str] | None = None,
    backend: str | None = None,
    limit: int | None = None,
    keep: bool = False,
) -> WhatsAppIngestResult:
    """Ingest archived WhatsApp webhook payloads from the local inbox."""

    configured_account = _configured_account(account)
    account_name = safe_account_name(configured_account)
    resolved_destinations = _validate_destinations(destinations)
    aggregate = WhatsAppIngestResult(account=account_name, destinations=resolved_destinations)
    files = list_inbox_files(account_name, state="pending")
    if limit is not None:
        files = files[:limit]

    for path in files:
        result = ingest_archived_whatsapp_payload(
            path,
            account=account_name,
            destinations=resolved_destinations,
            backend=backend,
            keep=keep,
        )
        aggregate.messages.extend(result.messages)
        aggregate.written_paths.extend(result.written_paths)
        aggregate.journal_entry_ids.extend(result.journal_entry_ids)
        aggregate.processed_paths.extend(result.processed_paths)
        aggregate.invalid_paths.extend(result.invalid_paths)
        aggregate.skipped_duplicates += result.skipped_duplicates
        aggregate.errors.extend(result.errors)
    aggregate.written_paths = sorted(set(aggregate.written_paths))
    aggregate.journal_entry_ids = sorted(set(aggregate.journal_entry_ids))
    return aggregate


def ingest_archived_whatsapp_payload(
    path: Path,
    *,
    account: str | None = None,
    destinations: list[str] | None = None,
    backend: str | None = None,
    keep: bool = False,
) -> WhatsAppIngestResult:
    """Ingest one archived WhatsApp webhook payload into local destinations."""

    configured_account = _configured_account(account)
    account_name = safe_account_name(configured_account)
    resolved_destinations = _validate_destinations(destinations)
    result = WhatsAppIngestResult(account=account_name, destinations=resolved_destinations)

    try:
        wrapper = load_archived_whatsapp_payload(path)
    except Exception as exc:
        invalid_path = mark_inbox_file_invalid(path, account_name, f"Could not read JSON: {exc}")
        result.invalid_paths.append(str(invalid_path))
        result.errors.append(str(exc))
        return result

    payload = wrapper.get("payload")
    if not isinstance(payload, dict):
        invalid_path = mark_inbox_file_invalid(
            path,
            account_name,
            "Archived payload is not an object",
        )
        result.invalid_paths.append(str(invalid_path))
        result.errors.append("Archived payload is not an object")
        return result

    messages = normalize_whatsapp_payload(payload, account=account_name)
    if not messages:
        invalid_path = mark_inbox_file_invalid(
            path,
            account_name,
            "No WhatsApp messages or statuses found",
        )
        result.invalid_paths.append(str(invalid_path))
        result.errors.append("No WhatsApp messages or statuses found")
        return result

    for message in messages:
        message_result = write_whatsapp_message(
            message,
            destinations=resolved_destinations,
            backend=backend,
        )
        result.messages.append(message)
        result.written_paths.extend(message_result.written_paths)
        result.journal_entry_ids.extend(message_result.journal_entry_ids)
        result.skipped_duplicates += message_result.skipped_duplicates

    if keep:
        result.processed_paths.append(str(path))
    else:
        processed_path = move_inbox_file(path, account_name, "processed")
        result.processed_paths.append(str(processed_path))
    result.written_paths = sorted(set(result.written_paths))
    result.journal_entry_ids = sorted(set(result.journal_entry_ids))
    return result


def write_whatsapp_message(
    message: WhatsAppMessage,
    *,
    destinations: list[str] | None = None,
    backend: str | None = None,
) -> WhatsAppIngestResult:
    """Write one normalized WhatsApp message to selected destinations."""

    resolved_destinations = _validate_destinations(destinations)
    result = WhatsAppIngestResult(account=message.account, destinations=resolved_destinations)
    for destination in resolved_destinations:
        if destination == "team-inbox":
            _thread, appended, paths = append_message_to_thread(message)
            result.written_paths.extend(str(path) for path in paths)
            if not appended:
                result.skipped_duplicates += 1
        elif destination == "private-context":
            path = append_private_context_message(message)
            result.written_paths.append(str(path))
        elif destination == "memory":
            path = append_memory_message(message)
            result.written_paths.append(str(path))
        elif destination == "journal":
            entry_id = write_journal_message(message, backend=backend)
            result.journal_entry_ids.append(entry_id)
        else:
            raise ValueError(f"Unsupported WhatsApp destination: {destination}")
    result.messages.append(message)
    result.written_paths = sorted(set(result.written_paths))
    result.journal_entry_ids = sorted(set(result.journal_entry_ids))
    return result


def send_text_message(
    *,
    account: str | None,
    to: str,
    text: str,
    preview_url: bool = False,
    check_window: bool = True,
) -> WhatsAppSendResult:
    """Send a free-form WhatsApp text message and record it locally."""

    configured_account = _configured_account(account)
    account_name = safe_account_name(configured_account)
    recipient = canonical_phone(to)
    if check_window and not conversation_window_open(account_name, recipient):
        raise ValueError(
            "No inbound WhatsApp message from this recipient in the last 24 hours. "
            "Use `jarvis whatsapp send-template` for outbound starts or rerun with "
            "`--no-window-check` only when you know the provider will allow it."
        )
    client = MetaWhatsAppClient(account=configured_account)
    response = client.send_text(to=recipient.lstrip("+"), text=text, preview_url=preview_url)
    message = WhatsAppMessage(
        message_id=(
            _response_message_id(response)
            or _outbound_fallback_id(account_name, recipient, text)
        ),
        account=account_name,
        direction="outbound",
        sender="",
        recipient=recipient,
        timestamp=datetime.now(UTC),
        message_type="text",
        text=text,
        raw=response,
    )
    thread, _appended, paths = append_message_to_thread(message)
    return WhatsAppSendResult(
        account=account_name,
        to=recipient,
        provider_response=response,
        message=message,
        thread_id=thread.thread_id,
        written_paths=[str(path) for path in paths],
    )


def send_template_message(
    *,
    account: str | None,
    to: str,
    template: str,
    language_code: str = "en_US",
    components: list[dict[str, Any]] | None = None,
) -> WhatsAppSendResult:
    """Send an approved WhatsApp template and record the outbound event locally."""

    configured_account = _configured_account(account)
    account_name = safe_account_name(configured_account)
    recipient = canonical_phone(to)
    client = MetaWhatsAppClient(account=configured_account)
    response = client.send_template(
        to=recipient.lstrip("+"),
        template=template,
        language_code=language_code,
        components=components,
    )
    message = WhatsAppMessage(
        message_id=(
            _response_message_id(response)
            or _outbound_fallback_id(account_name, recipient, f"template:{template}")
        ),
        account=account_name,
        direction="outbound",
        sender="",
        recipient=recipient,
        timestamp=datetime.now(UTC),
        message_type="template",
        text=f"Template: {template} ({language_code})",
        raw=response,
    )
    thread, _appended, paths = append_message_to_thread(message)
    return WhatsAppSendResult(
        account=account_name,
        to=recipient,
        provider_response=response,
        message=message,
        thread_id=thread.thread_id,
        written_paths=[str(path) for path in paths],
    )


def conversation_window_open(
    account: str | None,
    contact: str,
    *,
    now: datetime | None = None,
    window_hours: int = 24,
) -> bool:
    """Return whether local thread history shows an open customer-service window."""

    from .storage import load_thread

    configured_account = _configured_account(account)
    thread_id = thread_id_for(configured_account, canonical_phone(contact))
    try:
        thread = load_thread(configured_account, thread_id)
    except FileNotFoundError:
        return False
    current = now or datetime.now(UTC)
    cutoff = current - timedelta(hours=window_hours)
    inbound_times = [
        message.timestamp
        for message in thread.messages
        if message.direction == "inbound" and message.timestamp >= cutoff
    ]
    return bool(inbound_times)


def append_private_context_message(message: WhatsAppMessage) -> Path:
    """Append one normalized WhatsApp message to a daily private-context log."""

    target = (
        whatsapp_root()
        / message.account
        / "messages"
        / str(message.timestamp.year)
        / message.timestamp.strftime("%b")
        / f"{message.timestamp.strftime('%d')}.md"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    if f"Message ID: {message.message_id}" in existing:
        return target
    if not target.exists():
        target.write_text(
            f"# WhatsApp Messages - {message.timestamp.strftime('%Y-%m-%d')}\n\n",
            encoding="utf-8",
        )
    with target.open("a", encoding="utf-8") as handle:
        handle.write(render_message_markdown(message))
        handle.write("\n")
    return target


def append_memory_message(message: WhatsAppMessage) -> Path:
    """Append one idempotent WhatsApp message event to private memory."""

    target = whatsapp_root().parent / "events.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(
            "# Events\n\n"
            "> One entry per `---` block with YAML frontmatter "
            "(created_at, status, source)\n",
            encoding="utf-8",
        )
    existing = target.read_text(encoding="utf-8", errors="ignore")
    memory_id = f"whatsapp:{message.message_id}"
    if f'memory_id: "{memory_id}"' in existing:
        return target
    body = render_message_markdown(message).strip()
    block = (
        "\n---\n"
        f"created_at: {message.timestamp.date().isoformat()}\n"
        "status: active\n"
        f"source: {json.dumps(f'whatsapp:{message.account}:{message.message_id}')}\n"
        f"title: {json.dumps(_message_title(message))}\n"
        f"memory_id: {json.dumps(memory_id)}\n"
        "---\n\n"
        f"{body}\n"
    )
    with target.open("a", encoding="utf-8") as handle:
        if existing and not existing.endswith("\n"):
            handle.write("\n")
        handle.write(block)
    return target


def write_journal_message(message: WhatsAppMessage, *, backend: str | None = None) -> str:
    """Write one WhatsApp message to the active journal backend."""

    service = JournalService(backend=backend)
    service.connect()
    entry = service.create_entry(
        title=_message_title(message),
        content=render_message_markdown(message),
        entry_date=message.timestamp.date(),
        tags=["whatsapp", message.account, message.direction],
    )
    return entry.id


def render_message_markdown(message: WhatsAppMessage) -> str:
    """Render a normalized WhatsApp message as Markdown."""

    body = message.text or _non_text_body(message)
    lines = [
        f"## {message.timestamp.isoformat()} - {message.direction.title()}",
        "",
        f"- Message ID: {message.message_id}",
        f"- Account: {message.account}",
        f"- Type: {message.message_type}",
        f"- From: {message.sender}",
        f"- To: {message.recipient}",
    ]
    if message.contact_name:
        lines.append(f"- Contact: {message.contact_name}")
    if message.status:
        lines.append(f"- Status: {message.status}")
    lines.extend(["", body.strip() or "[no text]", ""])
    return "\n".join(lines)


def _normalize_inbound_messages(
    messages: object,
    *,
    account: str,
    business_number: str,
    contact_names: dict[str, str],
) -> list[WhatsAppMessage]:
    normalized: list[WhatsAppMessage] = []
    if not isinstance(messages, list):
        return normalized
    for raw in messages:
        if not isinstance(raw, dict):
            continue
        sender = canonical_phone(str(raw.get("from") or ""))
        message_type = str(raw.get("type") or "unknown")
        message_id = str(raw.get("id") or _message_fingerprint(raw, account=account))
        media, text, location, contacts = _extract_message_content(raw, message_type)
        normalized.append(
            WhatsAppMessage(
                message_id=message_id,
                account=account,
                direction="inbound",
                sender=sender,
                recipient=business_number,
                contact_name=contact_names.get(sender.lstrip("+"), ""),
                timestamp=_parse_unix_timestamp(raw.get("timestamp")),
                message_type=message_type,
                text=text,
                media=media,
                location=location,
                contacts=contacts,
                raw=raw,
            )
        )
    return normalized


def _normalize_statuses(
    statuses: object,
    *,
    account: str,
    business_number: str,
) -> list[WhatsAppMessage]:
    normalized: list[WhatsAppMessage] = []
    if not isinstance(statuses, list):
        return normalized
    for raw in statuses:
        if not isinstance(raw, dict):
            continue
        recipient = canonical_phone(str(raw.get("recipient_id") or ""))
        status = str(raw.get("status") or "unknown")
        message_id = str(raw.get("id") or _message_fingerprint(raw, account=account))
        timestamp = _parse_unix_timestamp(raw.get("timestamp"))
        normalized.append(
            WhatsAppMessage(
                message_id=f"status:{message_id}:{int(timestamp.timestamp())}:{status}",
                account=account,
                direction="status",
                sender=business_number,
                recipient=recipient,
                timestamp=timestamp,
                message_type="status",
                text=f"WhatsApp delivery status: {status}",
                status=status,
                raw=raw,
            )
        )
    return normalized


def _extract_message_content(
    raw: dict[str, Any],
    message_type: str,
) -> tuple[dict[str, Any], str, dict[str, Any], list[dict[str, Any]]]:
    media: dict[str, Any] = {}
    text = ""
    location: dict[str, Any] = {}
    contacts: list[dict[str, Any]] = []

    if message_type == "text" and isinstance(raw.get("text"), dict):
        text = str(raw["text"].get("body") or "").strip()
    elif message_type in {"image", "audio", "document", "video", "sticker"}:
        value = raw.get(message_type)
        if isinstance(value, dict):
            media = dict(value)
            caption = str(value.get("caption") or "").strip()
            text = caption
    elif message_type == "location" and isinstance(raw.get("location"), dict):
        location = dict(raw["location"])
        text = str(location.get("name") or location.get("address") or "").strip()
    elif message_type == "contacts" and isinstance(raw.get("contacts"), list):
        contacts = [item for item in raw["contacts"] if isinstance(item, dict)]
        text = "; ".join(
            str(item.get("name", {}).get("formatted_name") or "").strip()
            for item in contacts
            if isinstance(item.get("name"), dict)
        ).strip("; ")
    elif isinstance(raw.get(message_type), dict):
        value = raw[message_type]
        text = str(value.get("body") or value.get("title") or "").strip()

    return media, text, location, contacts


def _contact_names(raw_contacts: object) -> dict[str, str]:
    names: dict[str, str] = {}
    if not isinstance(raw_contacts, list):
        return names
    for contact in raw_contacts:
        if not isinstance(contact, dict):
            continue
        wa_id = str(contact.get("wa_id") or "").strip()
        profile = contact.get("profile")
        name = str(profile.get("name") or "").strip() if isinstance(profile, dict) else ""
        if wa_id and name:
            names[wa_id] = name
    return names


def _parse_unix_timestamp(value: object) -> datetime:
    try:
        return datetime.fromtimestamp(int(str(value)), UTC)
    except (TypeError, ValueError, OSError):
        return datetime.now(UTC)


def _validate_destinations(destinations: list[str] | None) -> list[str]:
    resolved = destinations or list(DEFAULT_DESTINATIONS)
    unsupported = sorted(set(resolved) - SUPPORTED_DESTINATIONS)
    if unsupported:
        raise ValueError(f"Unsupported WhatsApp destination(s): {', '.join(unsupported)}")
    return resolved


def _configured_account(account: str | None) -> str | None:
    if account:
        return account
    try:
        return load_config().whatsapp.default_account
    except Exception:
        return None


def _response_message_id(response: dict[str, Any]) -> str:
    messages = response.get("messages")
    if isinstance(messages, list) and messages and isinstance(messages[0], dict):
        return str(messages[0].get("id") or "").strip()
    return ""


def _outbound_fallback_id(account: str, recipient: str, text: str) -> str:
    basis = f"{account}:{recipient}:{datetime.now(UTC).isoformat()}:{text}"
    return f"local:{hashlib.sha256(basis.encode('utf-8')).hexdigest()[:24]}"


def _message_fingerprint(raw: dict[str, Any], *, account: str) -> str:
    encoded = json.dumps(raw, sort_keys=True, default=str)
    return f"local:{hashlib.sha256(f'{account}:{encoded}'.encode()).hexdigest()[:24]}"


def _message_title(message: WhatsAppMessage) -> str:
    contact = message.contact_name or message.contact_phone or "unknown"
    prefix = "WhatsApp"
    if message.direction == "status":
        return f"{prefix} status for {contact}"
    return f"{prefix} {message.direction} from {contact}"


def _non_text_body(message: WhatsAppMessage) -> str:
    if message.media:
        return json.dumps(message.media, indent=2, sort_keys=True)
    if message.location:
        return json.dumps(message.location, indent=2, sort_keys=True)
    if message.contacts:
        return json.dumps(message.contacts, indent=2, sort_keys=True)
    return ""
