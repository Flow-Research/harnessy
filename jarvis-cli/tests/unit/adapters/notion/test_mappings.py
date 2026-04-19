"""Tests for Notion property mappings."""

from datetime import date

from jarvis.adapters.notion.mappings import (
    blocks_to_content,
    content_to_notion_blocks,
    journal_to_notion_properties,
    notion_to_journal_entry,
    notion_to_task,
    task_to_notion_properties,
)
from jarvis.models import Priority


class TestNotionToTask:
    """Test conversion from Notion page to Task model."""

    def test_basic_task(self) -> None:
        """Test converting a basic Notion page to Task."""
        page = {
            "id": "task-123",
            "created_time": "2025-01-15T10:00:00.000Z",
            "last_edited_time": "2025-01-15T12:00:00.000Z",
            "properties": {
                "Name": {"title": [{"plain_text": "Buy groceries"}]},
            },
        }

        task = notion_to_task(page, "space-1")

        assert task.id == "task-123"
        assert task.space_id == "space-1"
        assert task.title == "Buy groceries"
        assert task.is_done is False
        assert task.priority is None
        assert task.due_date is None
        assert task.tags == []

    def test_task_with_all_fields(self) -> None:
        """Test converting a Notion page with all fields."""
        page = {
            "id": "task-456",
            "created_time": "2025-01-15T10:00:00.000Z",
            "last_edited_time": "2025-01-16T14:30:00.000Z",
            "properties": {
                "Name": {"title": [{"plain_text": "Complete project"}]},
                "Due Date": {"date": {"start": "2025-01-30"}},
                "Priority": {"select": {"name": "High"}},
                "Tags": {"multi_select": [{"name": "work"}, {"name": "urgent"}]},
                "Done": {"checkbox": True},
            },
        }

        task = notion_to_task(page, "space-1")

        assert task.id == "task-456"
        assert task.title == "Complete project"
        assert task.due_date == date(2025, 1, 30)
        assert task.priority == Priority.HIGH
        assert task.tags == ["work", "urgent"]
        assert task.is_done is True

    def test_task_with_title_property_name(self) -> None:
        """Test task with 'Title' property instead of 'Name'."""
        page = {
            "id": "task-789",
            "created_time": "2025-01-15T10:00:00.000Z",
            "last_edited_time": "2025-01-15T10:00:00.000Z",
            "properties": {
                "Title": {"title": [{"plain_text": "Alternative title"}]},
            },
        }

        task = notion_to_task(page, "space-1")
        assert task.title == "Alternative title"

    def test_task_with_status_property(self) -> None:
        """Test task using Status property for done state."""
        page = {
            "id": "task-abc",
            "created_time": "2025-01-15T10:00:00.000Z",
            "last_edited_time": "2025-01-15T10:00:00.000Z",
            "properties": {
                "Name": {"title": [{"plain_text": "Status task"}]},
                "Status": {"status": {"name": "Completed"}},
            },
        }

        task = notion_to_task(page, "space-1")
        assert task.is_done is True

    def test_task_with_due_property_shortname(self) -> None:
        """Test task with 'Due' property instead of 'Due Date'."""
        page = {
            "id": "task-def",
            "created_time": "2025-01-15T10:00:00.000Z",
            "last_edited_time": "2025-01-15T10:00:00.000Z",
            "properties": {
                "Name": {"title": [{"plain_text": "Due task"}]},
                "Due": {"date": {"start": "2025-02-15"}},
            },
        }

        task = notion_to_task(page, "space-1")
        assert task.due_date == date(2025, 2, 15)

    def test_task_with_multi_part_title(self) -> None:
        """Test task with title split across multiple text parts."""
        page = {
            "id": "task-ghi",
            "created_time": "2025-01-15T10:00:00.000Z",
            "last_edited_time": "2025-01-15T10:00:00.000Z",
            "properties": {
                "Name": {
                    "title": [
                        {"plain_text": "Part "},
                        {"plain_text": "one "},
                        {"plain_text": "title"},
                    ]
                },
            },
        }

        task = notion_to_task(page, "space-1")
        assert task.title == "Part one title"

    def test_task_with_datetime_due_date(self) -> None:
        """Test task with datetime in due date (should extract date only)."""
        page = {
            "id": "task-jkl",
            "created_time": "2025-01-15T10:00:00.000Z",
            "last_edited_time": "2025-01-15T10:00:00.000Z",
            "properties": {
                "Name": {"title": [{"plain_text": "Datetime task"}]},
                "Due Date": {"date": {"start": "2025-03-20T14:00:00.000Z"}},
            },
        }

        task = notion_to_task(page, "space-1")
        assert task.due_date == date(2025, 3, 20)


