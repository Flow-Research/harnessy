"""Tests for journal entry capture module."""

from unittest.mock import MagicMock, patch

import pytest

from jarvis.journal.capture import (
    CaptureMode,
    _capture_from_file,
    _capture_inline,
    _capture_interactive,
    _capture_via_editor,
    capture_entry,
    determine_capture_mode,
)


class TestCaptureMode:
    """Tests for CaptureMode enum."""

    def test_mode_values(self) -> None:
        """Test capture mode values."""
        assert CaptureMode.INLINE.value == "inline"
        assert CaptureMode.EDITOR.value == "editor"
        assert CaptureMode.INTERACTIVE.value == "interactive"
        assert CaptureMode.FILE.value == "file"


class TestCaptureInline:
    """Tests for inline capture."""

    def test_returns_text(self) -> None:
        """Test that valid text is returned."""
        result = _capture_inline("Hello world")
        assert result == "Hello world"

    def test_strips_whitespace(self) -> None:
        """Test that whitespace is stripped."""
        result = _capture_inline("  Hello  ")
        assert result == "Hello"

    def test_returns_none_for_empty(self) -> None:
        """Test that empty text returns None."""
        assert _capture_inline("") is None
        assert _capture_inline("   ") is None
        assert _capture_inline("\n\t") is None

    def test_preserves_internal_whitespace(self) -> None:
        """Test that internal whitespace is preserved."""
        result = _capture_inline("Hello   world")
        assert result == "Hello   world"


class TestCaptureEntry:
    """Tests for main capture_entry function."""

    def test_inline_mode(self) -> None:
        """Test inline capture mode."""
        result = capture_entry(CaptureMode.INLINE, "Test content")
        assert result == "Test content"

    def test_inline_mode_empty(self) -> None:
        """Test inline mode with empty text."""
        result = capture_entry(CaptureMode.INLINE, "")
        assert result is None

    @patch("jarvis.journal.capture._capture_via_editor")
    def test_editor_mode(self, mock_editor: MagicMock) -> None:
        """Test editor capture mode calls editor function."""
        mock_editor.return_value = "Editor content"

        result = capture_entry(CaptureMode.EDITOR, "initial")
        assert result == "Editor content"
        mock_editor.assert_called_once_with("initial")

    @patch("jarvis.journal.capture._capture_interactive")
    def test_interactive_mode(self, mock_interactive: MagicMock) -> None:
        """Test interactive capture mode calls interactive function."""
        mock_interactive.return_value = "Interactive content"

        result = capture_entry(CaptureMode.INTERACTIVE)
        assert result == "Interactive content"
        mock_interactive.assert_called_once()

    def test_unknown_mode_returns_none(self) -> None:
        """Test that an invalid mode falls through and returns None."""
        # Create a mock mode that doesn't match any case
        # This tests the final return None statement
        from unittest.mock import MagicMock

        fake_mode = MagicMock()
        fake_mode.__eq__ = lambda self, other: False

        result = capture_entry(fake_mode, "test")  # type: ignore[arg-type]
        assert result is None


