"""Tests for configuration loader."""

from collections.abc import Generator
from pathlib import Path

import pytest

from jarvis.config.loader import (
    ConfigError,
    clear_config_cache,
    get_backend_token,
    get_config,
    init_config,
    load_config,
    redact_token,
    validate_config,
)
from jarvis.config.schema import JarvisConfig


class TestLoadConfig:
    """Test cases for load_config function."""

    @pytest.fixture(autouse=True)
    def clear_cache(self) -> Generator[None, None, None]:
        """Clear config cache before each test."""
        clear_config_cache()
        yield
        clear_config_cache()

    def test_load_config_no_file(self, tmp_path: Path) -> None:
        """Test loading config when no file exists uses defaults."""
        config = load_config(config_path=tmp_path / "nonexistent.yaml")
        assert config.active_backend == "anytype"
        assert config.version == 1

    def test_load_config_from_yaml(self, tmp_path: Path) -> None:
        """Test loading config from YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
version: 1
active_backend: anytype
backends:
  anytype:
    default_space_id: "my-space"
"""
        )
        config = load_config(config_path=config_file)
        assert config.backends.anytype.default_space_id == "my-space"

    def test_load_config_with_notion(self, tmp_path: Path) -> None:
        """Test loading config with Notion backend configured."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
version: 1
active_backend: notion
backends:
  notion:
    workspace_id: "ws-123"
    task_database_id: "tasks-456"
    journal_database_id: "journal-789"
"""
        )
        config = load_config(config_path=config_file)
        assert config.active_backend == "notion"
        assert config.backends.notion is not None
        assert config.backends.notion.workspace_id == "ws-123"

    def test_load_config_caching(self, tmp_path: Path) -> None:
        """Test config is cached after first load."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("version: 1\nactive_backend: anytype")

        config1 = load_config(config_path=config_file)
        config2 = load_config(config_path=config_file)
        assert config1 is config2

    def test_load_config_reload(self, tmp_path: Path) -> None:
        """Test reload=True bypasses cache."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("version: 1\nactive_backend: anytype")

        config1 = load_config(config_path=config_file)
        config2 = load_config(config_path=config_file, reload=True)
        assert config1 is not config2


class TestGetConfig:
    """Test cases for get_config function."""

    @pytest.fixture(autouse=True)
    def clear_cache(self) -> Generator[None, None, None]:
        """Clear config cache before each test."""
        clear_config_cache()
        yield
        clear_config_cache()

    def test_get_config_returns_jarvis_config(self) -> None:
        """Test get_config returns a JarvisConfig instance."""
        config = get_config()
        assert isinstance(config, JarvisConfig)


class TestGetBackendToken:
    """Test cases for get_backend_token function."""

    def test_get_token_specific_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting token from JARVIS_*_TOKEN variable."""
        monkeypatch.setenv("JARVIS_NOTION_TOKEN", "secret_specific")
        token = get_backend_token("notion")
        assert token == "secret_specific"

    def test_get_token_fallback_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting token from fallback *_TOKEN variable."""
        # Ensure specific var is not set
        monkeypatch.delenv("JARVIS_NOTION_TOKEN", raising=False)
        monkeypatch.setenv("NOTION_TOKEN", "secret_fallback")
        token = get_backend_token("notion")
        assert token == "secret_fallback"

    def test_get_token_specific_takes_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test specific var takes precedence over fallback."""
        monkeypatch.setenv("JARVIS_NOTION_TOKEN", "secret_specific")
        monkeypatch.setenv("NOTION_TOKEN", "secret_fallback")
        token = get_backend_token("notion")
        assert token == "secret_specific"

    def test_get_token_not_found_raises_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test missing token raises ConfigError."""
        monkeypatch.delenv("JARVIS_NOTION_TOKEN", raising=False)
        monkeypatch.delenv("NOTION_TOKEN", raising=False)
        with pytest.raises(ConfigError) as exc_info:
            get_backend_token("notion")
        assert "No API token found" in str(exc_info.value)
        assert exc_info.value.backend == "notion"


