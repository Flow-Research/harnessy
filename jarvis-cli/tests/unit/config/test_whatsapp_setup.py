"""Tests for WhatsApp setup helpers."""

from jarvis.config.schema import JarvisConfig
from jarvis.config.whatsapp_setup import (
    ensure_default_whatsapp_accounts,
    render_whatsapp_env_file,
)


class TestEnsureDefaultWhatsAppAccounts:
    def test_seeds_personal_account_when_missing(self) -> None:
        config = JarvisConfig()

        accounts = ensure_default_whatsapp_accounts(config)

        assert [account.name for account in accounts] == ["personal"]
        assert config.whatsapp.default_account == "personal"
        assert accounts[0].access_token_env_var == "JARVIS_WHATSAPP_META_TOKEN_PERSONAL"

    def test_preserves_existing_account_and_fills_blank_env_vars(self) -> None:
        config = JarvisConfig.model_validate(
            {
                "whatsapp": {
                    "accounts": {
                        "client-x": {
                            "phone_number_id": "phone_123",
                            "access_token_env_var": "",
                            "app_secret_env_var": "",
                            "verify_token_env_var": "",
                        }
                    }
                }
            }
        )

        accounts = ensure_default_whatsapp_accounts(config)

        assert accounts[0].phone_number_id == "phone_123"
        assert accounts[0].access_token_env_var == "JARVIS_WHATSAPP_META_TOKEN_CLIENT_X"
        assert accounts[0].app_secret_env_var == "JARVIS_WHATSAPP_META_APP_SECRET_CLIENT_X"
        assert accounts[0].verify_token_env_var == "JARVIS_WHATSAPP_VERIFY_TOKEN_CLIENT_X"


class TestRenderWhatsAppEnvFile:
    def test_renders_only_present_secrets(self) -> None:
        config = JarvisConfig()
        accounts = ensure_default_whatsapp_accounts(config)
        accounts[0].access_token = "token"
        accounts[0].app_secret = "secret"
        accounts[0].verify_token = "verify"

        content = render_whatsapp_env_file(accounts)

        assert 'export JARVIS_WHATSAPP_META_TOKEN_PERSONAL="token"' in content
        assert 'export JARVIS_WHATSAPP_META_APP_SECRET_PERSONAL="secret"' in content
        assert 'export JARVIS_WHATSAPP_VERIFY_TOKEN_PERSONAL="verify"' in content