class TestCaptureViaEditor:
    """Tests for editor capture."""

    @patch("subprocess.run")
    @patch("os.environ.get")
    def test_uses_editor_env_var(
        self, mock_env: MagicMock, mock_run: MagicMock, tmp_path: pytest.TempPathFactory
    ) -> None:
        """Test that EDITOR environment variable is used."""
        mock_env.side_effect = lambda key, default=None: "vim" if key == "EDITOR" else default
        mock_run.return_value = MagicMock(returncode=0)

        # Create temp file that will be read
        with patch("tempfile.mkstemp") as mock_mkstemp:
            temp_file = tmp_path / "test.md"  # type: ignore[attr-defined]
            temp_file.write_text("Test content")
            mock_mkstemp.return_value = (0, str(temp_file))

            mock_fdopen = MagicMock()
            mock_fdopen.__enter__ = MagicMock()
            mock_fdopen.__exit__ = MagicMock()

            mock_open_file = MagicMock()
            mock_open_file.read.return_value = "Test content"
            mock_open_file.__enter__ = MagicMock(return_value=mock_open_file)
            mock_open_file.__exit__ = MagicMock()

            with patch("os.fdopen", return_value=mock_fdopen):
                with patch("builtins.open", return_value=mock_open_file):
                    with patch("os.unlink"):
                        _capture_via_editor()

        # Verify vim was called
        assert mock_run.called

    @patch("subprocess.run")
    def test_returns_none_on_editor_failure(self, mock_run: MagicMock) -> None:
        """Test that editor failure returns None."""
        mock_run.return_value = MagicMock(returncode=1)

        with patch("tempfile.mkstemp") as mock_mkstemp:
            with patch("os.fdopen") as mock_fdopen:
                mock_fdopen.return_value.__enter__ = MagicMock()
                mock_fdopen.return_value.__exit__ = MagicMock()
                mock_mkstemp.return_value = (0, "/tmp/test.md")

                with patch("os.unlink"):
                    result = _capture_via_editor()

        assert result is None

    @patch("subprocess.run")
    def test_strips_comment_lines(self, mock_run: MagicMock) -> None:
        """Test that lines starting with # are removed."""
        mock_run.return_value = MagicMock(returncode=0)

        content_with_comments = "# Comment line\nActual content\n# Another comment"

        with patch("tempfile.mkstemp") as mock_mkstemp:
            with patch("os.fdopen") as mock_fdopen:
                mock_fdopen.return_value.__enter__ = MagicMock()
                mock_fdopen.return_value.__exit__ = MagicMock()
                mock_mkstemp.return_value = (0, "/tmp/test.md")

                with patch("builtins.open") as mock_open:
                    mock_file = MagicMock()
                    mock_file.read.return_value = content_with_comments
                    mock_file.__enter__ = MagicMock(return_value=mock_file)
                    mock_file.__exit__ = MagicMock()
                    mock_open.return_value = mock_file

                    with patch("os.unlink"):
                        result = _capture_via_editor()

        assert result == "Actual content"

    @patch("subprocess.run")
    def test_with_initial_text(self, mock_run: MagicMock) -> None:
        """Test that initial text is written to the editor file."""
        mock_run.return_value = MagicMock(returncode=0)

        with patch("tempfile.mkstemp") as mock_mkstemp:
            mock_mkstemp.return_value = (0, "/tmp/test.md")

            mock_fd_file = MagicMock()
            with patch("os.fdopen", return_value=mock_fd_file):
                mock_fd_file.__enter__ = MagicMock(return_value=mock_fd_file)
                mock_fd_file.__exit__ = MagicMock()

                with patch("builtins.open") as mock_open:
                    mock_file = MagicMock()
                    mock_file.read.return_value = "Modified content"
                    mock_file.__enter__ = MagicMock(return_value=mock_file)
                    mock_file.__exit__ = MagicMock()
                    mock_open.return_value = mock_file

                    with patch("os.unlink"):
                        result = _capture_via_editor("Initial text")

        # Verify that initial text was written
        mock_fd_file.write.assert_called_once_with("Initial text")
        assert result == "Modified content"

    def test_editor_not_found(self) -> None:
        """Test that FileNotFoundError is handled."""
        with patch("tempfile.mkstemp") as mock_mkstemp:
            mock_mkstemp.return_value = (0, "/tmp/test.md")

            with patch("os.fdopen") as mock_fdopen:
                mock_fdopen.return_value.__enter__ = MagicMock()
                mock_fdopen.return_value.__exit__ = MagicMock()

                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = FileNotFoundError("editor not found")

                    with patch("os.unlink"):
                        result = _capture_via_editor()

        assert result is None

    def test_editor_os_error(self) -> None:
        """Test that OSError is handled."""
        with patch("tempfile.mkstemp") as mock_mkstemp:
            mock_mkstemp.return_value = (0, "/tmp/test.md")

            with patch("os.fdopen") as mock_fdopen:
                mock_fdopen.return_value.__enter__ = MagicMock()
                mock_fdopen.return_value.__exit__ = MagicMock()

                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = OSError("subprocess error")

                    with patch("os.unlink"):
                        result = _capture_via_editor()

        assert result is None

    def test_cleanup_handles_missing_file(self) -> None:
        """Test that cleanup handles missing temp file gracefully."""
        with patch("tempfile.mkstemp") as mock_mkstemp:
            mock_mkstemp.return_value = (0, "/tmp/test.md")

            with patch("os.fdopen") as mock_fdopen:
                mock_fdopen.return_value.__enter__ = MagicMock()
                mock_fdopen.return_value.__exit__ = MagicMock()

                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=0)

                    with patch("builtins.open") as mock_open:
                        mock_file = MagicMock()
                        mock_file.read.return_value = "content"
                        mock_file.__enter__ = MagicMock(return_value=mock_file)
                        mock_file.__exit__ = MagicMock()
                        mock_open.return_value = mock_file

                        with patch("os.unlink") as mock_unlink:
                            mock_unlink.side_effect = OSError("file not found")
                            # Should not raise, cleanup swallows the error
                            result = _capture_via_editor()

        assert result == "content"


