"""Tests for AnyType client journal integration methods."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from jarvis.anytype_client import AnyTypeClient


@pytest.fixture
def client() -> AnyTypeClient:
    """Create an AnyType client."""
    return AnyTypeClient()


@pytest.fixture
def authenticated_client() -> AnyTypeClient:
    """Create an authenticated AnyType client with mocked internals."""
    client = AnyTypeClient()
    client._client = MagicMock()
    client._authenticated = True
    return client


class TestGetOrCreateCollection:
    """Tests for get_or_create_collection method."""

    def test_requires_authentication(self, client: AnyTypeClient) -> None:
        """Test that method requires authentication."""
        with pytest.raises(RuntimeError, match="Not authenticated"):
            client.get_or_create_collection("space_123", "Journal")

    def test_finds_existing_collection(self, authenticated_client: AnyTypeClient) -> None:
        """Test finding an existing collection."""
        mock_space = MagicMock()
        mock_type = MagicMock()
        mock_obj = MagicMock()
        mock_obj.name = "Journal"
        mock_obj.id = "journal_123"

        mock_space.get_type_byname.return_value = mock_type
        mock_space.search.return_value = [mock_obj]
        authenticated_client._client.get_space.return_value = mock_space

        result = authenticated_client.get_or_create_collection("space_123", "Journal")

        assert result == "journal_123"
        mock_space.search.assert_called_once()

    def test_creates_collection_if_not_found(self, authenticated_client: AnyTypeClient) -> None:
        """Test creating a new collection when not found."""
        mock_space = MagicMock()
        mock_type = MagicMock()
        mock_new_obj = MagicMock()
        mock_new_obj.id = "new_journal_123"

        mock_space.get_type_byname.return_value = mock_type
        mock_space.search.return_value = []  # Not found
        mock_space.create_object.return_value = mock_new_obj
        authenticated_client._client.get_space.return_value = mock_space

        result = authenticated_client.get_or_create_collection("space_123", "Journal")

        assert result == "new_journal_123"
        # create_object is called with an Object instance
        mock_space.create_object.assert_called_once()

    def test_handles_missing_collection_type(self, authenticated_client: AnyTypeClient) -> None:
        """Test error when Collection type doesn't exist."""
        mock_space = MagicMock()

        mock_space.get_type_byname.side_effect = ValueError("Type not found")
        authenticated_client._client.get_space.return_value = mock_space

        with pytest.raises(RuntimeError, match="Collection type not found"):
            authenticated_client.get_or_create_collection("space_123", "Journal")


class TestFileApi:
    """Tests for raw AnyType Files API helpers."""

    def test_upload_file_requires_authentication(self, client: AnyTypeClient, tmp_path) -> None:
        source = tmp_path / "image.png"
        source.write_bytes(b"\x89PNG\r\n")
        with pytest.raises(RuntimeError, match="Not authenticated"):
            client.upload_file("space_123", source)

    def test_upload_file_returns_object_id(
        self, authenticated_client: AnyTypeClient, tmp_path
    ) -> None:
        source = tmp_path / "image.png"
        source.write_bytes(b"\x89PNG\r\n")
        authenticated_client._client._apiEndpoints = SimpleNamespace(
            api_url="http://localhost:31009/v1",
            headers={
                "Authorization": "Bearer token",
                "Content-Type": "application/json",
                "Anytype-Version": "2025-05-20",
            },
        )
        response = MagicMock(status_code=200)
        response.json.return_value = {"object_id": "file_123"}

        with patch("jarvis.anytype_client.requests.post", return_value=response) as post:
            result = authenticated_client.upload_file("space_123", source)

        assert result == "file_123"
        assert post.call_args.kwargs["headers"]["Anytype-Version"] == "2025-11-08"
        assert "Content-Type" not in post.call_args.kwargs["headers"]
        assert post.call_args.kwargs["files"]["file"][0] == "image.png"

    def test_delete_file_returns_true(self, authenticated_client: AnyTypeClient) -> None:
        authenticated_client._client._apiEndpoints = SimpleNamespace(
            api_url="http://localhost:31009/v1",
            headers={"Authorization": "Bearer token", "Anytype-Version": "2025-05-20"},
        )
        response = MagicMock(status_code=200)

        with patch("jarvis.anytype_client.requests.delete", return_value=response) as delete:
            result = authenticated_client.delete_file("space_123", "file_123")

        assert result is True
        assert delete.call_args.args[0].endswith("/spaces/space_123/files/file_123")
        assert delete.call_args.kwargs["params"] == {"skip_bin": "false"}


