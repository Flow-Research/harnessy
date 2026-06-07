"""CLI tests for config setup flows."""

from click.testing import CliRunner

from jarvis.cli import cli
from jarvis.config.schema import JarvisConfig


class TestConfigCli:
    def test_fathom_setup_command(self, monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        cfg = JarvisConfig.model_validate(
            {
                "fathom": {
                    "default_account": "personal",
                    "accounts": {
                        "personal": {
                            "email": "durutheguru@gmail.com",
                            "api_key_env_var": "FATHOM_API_KEY_PERSONAL",
                            "webhook_secret_env_var": "FATHOM_WEBHOOK_SECRET_PERSONAL",
                        }
                    },
                }
            }
        )
        saved: dict[str, object] = {}

        monkeypatch.setattr("jarvis.config.load_config", lambda reload=False: cfg)
        monkeypatch.setattr(
            "jarvis.config.ensure_default_accounts",
            lambda config: [
                type(
                    "Acct",
                    (),
                    {
                        "name": "personal",
                        "email": "durutheguru@gmail.com",
                        "api_key_env_var": "FATHOM_API_KEY_PERSONAL",
                        "webhook_secret_env_var": "FATHOM_WEBHOOK_SECRET_PERSONAL",
                        "api_key": "",
                        "webhook_secret": "",
                    },
                )()
            ],
        )
        monkeypatch.setattr(
            "jarvis.config.save_config",
            lambda config: saved.setdefault("config", config),
        )
        monkeypatch.setattr(
            "jarvis.config.render_fathom_env_file",
            lambda accounts: 'export FATHOM_API_KEY_PERSONAL="abc"\n',
        )
        monkeypatch.setattr(
            "jarvis.config.write_env_file",
            lambda path, content: saved.setdefault("env", (path, content)),
        )
        monkeypatch.setattr(
            "jarvis.config.ensure_shell_profile_sources_env",
            lambda profile, env: saved.setdefault("profile", (profile, env)) or True,
        )
        monkeypatch.setattr("jarvis.config.default_env_file_path", lambda: tmp_path / "fathom.zsh")
        monkeypatch.setattr("jarvis.config.default_shell_profile_path", lambda: tmp_path / ".zshrc")

        prompts = iter(
            [
                "personal",
                "durutheguru@gmail.com",
                "FATHOM_API_KEY_PERSONAL",
                "FATHOM_WEBHOOK_SECRET_PERSONAL",
                "abc",
                "whsec_123",
            ]
        )
        monkeypatch.setattr("click.prompt", lambda *args, **kwargs: next(prompts))
        confirms = iter([True, True])
        monkeypatch.setattr("click.confirm", lambda *args, **kwargs: next(confirms))

        result = runner.invoke(cli, ["config", "fathom-setup"])
        assert result.exit_code == 0
        assert "Fathom config updated" in result.output

    def test_whatsapp_setup_command(self, monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
        runner = CliRunner()
        cfg = JarvisConfig.model_validate(
            {
                "whatsapp": {
                    "default_account": "personal",
                    "accounts": {
                        "personal": {
                            "phone_number_id": "phone_123",
                            "business_account_id": "waba_123",
                            "access_token_env_var": "JARVIS_WHATSAPP_META_TOKEN_PERSONAL",
                            "app_secret_env_var": ("JARVIS_WHATSAPP_META_APP_SECRET_PERSONAL"),
                            "verify_token_env_var": ("JARVIS_WHATSAPP_VERIFY_TOKEN_PERSONAL"),
                        }
                    },
                }
            }
        )
        saved: dict[str, object] = {}

        monkeypatch.setattr("jarvis.config.load_config", lambda reload=False: cfg)
        monkeypatch.setattr(
            "jarvis.config.ensure_default_whatsapp_accounts",
            lambda config: [
                type(
                    "Acct",
                    (),
                    {
                        "name": "personal",
                        "phone_number_id": "phone_123",
                        "business_account_id": "waba_123",
                        "access_token_env_var": "JARVIS_WHATSAPP_META_TOKEN_PERSONAL",
                        "app_secret_env_var": ("JARVIS_WHATSAPP_META_APP_SECRET_PERSONAL"),
                        "verify_token_env_var": "JARVIS_WHATSAPP_VERIFY_TOKEN_PERSONAL",
                        "access_token": "",
                        "app_secret": "",
                        "verify_token": "",
                    },
                )()
            ],
        )
        monkeypatch.setattr(
            "jarvis.config.save_config",
            lambda config: saved.setdefault("config", config),
        )
        monkeypatch.setattr(
            "jarvis.config.render_whatsapp_env_file",
            lambda accounts: 'export JARVIS_WHATSAPP_META_TOKEN_PERSONAL="abc"\n',
        )
        monkeypatch.setattr(
            "jarvis.config.write_env_file",
            lambda path, content: saved.setdefault("env", (path, content)),
        )
        monkeypatch.setattr(
            "jarvis.config.ensure_shell_profile_sources_env",
            lambda profile, env: saved.setdefault("profile", (profile, env)) or True,
        )
        monkeypatch.setattr(
            "jarvis.config.default_whatsapp_env_file_path",
            lambda: tmp_path / "whatsapp.zsh",
        )
        monkeypatch.setattr("jarvis.config.default_shell_profile_path", lambda: tmp_path / ".zshrc")
        monkeypatch.setattr("jarvis.config.generate_whatsapp_verify_token", lambda: "generated")

        prompts = iter(
            [
                "personal",
                "phone_123",
                "waba_123",
                "JARVIS_WHATSAPP_META_TOKEN_PERSONAL",
                "JARVIS_WHATSAPP_META_APP_SECRET_PERSONAL",
                "JARVIS_WHATSAPP_VERIFY_TOKEN_PERSONAL",
                "abc",
                "appsecret",
                "verify",
            ]
        )
        monkeypatch.setattr("click.prompt", lambda *args, **kwargs: next(prompts))
        confirms = iter([True, True])
        monkeypatch.setattr("click.confirm", lambda *args, **kwargs: next(confirms))

        result = runner.invoke(cli, ["config", "whatsapp-setup"])
        assert result.exit_code == 0
        assert "WhatsApp config updated" in result.output
