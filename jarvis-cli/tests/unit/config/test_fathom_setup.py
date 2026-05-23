"""Tests for Fathom setup helpers."""

from pathlib import Path

from jarvis.config.fathom_setup import (
    default_env_var,
    ensure_default_accounts,
    ensure_shell_profile_sources_env,
    render_fathom_env_file,
    update_managed_env_var,
)
from jarvis.config.schema import JarvisConfig


class TestDefaultEnvVar:
    def test_builds_slugged_env_var(self) -> None:
        assert default_env_var("FATHOM_API_KEY", "personal") == "FATHOM_API_KEY_PERSONAL"
        assert default_env_var("FATHOM_API_KEY", "client-x") == "FATHOM_API_KEY_CLIENT_X"


class TestEnsureDefaultAccounts:
    def test_seeds_accounts_when_missing(self) -> None:
        config = JarvisConfig()
        accounts = ensure_default_accounts(config)
        assert [account.name for account in accounts] == ["personal", "work"]
        assert config.fathom.default_account == "personal"

    def test_preserves_existing_accounts_and_fills_blank_env_vars(self) -> None:
        config = JarvisConfig.model_validate(
            {
                "fathom": {
                    "accounts": {
                        "personal": {
                            "email": "me@gmail.com",
                            "api_key_env_var": "",
                            "webhook_secret_env_var": "",
                        }
                    }
                }
            }
        )
        accounts = ensure_default_accounts(config)
        assert accounts[0].api_key_env_var == "FATHOM_API_KEY_PERSONAL"
        assert accounts[0].webhook_secret_env_var == "FATHOM_WEBHOOK_SECRET_PERSONAL"


class TestRenderFathomEnvFile:
    def test_renders_only_present_secrets(self) -> None:
        config = JarvisConfig()
        accounts = ensure_default_accounts(config)
        accounts[0].api_key = "abc"
        accounts[0].webhook_secret = "whsec_def"
        content = render_fathom_env_file(accounts)
        assert 'export FATHOM_API_KEY_PERSONAL="abc"' in content
        assert 'export FATHOM_WEBHOOK_SECRET_PERSONAL="whsec_def"' in content
        assert "FATHOM_API_KEY_WORK" not in content


class TestUpdateManagedEnvVar:
    def test_upserts_one_secret_without_clobbering_existing_values(self, tmp_path: Path) -> None:
        env_file = tmp_path / "fathom.zsh"
        env_file.write_text(
            "# existing\n"
            'export FATHOM_API_KEY_PERSONAL="api_key"\n'
            'export FATHOM_WEBHOOK_SECRET_PERSONAL="old"\n',
            encoding="utf-8",
        )

        update_managed_env_var(env_file, "FATHOM_WEBHOOK_SECRET_PERSONAL", "new")

        content = env_file.read_text(encoding="utf-8")
        assert 'export FATHOM_API_KEY_PERSONAL="api_key"' in content
        assert 'export FATHOM_WEBHOOK_SECRET_PERSONAL="new"' in content
        assert "old" not in content


class TestEnsureShellProfileSourcesEnv:
    def test_appends_source_once(self, tmp_path: Path) -> None:
        profile = tmp_path / ".zshrc"
        env_file = tmp_path / "fathom.zsh"
        changed = ensure_shell_profile_sources_env(profile, env_file)
        assert changed is True
        changed_again = ensure_shell_profile_sources_env(profile, env_file)
        assert changed_again is False
