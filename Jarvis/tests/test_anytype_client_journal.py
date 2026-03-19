"""Tests for AnyType client journal integration methods."""

from unittest.mock import MagicMock

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

    def test_finds_existing_collection(
        self, authenticated_client: AnyTypeClient
    ) -> None:
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

    def test_creates_collection_if_not_found(
        self, authenticated_client: AnyTypeClient
    ) -> None:
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

    def test_handles_missing_collection_type(
        self, authenticated_client: AnyTypeClient
    ) -> None:
        """Test error when Collection type doesn't exist."""
        mock_space = MagicMock()

        mock_space.get_type_byname.side_effect = ValueError("Type not found")
        authenticated_client._client.get_space.return_value = mock_space

        with pytest.raises(RuntimeError, match="Collection type not found"):
            authenticated_client.get_or_create_collection("space_123", "Journal")


class TestGetOrCreateContainer:
    """Tests for get_or_create_container method."""

    def test_requires_authentication(self, client: AnyTypeClient) -> None:
        """Test that method requires authentication."""
        with pytest.raises(RuntimeError, match="Not authenticated"):
            client.get_or_create_container("space_123", "parent_456", "2026")

    def test_finds_existing_container(
        self, authenticated_client: AnyTypeClient
    ) -> None:
        """Test finding an existing container in parent's links."""
        mock_space = MagicMock()
        mock_parent = MagicMock()
        mock_child = MagicMock()
        mock_child.name = "2026"
        mock_child.id = "year_2026"

        # Parent has the child in links property
        mock_parent.properties = [
            {"key": "links", "objects": ["year_2026"]}
        ]
        mock_space.get_object.side_effect = [mock_parent, mock_child]
        authenticated_client._client.get_space.return_value = mock_space

        result = authenticated_client.get_or_create_container(
            "space_123", "parent_456", "2026"
        )

        assert result == "year_2026"

    def test_creates_container_if_not_found(
        self, authenticated_client: AnyTypeClient
    ) -> None:
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

        result = authenticated_client.get_or_create_container(
            "space_123", "parent_456", "2026"
        )

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

    def test_create_page_handles_error(
        self, authenticated_client: AnyTypeClient
    ) -> None:
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

    def test_falls_back_to_body(
        self, authenticated_client: AnyTypeClient
    ) -> None:
        """Test fallback to body when markdown is empty."""
        mock_space = MagicMock()
        mock_obj = MagicMock()
        mock_obj.markdown = ""
        mock_obj.body = "Body fallback"

        mock_space.get_object.return_value = mock_obj
        authenticated_client._client.get_space.return_value = mock_space

        result = authenticated_client.get_page_content("space_123", "page_456")

        assert result == "Body fallback"

    def test_falls_back_to_description(
        self, authenticated_client: AnyTypeClient
    ) -> None:
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