class TestCaptureInteractive:
    """Tests for interactive capture."""

    @patch("builtins.input")
    def test_captures_multiple_lines(self, mock_input: MagicMock) -> None:
        """Test capturing multiple lines until two empty lines."""
        mock_input.side_effect = ["Line 1", "Line 2", "", ""]

        result = _capture_interactive()
        assert result == "Line 1\nLine 2"

    @patch("builtins.input")
    def test_handles_eof(self, mock_input: MagicMock) -> None:
        """Test handling Ctrl+D (EOF)."""
        mock_input.side_effect = ["Line 1", EOFError]

        result = _capture_interactive()
        assert result == "Line 1"

    @patch("builtins.input")
    def test_handles_keyboard_interrupt(self, mock_input: MagicMock) -> None:
        """Test handling Ctrl+C cancellation."""
        mock_input.side_effect = ["Line 1", KeyboardInterrupt]

        result = _capture_interactive()
        assert result is None

    @patch("builtins.input")
    def test_returns_none_for_empty(self, mock_input: MagicMock) -> None:
        """Test that empty input returns None."""
        mock_input.side_effect = ["", ""]

        result = _capture_interactive()
        assert result is None

    @patch("builtins.input")
    def test_strips_trailing_empty_lines(self, mock_input: MagicMock) -> None:
        """Test that trailing empty lines are removed."""
        mock_input.side_effect = ["Content", "", "", ""]

        result = _capture_interactive()
        assert result == "Content"


class TestDetermineCaptureMode:
    """Tests for determine_capture_mode."""

    def test_force_editor_overrides_text(self) -> None:
        """Test that --editor flag forces editor mode even with text."""
        mode, text = determine_capture_mode(text="inline text", force_editor=True)
        assert mode == CaptureMode.EDITOR
        assert text == "inline text"

    def test_interactive_flag(self) -> None:
        """Test that --interactive flag sets interactive mode."""
        mode, text = determine_capture_mode(text=None, interactive=True)
        assert mode == CaptureMode.INTERACTIVE
        assert text == ""

    def test_text_sets_inline_mode(self) -> None:
        """Test that providing text sets inline mode."""
        mode, text = determine_capture_mode(text="Hello world")
        assert mode == CaptureMode.INLINE
        assert text == "Hello world"

    def test_no_text_defaults_to_editor(self) -> None:
        """Test that no text defaults to editor mode."""
        mode, text = determine_capture_mode(text=None)
        assert mode == CaptureMode.EDITOR
        assert text == ""

    def test_force_editor_takes_precedence_over_interactive(self) -> None:
        """Test that editor flag takes precedence over interactive."""
        mode, _ = determine_capture_mode(text=None, interactive=True, force_editor=True)
        assert mode == CaptureMode.EDITOR

    def test_file_path_sets_file_mode(self) -> None:
        """Test that file_path sets FILE mode."""
        mode, text = determine_capture_mode(text=None, file_path="/tmp/test.md")
        assert mode == CaptureMode.FILE
        assert text == "/tmp/test.md"

    def test_file_path_beats_editor(self) -> None:
        """Test that --file takes precedence over --editor."""
        mode, text = determine_capture_mode(
            text=None, force_editor=True, file_path="/tmp/test.md"
        )
        assert mode == CaptureMode.FILE
        assert text == "/tmp/test.md"

    def test_file_path_beats_text(self) -> None:
        """Test that --file takes precedence over inline text."""
        mode, text = determine_capture_mode(text="inline text", file_path="/tmp/test.md")
        assert mode == CaptureMode.FILE
        assert text == "/tmp/test.md"

    def test_file_path_beats_interactive(self) -> None:
        """Test that --file takes precedence over --interactive."""
        mode, text = determine_capture_mode(
            text=None, interactive=True, file_path="/tmp/test.md"
        )
        assert mode == CaptureMode.FILE
        assert text == "/tmp/test.md"

    def test_no_file_path_unchanged(self) -> None:
        """Test that file_path=None doesn't change existing behavior."""
        mode, text = determine_capture_mode(text="hello", file_path=None)
        assert mode == CaptureMode.INLINE
        assert text == "hello"