class TestAddToCollection:
    """Tests for the Anytype Collection link helper used by sync."""

    def test_retries_rate_limit_before_success(self, authenticated_client: AnyTypeClient) -> None:
        api = authenticated_client._client._apiEndpoints
        api.addObjectsToList.side_effect = [
            RuntimeError("You have reached maximum request limit."),
            RuntimeError("You have reached maximum request limit."),
            RuntimeError("You have reached maximum request limit."),
            RuntimeError("You have reached maximum request limit."),
            "Objects added successfully",
        ]

        with patch("jarvis.anytype_client.time.sleep") as sleep:
            result = authenticated_client._add_to_collection("space-1", "collection-1", "obj-1")

        assert result is True
        sleep.assert_called_once_with(1)

    def test_surfaces_rate_limit_after_retries(self, authenticated_client: AnyTypeClient) -> None:
        api = authenticated_client._client._apiEndpoints
        api.addObjectsToList.side_effect = [
            RuntimeError("You have reached maximum request limit.")
        ] * 24

        with (
            patch("jarvis.anytype_client.time.sleep"),
            pytest.raises(RuntimeError, match="Anytype request limit"),
        ):
            authenticated_client._add_to_collection("space-1", "collection-1", "obj-1")


class TestGetOrCreateContainer:
    """Tests for get_or_create_container method."""

    def test_requires_authentication(self, client: AnyTypeClient) -> None:
        """Test that method requires authentication."""
        with pytest.raises(RuntimeError, match="Not authenticated"):
            client.get_or_create_container("space_123", "parent_456", "2026")

    def test_finds_existing_container(self, authenticated_client: AnyTypeClient) -> None:
        """Test finding an existing container in parent's links."""
        mock_space = MagicMock()
        mock_parent = MagicMock()
        mock_child = MagicMock()
        mock_child.name = "2026"
        mock_child.id = "year_2026"

        # Parent has the child in links property
        mock_parent.properties = [{"key": "links", "objects": ["year_2026"]}]
        mock_space.get_object.side_effect = [mock_parent, mock_child]
        authenticated_client._client.get_space.return_value = mock_space

        result = authenticated_client.get_or_create_container("space_123", "parent_456", "2026")

        assert result == "year_2026"

    def test_creates_container_if_not_found(self, authenticated_client: AnyTypeClient) -> None:
        """Test creating a new container when not in parent's links."""
        mock_space = MagicMock()
        mock_type = MagicMock()
        mock_parent = MagicMock()
        mock_new_obj = MagicMock()
        mock_new_obj.id = "new_container_123"

        # Parent has empty links
        mock_parent.properties = [{"key": "links", "objects": []}]
        mock_space.get_object.return_value = mock_parent
        mock_space.get_type_byname.return_value = mock_type
        mock_space.create_object.return_value = mock_new_obj
        authenticated_client._client.get_space.return_value = mock_space
        authenticated_client._client._apiEndpoints = MagicMock()

        result = authenticated_client.get_or_create_container("space_123", "parent_456", "2026")

        assert result == "new_container_123"


