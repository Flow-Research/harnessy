"""Meta WhatsApp Cloud API client."""

from __future__ import annotations

from typing import Any

import httpx

from jarvis.config import (
    get_whatsapp_access_token,
    get_whatsapp_account_config,
    get_whatsapp_phone_number_id,
)

GRAPH_API_BASE = "https://graph.facebook.com"


class MetaWhatsAppClient:
    """Minimal client for sending WhatsApp Cloud API messages."""

    def __init__(
        self,
        access_token: str | None = None,
        *,
        account: str | None = None,
        phone_number_id: str | None = None,
        api_version: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.account = account
        account_config = get_whatsapp_account_config(account)
        self.access_token = access_token or get_whatsapp_access_token(account)
        self.phone_number_id = phone_number_id or get_whatsapp_phone_number_id(account)
        self.api_version = api_version or account_config.api_version
        self.timeout = timeout

    def send_text(self, *, to: str, text: str, preview_url: bool = False) -> dict[str, Any]:
        """Send a free-form text message through the Cloud API."""

        body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": text, "preview_url": preview_url},
        }
        return self._post_message(body)

    def send_template(
        self,
        *,
        to: str,
        template: str,
        language_code: str = "en_US",
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send an approved WhatsApp template message."""

        template_body: dict[str, Any] = {
            "name": template,
            "language": {"code": language_code},
        }
        if components:
            template_body["components"] = components
        body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "template",
            "template": template_body,
        }
        return self._post_message(body)

    def _post_message(self, body: dict[str, Any]) -> dict[str, Any]:
        path = f"/{self.api_version}/{self.phone_number_id}/messages"
        with httpx.Client(base_url=GRAPH_API_BASE, timeout=self.timeout) as client:
            response = client.post(
                path,
                json=body,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else {}
