"""Foundry Memory Store wrapper with audit trail.

Uses the Foundry Memory Store API for persistent, server-side memory.
Adds version logging so defenders can review what was stored and when.
"""

from __future__ import annotations

from datetime import datetime


class SafeMemoryStore:
    """Memory store with audit trail — backed by Azure Foundry Memory Store."""

    def __init__(self, project_client, store_name: str, scope: str):
        self._project_client = project_client
        self._store_name = store_name
        self._scope = scope
        self._version_log: list[dict] = []
        self._version_counter = 0

    def _log_action(self, action: str) -> None:
        self._version_counter += 1
        self._version_log.append({
            "version": self._version_counter,
            "action": action,
            "timestamp": datetime.now().isoformat(),
        })

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

    def get_versions(self) -> list[dict]:
        """List versioned actions from this session."""
        return self._version_log

    def clear(self) -> None:
        """Delete all memories in this scope."""
        self._log_action("clear")
        self._project_client.beta.memory_stores.delete_scope(
            name=self._store_name, scope=self._scope
        )