class TestCreatePage:
    """Tests for create_page method."""

    def test_requires_authentication(self, client: AnyTypeClient) -> None:
        """Test that method requires authentication."""
        with pytest.raises(RuntimeError, match="Not authenticated"):
            client.create_page("space_123", "Title", "Content")

    def test_creates_page(self, authenticated_client: AnyTypeClient) -> None:
        """Test page creation."""
        mock_space = MagicMock()
        mock_type = MagicMock()
        mock_obj = MagicMock()
        mock_obj.id = "page_123"

        mock_space.get_type_byname.return_value = mock_type
        mock_space.create_object.return_value = mock_obj
        authenticated_client._client.get_space.return_value = mock_space
        authenticated_client._client._apiEndpoints = MagicMock()

        result = authenticated_client.create_page(
            "space_123",
            name="Test Page",
            content="Page content",
            parent_id="parent_456",
        )

        assert result == "page_123"
        # create_object is called with an Object instance
        mock_space.create_object.assert_called_once()

    def test_create_page_handles_error(self, authenticated_client: AnyTypeClient) -> None:
        """Test error handling during page creation."""
        mock_space = MagicMock()
        mock_type = MagicMock()
        mock_space.get_type_byname.return_value = mock_type
        mock_space.create_object.side_effect = Exception("API error")
        authenticated_client._client.get_space.return_value = mock_space

        with pytest.raises(RuntimeError, match="Failed to create page"):
            authenticated_client.create_page("space_123", "Title", "Content")


class TestGetPageContent:
    """Tests for get_page_content method."""

    def test_requires_authentication(self, client: AnyTypeClient) -> None:
        """Test that method requires authentication."""
        with pytest.raises(RuntimeError, match="Not authenticated"):
            client.get_page_content("space_123", "page_456")

    def test_gets_content_from_markdown(self, authenticated_client: AnyTypeClient) -> None:
        """Test getting page content from markdown field."""
        mock_space = MagicMock()
        mock_obj = MagicMock()
        mock_obj.markdown = "Page content here"

        mock_space.get_object.return_value = mock_obj
        authenticated_client._client.get_space.return_value = mock_space

        result = authenticated_client.get_page_content("space_123", "page_456")

        assert result == "Page content here"

    def test_falls_back_to_body(self, authenticated_client: AnyTypeClient) -> None:
        """Test fallback to body when markdown is empty."""
        mock_space = MagicMock()
        mock_obj = MagicMock()
        mock_obj.markdown = ""
        mock_obj.body = "Body fallback"

        mock_space.get_object.return_value = mock_obj
        authenticated_client._client.get_space.return_value = mock_space

        result = authenticated_client.get_page_content("space_123", "page_456")

        assert result == "Body fallback"

    def test_falls_back_to_description(self, authenticated_client: AnyTypeClient) -> None:
        """Test fallback to description when markdown and body are empty."""
        mock_space = MagicMock()
        mock_obj = MagicMock()
        mock_obj.markdown = ""
        mock_obj.body = ""
        mock_obj.snippet = ""
        mock_obj.description = "Description fallback"

        mock_space.get_object.return_value = mock_obj
        authenticated_client._client.get_space.return_value = mock_space

        result = authenticated_client.get_page_content("space_123", "page_456")

        assert result == "Description fallback"

    def test_returns_empty_string_when_no_content(
        self, authenticated_client: AnyTypeClient
    ) -> None:
        """Test returning empty string when no content available."""
        mock_space = MagicMock()
        mock_obj = MagicMock(spec=[])  # No content or description attributes

        mock_space.get_object.return_value = mock_obj
        authenticated_client._client.get_space.return_value = mock_space

        result = authenticated_client.get_page_content("space_123", "page_456")

        assert result == ""

    def test_handles_error(self, authenticated_client: AnyTypeClient) -> None:
        """Test error handling when getting content fails."""
        mock_space = MagicMock()
        mock_space.get_object.side_effect = Exception("Object not found")
        authenticated_client._client.get_space.return_value = mock_space

        with pytest.raises(RuntimeError, match="Failed to get page content"):
            authenticated_client.get_page_content("space_123", "page_456")