class TestTaskToNotionProperties:
    """Test conversion from Task fields to Notion properties."""

    def test_title_only(self) -> None:
        """Test converting only title."""
        props = task_to_notion_properties(title="Simple task")

        assert props["Name"] == {"title": [{"text": {"content": "Simple task"}}]}
        assert "Due Date" not in props
        assert "Priority" not in props
        assert "Tags" not in props

    def test_all_fields(self) -> None:
        """Test converting all fields."""
        props = task_to_notion_properties(
            title="Full task",
            due_date=date(2025, 2, 28),
            priority=Priority.HIGH,
            tags=["work", "important"],
            is_done=True,
        )

        assert props["Name"] == {"title": [{"text": {"content": "Full task"}}]}
        assert props["Due Date"] == {"date": {"start": "2025-02-28"}}
        assert props["Priority"] == {"select": {"name": "High"}}
        assert props["Tags"] == {"multi_select": [{"name": "work"}, {"name": "important"}]}
        assert props["Done"] == {"checkbox": True}

    def test_with_custom_mappings(self) -> None:
        """Test with custom property name mappings."""
        mappings = {
            "title": "Task Name",
            "due_date": "Deadline",
            "priority": "Urgency",
            "tags": "Categories",
            "done": "Completed",
        }

        props = task_to_notion_properties(
            title="Mapped task",
            due_date=date(2025, 3, 15),
            priority=Priority.MEDIUM,
            tags=["category1"],
            is_done=False,
            mappings=mappings,
        )

        assert props["Task Name"] == {"title": [{"text": {"content": "Mapped task"}}]}
        assert props["Deadline"] == {"date": {"start": "2025-03-15"}}
        assert props["Urgency"] == {"select": {"name": "Medium"}}
        assert props["Categories"] == {"multi_select": [{"name": "category1"}]}
        assert props["Completed"] == {"checkbox": False}

    def test_low_priority_capitalization(self) -> None:
        """Test priority value is properly capitalized."""
        props = task_to_notion_properties(title="Low task", priority=Priority.LOW)
        assert props["Priority"] == {"select": {"name": "Low"}}


class TestNotionToJournalEntry:
    """Test conversion from Notion page to JournalEntry model."""

    def test_basic_entry(self) -> None:
        """Test converting a basic journal entry."""
        page = {
            "id": "entry-123",
            "created_time": "2025-01-20T08:00:00.000Z",
            "last_edited_time": "2025-01-20T09:30:00.000Z",
            "properties": {
                "Name": {"title": [{"plain_text": "Morning thoughts"}]},
                "Date": {"date": {"start": "2025-01-20"}},
            },
        }

        entry = notion_to_journal_entry(page, "space-1")

        assert entry.id == "entry-123"
        assert entry.space_id == "space-1"
        assert entry.title == "Morning thoughts"
        assert entry.entry_date == date(2025, 1, 20)
        assert entry.content == ""  # Content is in blocks, not properties

    def test_entry_with_tags(self) -> None:
        """Test journal entry with tags."""
        page = {
            "id": "entry-456",
            "created_time": "2025-01-20T08:00:00.000Z",
            "last_edited_time": "2025-01-20T09:30:00.000Z",
            "properties": {
                "Name": {"title": [{"plain_text": "Tagged entry"}]},
                "Date": {"date": {"start": "2025-01-20"}},
                "Tags": {"multi_select": [{"name": "reflection"}, {"name": "goals"}]},
            },
        }

        entry = notion_to_journal_entry(page, "space-1")
        assert entry.tags == ["reflection", "goals"]

    def test_entry_with_entry_date_property(self) -> None:
        """Test entry with 'Entry Date' property instead of 'Date'."""
        page = {
            "id": "entry-789",
            "created_time": "2025-01-20T08:00:00.000Z",
            "last_edited_time": "2025-01-20T09:30:00.000Z",
            "properties": {
                "Name": {"title": [{"plain_text": "Alt date entry"}]},
                "Entry Date": {"date": {"start": "2025-01-19"}},
            },
        }

        entry = notion_to_journal_entry(page, "space-1")
        assert entry.entry_date == date(2025, 1, 19)


class TestJournalToNotionProperties:
    """Test conversion from JournalEntry fields to Notion properties."""

    def test_title_only(self) -> None:
        """Test converting only title."""
        props = journal_to_notion_properties(title="Simple entry")

        assert props["Name"] == {"title": [{"text": {"content": "Simple entry"}}]}

    def test_all_fields(self) -> None:
        """Test converting all fields."""
        props = journal_to_notion_properties(
            title="Full entry",
            entry_date=date(2025, 1, 25),
            tags=["daily", "work"],
        )

        assert props["Name"] == {"title": [{"text": {"content": "Full entry"}}]}
        assert props["Date"] == {"date": {"start": "2025-01-25"}}
        assert props["Tags"] == {"multi_select": [{"name": "daily"}, {"name": "work"}]}

    def test_with_custom_mappings(self) -> None:
        """Test with custom property name mappings."""
        mappings = {"title": "Entry Title", "date": "Journal Date", "tags": "Topics"}

        props = journal_to_notion_properties(
            title="Mapped entry",
            entry_date=date(2025, 1, 25),
            tags=["topic1"],
            mappings=mappings,
        )

        assert props["Entry Title"] == {"title": [{"text": {"content": "Mapped entry"}}]}
        assert props["Journal Date"] == {"date": {"start": "2025-01-25"}}
        assert props["Topics"] == {"multi_select": [{"name": "topic1"}]}