class TestRedactToken:
    """Test cases for redact_token function."""

    def test_redact_normal_token(self) -> None:
        """Test redacting a normal length token."""
        token = "secret_abcdefghijklmnop"
        redacted = redact_token(token)
        assert redacted == "secr****"

    def test_redact_short_token(self) -> None:
        """Test redacting a short token (<=4 chars)."""
        assert redact_token("abc") == "****"
        assert redact_token("abcd") == "****"

    def test_redact_five_char_token(self) -> None:
        """Test redacting a 5-char token."""
        assert redact_token("abcde") == "abcd****"

    def test_redact_empty_token(self) -> None:
        """Test redacting an empty token."""
        assert redact_token("") == "****"


class TestInitConfig:
    """Test cases for init_config function."""

    def test_init_config_creates_file(self, tmp_path: Path) -> None:
        """Test init_config creates config file."""
        config_path = tmp_path / "config.yaml"
        result = init_config(config_path=config_path)

        assert result == config_path
        assert config_path.exists()

    def test_init_config_contains_defaults(self, tmp_path: Path) -> None:
        """Test init_config writes default content."""
        config_path = tmp_path / "config.yaml"
        init_config(config_path=config_path)

        content = config_path.read_text()
        assert "active_backend: anytype" in content
        assert "version: 1" in content

    def test_init_config_creates_directory(self, tmp_path: Path) -> None:
        """Test init_config creates parent directory."""
        config_path = tmp_path / "subdir" / "config.yaml"
        init_config(config_path=config_path)

        assert config_path.parent.exists()
        assert config_path.exists()

    def test_init_config_existing_file_raises_error(self, tmp_path: Path) -> None:
        """Test init_config raises error if file exists."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("existing content")

        with pytest.raises(ConfigError) as exc_info:
            init_config(config_path=config_path)
        assert "already exists" in str(exc_info.value)

    def test_init_config_force_overwrites(self, tmp_path: Path) -> None:
        """Test init_config with force=True overwrites existing file."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("existing content")

        init_config(config_path=config_path, force=True)

        content = config_path.read_text()
        assert "existing content" not in content
        assert "active_backend: anytype" in content


class TestValidateConfig:
    """Test cases for validate_config function."""

    @pytest.fixture(autouse=True)
    def clear_cache(self) -> Generator[None, None, None]:
        """Clear config cache before each test."""
        clear_config_cache()
        yield
        clear_config_cache()

    def test_validate_config_anytype_ok(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test validation passes for AnyType with defaults."""
        # Create minimal config
        config_file = tmp_path / "config.yaml"
        config_file.write_text("active_backend: anytype")
        # Force load this config
        load_config(config_path=config_file, reload=True)

        issues = validate_config()
        assert issues == []

    def test_validate_config_notion_missing_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test validation fails if Notion active but not configured."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("active_backend: notion")
        load_config(config_path=config_file, reload=True)

        issues = validate_config()
        assert len(issues) == 1
        assert "not configured" in issues[0]

    def test_validate_config_notion_missing_token(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test validation warns if Notion token missing."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
active_backend: notion
backends:
  notion:
    workspace_id: "ws-123"
    task_database_id: "tasks-456"
    journal_database_id: "journal-789"
"""
        )
        load_config(config_path=config_file, reload=True)
        # Ensure token is not set
        monkeypatch.delenv("JARVIS_NOTION_TOKEN", raising=False)
        monkeypatch.delenv("NOTION_TOKEN", raising=False)

        issues = validate_config()
        assert len(issues) == 1
        assert "token not found" in issues[0]

    def test_validate_config_notion_with_token(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test validation passes if Notion properly configured with token."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
active_backend: notion
backends:
  notion:
    workspace_id: "ws-123"
    task_database_id: "tasks-456"
    journal_database_id: "journal-789"
"""
        )
        load_config(config_path=config_file, reload=True)
        monkeypatch.setenv("JARVIS_NOTION_TOKEN", "secret_test")

        issues = validate_config()
        assert issues == []
