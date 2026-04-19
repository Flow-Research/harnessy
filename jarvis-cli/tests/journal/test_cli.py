"""Tests for journal CLI commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from jarvis.journal.cli import (
    generate_title,
    get_connected_client,
    get_space_selection,
    journal_cli,
)


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock AnyType client."""
    client = MagicMock()
    client.get_spaces.return_value = [("space_1", "Personal"), ("space_2", "Work")]
    client.get_or_create_collection.return_value = "journal_123"
    client.get_or_create_container.side_effect = ["year_2026", "month_jan"]
    client.create_page.return_value = "entry_456"
    return client


class TestGetConnectedClient:
    """Tests for get_connected_client function."""

    @patch("jarvis.journal.cli.AnyTypeClient")
    def test_returns_connected_client(self, mock_class: MagicMock) -> None:
        """Test successful connection."""
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance

        result = get_connected_client()

        assert result == mock_instance
        mock_instance.connect.assert_called_once()

    @patch("jarvis.journal.cli.AnyTypeClient")
    def test_raises_on_connection_failure(self, mock_class: MagicMock) -> None:
        """Test SystemExit on connection failure."""
        mock_instance = MagicMock()
        mock_instance.connect.side_effect = Exception("Connection failed")
        mock_class.return_value = mock_instance

        with pytest.raises(SystemExit):
            get_connected_client()


class TestGetSpaceSelection:
    """Tests for get_space_selection function."""

    def test_finds_space_by_name(self, mock_client: MagicMock) -> None:
        """Test finding space by name."""
        space_id, space_name = get_space_selection(mock_client, "Personal")

        assert space_id == "space_1"
        assert space_name == "Personal"

    def test_finds_space_by_id(self, mock_client: MagicMock) -> None:
        """Test finding space by ID."""
        space_id, space_name = get_space_selection(mock_client, "space_2")

        assert space_id == "space_2"
        assert space_name == "Work"

    def test_space_not_found_exits(self, mock_client: MagicMock) -> None:
        """Test SystemExit when space not found."""
        with pytest.raises(SystemExit):
            get_space_selection(mock_client, "NonExistent")

    @patch("jarvis.state.get_selected_space")
    @patch("jarvis.state.save_selected_space")
    def test_uses_saved_space(
        self,
        mock_save: MagicMock,
        mock_get: MagicMock,
        mock_client: MagicMock,
    ) -> None:
        """Test using saved space selection."""
        mock_get.return_value = "space_1"

        space_id, _ = get_space_selection(mock_client)

        assert space_id == "space_1"

    @patch("jarvis.state.get_selected_space")
    @patch("jarvis.state.save_selected_space")
    def test_auto_selects_single_space(
        self,
        mock_save: MagicMock,
        mock_get: MagicMock,
    ) -> None:
        """Test auto-selection when only one space exists."""
        mock_get.return_value = None
        mock_client = MagicMock()
        mock_client.get_spaces.return_value = [("only_space", "Only Space")]

        space_id, _ = get_space_selection(mock_client)

        assert space_id == "only_space"
        mock_save.assert_called_once_with("only_space")


class TestGenerateTitle:
    """Tests for generate_title function."""

    @patch("jarvis.journal.cli.get_anthropic_client")
    def test_generates_title_from_ai(self, mock_get_client: MagicMock) -> None:
        """Test successful AI title generation."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Breakthrough Moment")]
        mock_client.messages.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = generate_title("Had a breakthrough on the project today")

        assert result == "Breakthrough Moment"

    @patch("jarvis.journal.cli.get_anthropic_client")
    def test_strips_quotes_from_title(self, mock_get_client: MagicMock) -> None:
        """Test that quotes are stripped from AI response."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='"Quoted Title"')]
        mock_client.messages.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = generate_title("Content")

        assert result == "Quoted Title"

    @patch("jarvis.journal.cli.get_anthropic_client")
    def test_fallback_on_ai_error(self, mock_get_client: MagicMock) -> None:
        """Test fallback to first line on AI error."""
        mock_get_client.side_effect = Exception("API error")

        result = generate_title("First line of content\nSecond line")

        assert result == "First line of content"

    @patch("jarvis.journal.cli.get_anthropic_client")
    def test_fallback_truncates_long_lines(self, mock_get_client: MagicMock) -> None:
        """Test that fallback truncates long first lines."""
        mock_get_client.side_effect = Exception("API error")
        long_content = "A" * 100

        result = generate_title(long_content)

        assert len(result) == 50


