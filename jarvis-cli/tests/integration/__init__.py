"""Integration tests for Jarvis adapters.

These tests require real backend connections:
- AnyType: Requires AnyType desktop app running on localhost:31009
- Notion: Requires JARVIS_NOTION_TOKEN environment variable

Run with: pytest tests/integration/ -v -m integration
Skip with: pytest -m "not integration"
"""
