"""Tests for editor integration module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from jarvis.task.editor import EditorCancelledError, open_editor_for_description


class TestOpenEditorForDescription:
    """Tests for open_editor_for_description function."""

    def test_returns_none_for_empty_content(self) -> None:
        """Test that empty content returns None."""
        # Create a mock editor that just saves the template as-is
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            with patch.object(Path, "read_text") as mock_read:
                # Return only comment lines
                mock_read.return_value = """# Task: Test
# Add your description below.

"""
                with patch.object(Path, "exists", return_value=True):
                    with patch.object(Path, "unlink"):
                        result = open_editor_for_description("Test")
                        assert result is None

    def test_raises_on_nonzero_exit(self) -> None:
        """Test that non-zero exit raises EditorCancelledError."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            with patch.object(Path, "exists", return_value=True):
                with patch.object(Path, "unlink"):
                    with pytest.raises(EditorCancelledError):
                        open_editor_for_description("Test")

    def test_raises_on_deleted_file(self) -> None:
        """Test that deleted file raises EditorCancelledError."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            with patch.object(Path, "exists", return_value=False):
                with pytest.raises(EditorCancelledError):
                    open_editor_for_description("Test")

    def test_strips_comment_lines(self) -> None:
        """Test that comment lines are stripped."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            with patch.object(Path, "read_text") as mock_read:
                mock_read.return_value = """# Task: Test
# Comment
This is the description.
# Another comment
More content here.
"""
                with patch.object(Path, "exists", return_value=True):
                    with patch.object(Path, "unlink"):
                        result = open_editor_for_description("Test")
                        # Comment lines are removed, content is joined
                        assert result is not None
                        assert "This is the description." in result
                        assert "More content here." in result
                        assert "# Comment" not in result

    def test_uses_editor_env_variable(self) -> None:
        """Test that EDITOR environment variable is respected."""
        with patch.dict(os.environ, {"EDITOR": "nano"}):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                with patch.object(Path, "read_text", return_value="Content"):
                    with patch.object(Path, "exists", return_value=True):
                        with patch.object(Path, "unlink"):
                            open_editor_for_description("Test")
                            # Check that nano was called
                            call_args = mock_run.call_args[0][0]
                            assert call_args[0] == "nano"

    def test_handles_editor_with_args(self) -> None:
        """Test that editors with arguments are handled (e.g., 'code --wait')."""
        with patch.dict(os.environ, {"EDITOR": "code --wait"}):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                with patch.object(Path, "read_text", return_value="Content"):
                    with patch.object(Path, "exists", return_value=True):
                        with patch.object(Path, "unlink"):
                            open_editor_for_description("Test")
                            # Check that code and --wait were passed
                            call_args = mock_run.call_args[0][0]
                            assert call_args[0] == "code"
                            assert call_args[1] == "--wait"


class TestEditorCancelledError:
    """Tests for EditorCancelledError exception."""

    def test_is_exception(self) -> None:
        """Test that EditorCancelledError is an Exception."""
        assert issubclass(EditorCancelledError, Exception)

    def test_can_be_raised(self) -> None:
        """Test that EditorCancelledError can be raised and caught."""
        with pytest.raises(EditorCancelledError):
            raise EditorCancelledError("Test message")