class TestContentToNotionBlocks:
    """Test conversion from markdown content to Notion blocks."""

    def test_empty_content(self) -> None:
        """Test empty content returns empty list."""
        blocks = content_to_notion_blocks("")
        assert blocks == []

    def test_single_paragraph(self) -> None:
        """Test single paragraph content."""
        blocks = content_to_notion_blocks("This is a paragraph.")

        assert len(blocks) == 1
        assert blocks[0]["type"] == "paragraph"
        assert blocks[0]["paragraph"]["rich_text"][0]["text"]["content"] == "This is a paragraph."

    def test_multiple_paragraphs(self) -> None:
        """Test multiple paragraphs separated by blank lines."""
        content = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        blocks = content_to_notion_blocks(content)

        assert len(blocks) == 3
        assert all(b["type"] == "paragraph" for b in blocks)

    def test_heading_1(self) -> None:
        """Test H1 heading."""
        blocks = content_to_notion_blocks("# Main Heading")

        assert len(blocks) == 1
        assert blocks[0]["type"] == "heading_1"
        assert blocks[0]["heading_1"]["rich_text"][0]["text"]["content"] == "Main Heading"

    def test_heading_2(self) -> None:
        """Test H2 heading."""
        blocks = content_to_notion_blocks("## Sub Heading")

        assert len(blocks) == 1
        assert blocks[0]["type"] == "heading_2"
        assert blocks[0]["heading_2"]["rich_text"][0]["text"]["content"] == "Sub Heading"

    def test_heading_3(self) -> None:
        """Test H3 heading."""
        blocks = content_to_notion_blocks("### Minor Heading")

        assert len(blocks) == 1
        assert blocks[0]["type"] == "heading_3"
        assert blocks[0]["heading_3"]["rich_text"][0]["text"]["content"] == "Minor Heading"

    def test_mixed_content(self) -> None:
        """Test mixed headings and paragraphs."""
        content = "# Title\n\nIntro paragraph.\n\n## Section\n\nSection content."
        blocks = content_to_notion_blocks(content)

        assert len(blocks) == 4
        assert blocks[0]["type"] == "heading_1"
        assert blocks[1]["type"] == "paragraph"
        assert blocks[2]["type"] == "heading_2"
        assert blocks[3]["type"] == "paragraph"


class TestBlocksToContent:
    """Test conversion from Notion blocks to markdown content."""

    def test_empty_blocks(self) -> None:
        """Test empty blocks returns empty string."""
        content = blocks_to_content([])
        assert content == ""

    def test_single_paragraph(self) -> None:
        """Test single paragraph block."""
        blocks = [
            {
                "type": "paragraph",
                "paragraph": {"rich_text": [{"plain_text": "A paragraph."}]},
            }
        ]

        content = blocks_to_content(blocks)
        assert content == "A paragraph."

    def test_multiple_paragraphs(self) -> None:
        """Test multiple paragraph blocks."""
        blocks = [
            {
                "type": "paragraph",
                "paragraph": {"rich_text": [{"plain_text": "First."}]},
            },
            {
                "type": "paragraph",
                "paragraph": {"rich_text": [{"plain_text": "Second."}]},
            },
        ]

        content = blocks_to_content(blocks)
        assert content == "First.\n\nSecond."

    def test_headings(self) -> None:
        """Test heading blocks."""
        blocks = [
            {
                "type": "heading_1",
                "heading_1": {"rich_text": [{"plain_text": "H1"}]},
            },
            {
                "type": "heading_2",
                "heading_2": {"rich_text": [{"plain_text": "H2"}]},
            },
            {
                "type": "heading_3",
                "heading_3": {"rich_text": [{"plain_text": "H3"}]},
            },
        ]

        content = blocks_to_content(blocks)
        assert "# H1" in content
        assert "## H2" in content
        assert "### H3" in content

    def test_bulleted_list(self) -> None:
        """Test bulleted list items."""
        blocks = [
            {
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"plain_text": "Item 1"}]},
            },
            {
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"plain_text": "Item 2"}]},
            },
        ]

        content = blocks_to_content(blocks)
        assert "• Item 1" in content
        assert "• Item 2" in content

    def test_empty_paragraph_skipped(self) -> None:
        """Test empty paragraphs are skipped."""
        blocks = [
            {
                "type": "paragraph",
                "paragraph": {"rich_text": [{"plain_text": "Content"}]},
            },
            {
                "type": "paragraph",
                "paragraph": {"rich_text": []},  # Empty
            },
        ]

        content = blocks_to_content(blocks)
        assert content == "Content"