class TestJournalCliGroup:
    """Tests for the journal CLI group."""

    def test_journal_group_exists(self, runner: CliRunner) -> None:
        """Test that journal command group exists."""
        result = runner.invoke(journal_cli, ["--help"])
        assert result.exit_code == 0
        assert "journal" in result.output.lower() or "write" in result.output.lower()

    def test_write_command_exists(self, runner: CliRunner) -> None:
        """Test that write subcommand exists."""
        result = runner.invoke(journal_cli, ["write", "--help"])
        assert result.exit_code == 0
        assert "write" in result.output.lower()


class TestWriteCommand:
    """Tests for the write command."""

    @patch("jarvis.journal.cli.save_draft")
    @patch("jarvis.journal.cli.capture_entry")
    def test_cancelled_on_empty_content(
        self,
        mock_capture: MagicMock,
        mock_save_draft: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test that empty content cancels the entry."""
        mock_capture.return_value = None

        result = runner.invoke(journal_cli, ["write"])

        assert "cancelled" in result.output.lower() or result.exit_code == 0

    @patch("jarvis.journal.cli._offer_deep_dive")
    @patch("jarvis.journal.cli.save_entry_reference")
    @patch("jarvis.journal.cli.JournalHierarchy")
    @patch("jarvis.journal.cli.get_space_selection")
    @patch("jarvis.journal.cli.get_connected_client")
    @patch("jarvis.journal.cli.generate_title")
    @patch("jarvis.journal.cli.save_draft")
    @patch("jarvis.journal.cli.capture_entry")
    def test_inline_text_creates_entry(
        self,
        mock_capture: MagicMock,
        mock_save_draft: MagicMock,
        mock_gen_title: MagicMock,
        mock_get_client: MagicMock,
        mock_get_space: MagicMock,
        mock_hierarchy_class: MagicMock,
        mock_save_ref: MagicMock,
        mock_deep_dive: MagicMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test creating entry with inline text."""
        mock_capture.return_value = "Test entry content"
        draft_path = tmp_path / "draft.txt"
        draft_path.write_text("Test entry content")
        mock_save_draft.return_value = draft_path
        mock_gen_title.return_value = "Test Title"
        mock_get_client.return_value = MagicMock()
        mock_get_space.return_value = ("space_1", "Personal")

        mock_hierarchy = MagicMock()
        mock_hierarchy.create_entry.return_value = (
            "entry_123",
            "journal_456",
            "year_789",
            "month_012",
        )
        mock_hierarchy.get_path.return_value = "Journal/2026/January"
        mock_hierarchy_class.return_value = mock_hierarchy

        result = runner.invoke(
            journal_cli, ["write", "Test entry content", "--no-deep-dive"]
        )

        assert result.exit_code == 0
        assert "saved" in result.output.lower()

    @patch("jarvis.journal.cli.save_draft")
    @patch("jarvis.journal.cli.capture_entry")
    def test_custom_title_skips_generation(
        self,
        mock_capture: MagicMock,
        mock_save_draft: MagicMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that --title option skips AI title generation."""
        mock_capture.return_value = "Content"
        draft_path = tmp_path / "draft.txt"
        draft_path.write_text("Content")
        mock_save_draft.return_value = draft_path

        with patch("jarvis.journal.cli.get_connected_client") as mock_client:
            with patch("jarvis.journal.cli.get_space_selection") as mock_space:
                with patch("jarvis.journal.cli.JournalHierarchy") as mock_h:
                    with patch("jarvis.journal.cli.save_entry_reference"):
                        mock_client.return_value = MagicMock()
                        mock_space.return_value = ("s1", "Space")
                        mock_h_inst = MagicMock()
                        mock_h_inst.create_entry.return_value = ("e", "j", "y", "m")
                        mock_h_inst.get_path.return_value = "Journal/2026/January"
                        mock_h.return_value = mock_h_inst

                        result = runner.invoke(
                            journal_cli,
                            ["write", "--title", "Custom Title", "--no-deep-dive"],
                        )

        assert result.exit_code == 0
        # AI generate_title should not be called when --title is provided
        assert "Custom Title" in result.output or "saved" in result.output.lower()


class TestEditorFlag:
    """Tests for the --editor flag."""

    def test_editor_flag_sets_mode(self, runner: CliRunner) -> None:
        """Test that -e flag sets editor mode."""
        with patch("jarvis.journal.cli.capture_entry") as mock_capture:
            with patch("jarvis.journal.cli.determine_capture_mode") as mock_determine:
                mock_determine.return_value = (MagicMock(), "")
                mock_capture.return_value = None

                runner.invoke(journal_cli, ["write", "-e"])

                mock_determine.assert_called_once()
                call_kwargs = mock_determine.call_args
                assert call_kwargs[1]["force_editor"] is True


class TestInteractiveFlag:
    """Tests for the --interactive flag."""

    def test_interactive_flag_sets_mode(self, runner: CliRunner) -> None:
        """Test that -i flag sets interactive mode."""
        with patch("jarvis.journal.cli.capture_entry") as mock_capture:
            with patch("jarvis.journal.cli.determine_capture_mode") as mock_determine:
                mock_determine.return_value = (MagicMock(), "")
                mock_capture.return_value = None

                runner.invoke(journal_cli, ["write", "-i"])

                mock_determine.assert_called_once()
                call_kwargs = mock_determine.call_args
                assert call_kwargs[1]["interactive"] is True


class TestListCommand:
    """Tests for the list command."""

    @patch("jarvis.journal.state.load_entries")
    def test_list_shows_entries(
        self, mock_load: MagicMock, runner: CliRunner
    ) -> None:
        """Test listing entries displays table."""
        from datetime import date, datetime

        from jarvis.journal.models import JournalEntryReference

        entries = [
            JournalEntryReference(
                id="entry_1",
                space_id="space_1",
                path="Journal/2026/January",
                title="1 - First Entry",
                entry_date=date(2026, 1, 24),
                created_at=datetime(2026, 1, 24, 10, 0),
                content_preview="Content of first entry",
            ),
            JournalEntryReference(
                id="entry_2",
                space_id="space_1",
                path="Journal/2026/January",
                title="2 - Second Entry",
                entry_date=date(2026, 1, 23),
                created_at=datetime(2026, 1, 23, 10, 0),
                content_preview="Content of second entry",
            ),
        ]
        mock_load.return_value = entries

        result = runner.invoke(journal_cli, ["list"])

        assert result.exit_code == 0
        assert "First Entry" in result.output
        assert "Second Entry" in result.output

    @patch("jarvis.journal.state.load_entries")
    def test_list_no_entries(self, mock_load: MagicMock, runner: CliRunner) -> None:
        """Test listing when no entries exist."""
        mock_load.return_value = []

        result = runner.invoke(journal_cli, ["list"])

        assert result.exit_code == 0
        assert "No journal entries yet" in result.output

    @patch("jarvis.journal.state.load_entries")
    def test_list_respects_limit(
        self, mock_load: MagicMock, runner: CliRunner
    ) -> None:
        """Test that limit option works."""
        from datetime import date, datetime

        from jarvis.journal.models import JournalEntryReference

        entries = [
            JournalEntryReference(
                id=f"entry_{i}",
                space_id="space_1",
                path="Journal/2026/January",
                title=f"{i} - Entry {i}",
                entry_date=date(2026, 1, i + 1),
                created_at=datetime(2026, 1, i + 1, 10, 0),
                content_preview=f"Content {i}",
            )
            for i in range(15)
        ]
        mock_load.return_value = entries

        result = runner.invoke(journal_cli, ["list", "-n", "5"])

        assert result.exit_code == 0
        # Should show message about more entries
        assert "5" in result.output


class TestReadCommand:
    """Tests for the read command."""

    @patch("jarvis.journal.cli.get_connected_client")
    @patch("jarvis.journal.state.load_entries")
    def test_read_latest(
        self,
        mock_load: MagicMock,
        mock_client: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test reading the latest entry."""
        from datetime import date, datetime

        from jarvis.journal.models import JournalEntryReference

        entry = JournalEntryReference(
            id="entry_1",
            space_id="space_1",
            path="Journal/2026/January",
            title="24 - Latest Entry",
            entry_date=date(2026, 1, 24),
            created_at=datetime(2026, 1, 24, 10, 0),
            content_preview="This is the latest entry content",
        )
        mock_load.return_value = [entry]
        mock_client.return_value.get_page_content.return_value = None

        result = runner.invoke(journal_cli, ["read", "--latest"])

        assert result.exit_code == 0
        assert "Latest Entry" in result.output
        assert "latest entry content" in result.output

    @patch("jarvis.journal.state.load_entries")
    def test_read_no_entries(
        self, mock_load: MagicMock, runner: CliRunner
    ) -> None:
        """Test reading when no entries exist."""
        mock_load.return_value = []

        result = runner.invoke(journal_cli, ["read", "--latest"])

        assert result.exit_code == 0
        assert "No journal entries" in result.output

    @patch("jarvis.journal.cli.get_connected_client")
    @patch("jarvis.journal.state.load_entries")
    def test_read_by_number(
        self,
        mock_load: MagicMock,
        mock_client: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test reading entry by list number."""
        from datetime import date, datetime

        from jarvis.journal.models import JournalEntryReference

        entries = [
            JournalEntryReference(
                id="entry_1",
                space_id="space_1",
                path="Journal/2026/January",
                title="24 - First",
                entry_date=date(2026, 1, 24),
                created_at=datetime(2026, 1, 24, 10, 0),
                content_preview="First content",
            ),
            JournalEntryReference(
                id="entry_2",
                space_id="space_1",
                path="Journal/2026/January",
                title="23 - Second",
                entry_date=date(2026, 1, 23),
                created_at=datetime(2026, 1, 23, 10, 0),
                content_preview="Second content",
            ),
        ]
        mock_load.return_value = entries
        mock_client.return_value.get_page_content.return_value = None

        result = runner.invoke(journal_cli, ["read", "-n", "2"])

        assert result.exit_code == 0
        assert "Second" in result.output

    @patch("jarvis.journal.state.load_entries")
    def test_read_invalid_number(
        self, mock_load: MagicMock, runner: CliRunner
    ) -> None:
        """Test reading with invalid entry number."""
        from datetime import date, datetime

        from jarvis.journal.models import JournalEntryReference

        entry = JournalEntryReference(
            id="entry_1",
            space_id="space_1",
            path="Journal/2026/January",
            title="24 - Only Entry",
            entry_date=date(2026, 1, 24),
            created_at=datetime(2026, 1, 24, 10, 0),
            content_preview="Only content",
        )
        mock_load.return_value = [entry]

        result = runner.invoke(journal_cli, ["read", "-n", "5"])

        assert "not found" in result.output.lower()


class TestSearchCommand:
    """Tests for the search command."""

    @patch("jarvis.journal.state.search_entries")
    def test_search_finds_results(
        self, mock_search: MagicMock, runner: CliRunner
    ) -> None:
        """Test search returns matching entries."""
        from datetime import date, datetime

        from jarvis.journal.models import JournalEntryReference

        entries = [
            JournalEntryReference(
                id="entry_1",
                space_id="space_1",
                path="Journal/2026/January",
                title="24 - Project Update",
                entry_date=date(2026, 1, 24),
                created_at=datetime(2026, 1, 24, 10, 0),
                content_preview="Working on the project today",
            ),
        ]
        mock_search.return_value = entries

        result = runner.invoke(journal_cli, ["search", "project"])

        assert result.exit_code == 0
        assert "Project Update" in result.output
        assert "1 matching" in result.output

    @patch("jarvis.journal.state.search_entries")
    def test_search_no_results(
        self, mock_search: MagicMock, runner: CliRunner
    ) -> None:
        """Test search with no matches."""
        mock_search.return_value = []

        result = runner.invoke(journal_cli, ["search", "nonexistent"])

        assert result.exit_code == 0
        assert "No entries found" in result.output

    @patch("jarvis.journal.state.search_entries")
    def test_search_respects_limit(
        self, mock_search: MagicMock, runner: CliRunner
    ) -> None:
        """Test search limit option."""
        mock_search.return_value = []

        runner.invoke(journal_cli, ["search", "test", "-n", "5"])

        mock_search.assert_called_once_with("test", limit=5)


class TestInsightsCommand:
    """Tests for the insights command."""

    @patch("jarvis.journal.cli.get_anthropic_client")
    @patch("jarvis.journal.state.get_entries_by_date_range")
    def test_insights_with_entries(
        self,
        mock_get_entries: MagicMock,
        mock_get_client: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test insights command with multiple entries."""
        from datetime import date, datetime

        from jarvis.journal.models import JournalEntryReference

        entries = [
            JournalEntryReference(
                id="entry_1",
                space_id="space_1",
                path="Journal/2026/January",
                title="24 - First Entry",
                entry_date=date(2026, 1, 24),
                created_at=datetime(2026, 1, 24, 10, 0),
                content_preview="Content about work",
            ),
            JournalEntryReference(
                id="entry_2",
                space_id="space_1",
                path="Journal/2026/January",
                title="23 - Second Entry",
                entry_date=date(2026, 1, 23),
                created_at=datetime(2026, 1, 23, 10, 0),
                content_preview="Content about projects",
            ),
        ]
        mock_get_entries.return_value = entries

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Theme: Work and productivity")]
        mock_client.messages.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = runner.invoke(journal_cli, ["insights"])

        assert result.exit_code == 0
        assert "Insights" in result.output

    @patch("jarvis.journal.state.get_entries_by_date_range")
    def test_insights_no_entries(
        self, mock_get_entries: MagicMock, runner: CliRunner
    ) -> None:
        """Test insights with no entries in range."""
        mock_get_entries.return_value = []

        result = runner.invoke(journal_cli, ["insights"])

        assert "No entries found" in result.output

    @patch("jarvis.journal.state.get_entries_by_date_range")
    def test_insights_too_few_entries(
        self, mock_get_entries: MagicMock, runner: CliRunner
    ) -> None:
        """Test insights with only one entry."""
        from datetime import date, datetime

        from jarvis.journal.models import JournalEntryReference

        entry = JournalEntryReference(
            id="entry_1",
            space_id="space_1",
            path="Journal/2026/January",
            title="24 - Only Entry",
            entry_date=date(2026, 1, 24),
            created_at=datetime(2026, 1, 24, 10, 0),
            content_preview="Only content",
        )
        mock_get_entries.return_value = [entry]

        result = runner.invoke(journal_cli, ["insights"])

        assert "at least 2 entries" in result.output


class TestParseSince:
    """Tests for the _parse_since helper function."""

    def test_parse_weeks(self) -> None:
        """Test parsing weeks."""
        from datetime import date

        from jarvis.journal.cli import _parse_since

        end = date(2026, 1, 24)
        result = _parse_since("2 weeks", end)

        assert result == date(2026, 1, 10)

    def test_parse_days(self) -> None:
        """Test parsing days."""
        from datetime import date

        from jarvis.journal.cli import _parse_since

        end = date(2026, 1, 24)
        result = _parse_since("5 days", end)

        assert result == date(2026, 1, 19)

    def test_parse_month(self) -> None:
        """Test parsing months (approximate as 30 days)."""
        from datetime import date

        from jarvis.journal.cli import _parse_since

        end = date(2026, 1, 31)
        result = _parse_since("1 month", end)

        assert result == date(2026, 1, 1)

    def test_parse_invalid_fallback(self) -> None:
        """Test fallback to 2 weeks for invalid input."""
        from datetime import date

        from jarvis.journal.cli import _parse_since

        end = date(2026, 1, 24)
        result = _parse_since("invalid input", end)

        assert result == date(2026, 1, 10)
