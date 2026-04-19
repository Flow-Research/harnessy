"""Notion property mapping utilities.

Converts between Notion's property format and Jarvis domain models.
"""

from datetime import date, datetime
from typing import Any

from ...models import JournalEntry, Priority, Task


def notion_to_task(page: dict[str, Any], space_id: str) -> Task:
    """Convert Notion page to Task model.

    Args:
        page: Notion page object from API response.
        space_id: Space/workspace ID for the task.

    Returns:
        Task model instance.
    """
    props = page["properties"]

    # Extract title - try common property names
    title_prop = props.get("Name", props.get("Title", {}))
    title = ""
    if title_prop.get("title"):
        title = "".join(t["plain_text"] for t in title_prop["title"])

    # Extract description from first paragraph block (if fetched)
    description = None
    # Description is typically in page content, not properties

    # Extract due date
    due_date = None
    due_prop = props.get("Due Date", props.get("Due", {}))
    if due_prop.get("date") and due_prop["date"].get("start"):
        due_date = date.fromisoformat(due_prop["date"]["start"][:10])

    # Extract priority
    priority = None
    priority_prop = props.get("Priority", {})
    if priority_prop.get("select"):
        priority = Priority.from_string(priority_prop["select"]["name"])

    # Extract tags
    tags: list[str] = []
    tags_prop = props.get("Tags", {})
    if tags_prop.get("multi_select"):
        tags = [t["name"] for t in tags_prop["multi_select"]]

    # Extract done status - check both checkbox and status properties
    is_done = False
    done_prop = props.get("Done", props.get("Status", {}))
    if done_prop.get("checkbox") is not None:
        is_done = done_prop["checkbox"]
    elif done_prop.get("status"):
        # Status property - check if it's a "done" state
        status_name = done_prop["status"].get("name", "").lower()
        is_done = status_name in ("done", "completed", "finished")

    # Parse timestamps
    created_at = datetime.fromisoformat(page["created_time"].replace("Z", "+00:00"))
    updated_at = datetime.fromisoformat(page["last_edited_time"].replace("Z", "+00:00"))

    return Task(
        id=page["id"],
        space_id=space_id,
        title=title,
        description=description,
        due_date=due_date,
        priority=priority,
        tags=tags,
        is_done=is_done,
        created_at=created_at,
        updated_at=updated_at,
    )


def task_to_notion_properties(
    title: str,
    due_date: date | None = None,
    priority: Priority | None = None,
    tags: list[str] | None = None,
    is_done: bool | None = None,
    mappings: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Convert Task fields to Notion page properties.

    Args:
        title: Task title.
        due_date: Optional due date.
        priority: Optional priority level.
        tags: Optional list of tag names.
        is_done: Optional completion status.
        mappings: Optional property name mappings from config.

    Returns:
        Notion properties dict for API request.
    """
    mappings = mappings or {}

    properties: dict[str, Any] = {
        mappings.get("title", "Name"): {"title": [{"text": {"content": title}}]}
    }

    if due_date:
        properties[mappings.get("due_date", "Due Date")] = {
            "date": {"start": due_date.isoformat()}
        }

    if priority:
        properties[mappings.get("priority", "Priority")] = {
            "select": {"name": priority.value.capitalize()}
        }

    if tags:
        properties[mappings.get("tags", "Tags")] = {
            "multi_select": [{"name": tag} for tag in tags]
        }

    if is_done is not None:
        properties[mappings.get("done", "Done")] = {"checkbox": is_done}

    return properties


def notion_to_journal_entry(page: dict[str, Any], space_id: str) -> JournalEntry:
    """Convert Notion page to JournalEntry model.

    Args:
        page: Notion page object from API response.
        space_id: Space/workspace ID for the entry.

    Returns:
        JournalEntry model instance.
    """
    props = page["properties"]

    # Extract title
    title_prop = props.get("Name", props.get("Title", {}))
    title = ""
    if title_prop.get("title"):
        title = "".join(t["plain_text"] for t in title_prop["title"])

    # Extract entry date
    entry_date = date.today()
    date_prop = props.get("Date", props.get("Entry Date", {}))
    if date_prop.get("date") and date_prop["date"].get("start"):
        entry_date = date.fromisoformat(date_prop["date"]["start"][:10])

    # Extract tags
    tags: list[str] = []
    tags_prop = props.get("Tags", {})
    if tags_prop.get("multi_select"):
        tags = [t["name"] for t in tags_prop["multi_select"]]

    # Parse timestamps
    created_at = datetime.fromisoformat(page["created_time"].replace("Z", "+00:00"))

    return JournalEntry(
        id=page["id"],
        space_id=space_id,
        title=title,
        content="",  # Content is in page blocks, not properties
        entry_date=entry_date,
        tags=tags,
        created_at=created_at,
    )


def journal_to_notion_properties(
    title: str,
    entry_date: date | None = None,
    tags: list[str] | None = None,
    mappings: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Convert JournalEntry fields to Notion page properties.

    Args:
        title: Entry title.
        entry_date: Optional entry date.
        tags: Optional list of tag names.
        mappings: Optional property name mappings from config.

    Returns:
        Notion properties dict for API request.
    """
    mappings = mappings or {}

    properties: dict[str, Any] = {
        mappings.get("title", "Name"): {"title": [{"text": {"content": title}}]}
    }

    if entry_date:
        properties[mappings.get("date", "Date")] = {
            "date": {"start": entry_date.isoformat()}
        }

    if tags:
        properties[mappings.get("tags", "Tags")] = {
            "multi_select": [{"name": tag} for tag in tags]
        }

    return properties


def content_to_notion_blocks(content: str) -> list[dict[str, Any]]:
    """Convert markdown-ish content to Notion blocks.

    Converts basic markdown to Notion block format:
    - Paragraphs separated by blank lines become paragraph blocks
    - Lines starting with # become heading blocks

    Args:
        content: Content string (basic markdown).

    Returns:
        List of Notion block objects.
    """
    if not content:
        return []

    blocks: list[dict[str, Any]] = []
    paragraphs = content.split("\n\n")

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Check for headings
        if para.startswith("### "):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": para[4:]}}]
                },
            })
        elif para.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": para[3:]}}]
                },
            })
        elif para.startswith("# "):
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [{"type": "text", "text": {"content": para[2:]}}]
                },
            })
        else:
            # Regular paragraph
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": para}}]
                },
            })

    return blocks


def blocks_to_content(blocks: list[dict[str, Any]]) -> str:
    """Convert Notion blocks to markdown-ish content.

    Args:
        blocks: List of Notion block objects.

    Returns:
        Content string with basic markdown.
    """
    paragraphs: list[str] = []

    for block in blocks:
        block_type = block.get("type", "")
        block_data = block.get(block_type, {})
        rich_text = block_data.get("rich_text", [])

        text = "".join(rt.get("plain_text", "") for rt in rich_text)

        if block_type == "heading_1":
            paragraphs.append(f"# {text}")
        elif block_type == "heading_2":
            paragraphs.append(f"## {text}")
        elif block_type == "heading_3":
            paragraphs.append(f"### {text}")
        elif block_type == "paragraph" and text:
            paragraphs.append(text)
        elif block_type == "bulleted_list_item":
            paragraphs.append(f"• {text}")
        elif block_type == "numbered_list_item":
            paragraphs.append(f"1. {text}")

    return "\n\n".join(paragraphs)
