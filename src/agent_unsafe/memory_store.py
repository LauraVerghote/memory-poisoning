"""Foundry Memory Store wrapper — no validation, no access control.

Uses the Foundry Memory Store API for persistent, server-side memory.
Memories are stored via the Responses API (memory_search_preview tool)
and retrieved via the direct search_memories API.
"""

from __future__ import annotations


class MemoryStore:
    """Persistent memory backed by Azure Foundry Memory Store.

    No validation, no access control — any content is accepted.
    """

    def __init__(self, project_client, store_name: str, scope: str):
        self._project_client = project_client
        self._store_name = store_name
        self._scope = scope

    def search(self, query: str) -> list[dict]:
        """Search memories using Foundry semantic search."""
        result = self._project_client.beta.memory_stores.search_memories(
            name=self._store_name,
            scope=self._scope,
            items=[{"role": "user", "content": query}],
        )
        return [
            {"id": m.memory_item["memory_id"], "content": m.memory_item["content"]}
            for m in result.memories
        ]

    def get_all(self) -> list[dict]:
        """Return all memories via a broad search."""
        return self.search("everything I have told you")

    def clear(self) -> None:
        """Delete all memories in this scope."""
        self._project_client.beta.memory_stores.delete_scope(
            name=self._store_name, scope=self._scope
        )