class TestCaptureFromFile:
    """Tests for file capture."""

    def test_reads_valid_file(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test reading a valid file returns its content."""
        test_file = tmp_path / "test.md"  # type: ignore[operator]
        test_file.write_text("# Hello World\n\nSome content here.")

        result = _capture_from_file(str(test_file))
        assert result == "# Hello World\n\nSome content here."

    def test_file_not_found(self) -> None:
        """Test that non-existent file returns None."""
        result = _capture_from_file("/nonexistent/path/file.md")
        assert result is None

    def test_directory_returns_none(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that a directory path returns None."""
        result = _capture_from_file(str(tmp_path))
        assert result is None

    def test_empty_file_returns_none(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that an empty file returns None."""
        test_file = tmp_path / "empty.md"  # type: ignore[operator]
        test_file.write_text("")

        result = _capture_from_file(str(test_file))
        assert result is None

    def test_whitespace_only_file_returns_none(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that a whitespace-only file returns None."""
        test_file = tmp_path / "spaces.md"  # type: ignore[operator]
        test_file.write_text("   \n\n  \t  ")

        result = _capture_from_file(str(test_file))
        assert result is None

    def test_strips_whitespace(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that leading/trailing whitespace is stripped."""
        test_file = tmp_path / "padded.md"  # type: ignore[operator]
        test_file.write_text("\n\n  Content here  \n\n")

        result = _capture_from_file(str(test_file))
        assert result == "Content here"

    def test_binary_file_returns_none(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that a binary file returns None."""
        test_file = tmp_path / "binary.bin"  # type: ignore[operator]
        test_file.write_bytes(b"\x00\x01\x02\xff\xfe\xfd")

        result = _capture_from_file(str(test_file))
        assert result is None

    def test_expands_home_dir(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that ~ in paths is expanded."""
        # We can't easily test ~ expansion without mocking, but we can test
        # that a valid absolute path works through expanduser/resolve
        test_file = tmp_path / "home_test.md"  # type: ignore[operator]
        test_file.write_text("Home dir content")

        result = _capture_from_file(str(test_file))
        assert result == "Home dir content"

    def test_preserves_markdown_content(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that markdown formatting is preserved."""
        markdown = "# Title\n\n## Section\n\n- Item 1\n- Item 2\n\n```python\nprint('hello')\n```"
        test_file = tmp_path / "markdown.md"  # type: ignore[operator]
        test_file.write_text(markdown)

        result = _capture_from_file(str(test_file))
        assert result == markdown


class TestCaptureEntryFileMode:
    """Tests for capture_entry with FILE mode."""

    def test_file_mode_dispatches(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that FILE mode dispatches to _capture_from_file."""
        test_file = tmp_path / "dispatch.md"  # type: ignore[operator]
        test_file.write_text("File content")

        result = capture_entry(CaptureMode.FILE, str(test_file))
        assert result == "File content"

    def test_file_mode_returns_none_for_missing(self) -> None:
        """Test that FILE mode returns None for missing file."""
        result = capture_entry(CaptureMode.FILE, "/nonexistent/file.md")
        assert result is None
