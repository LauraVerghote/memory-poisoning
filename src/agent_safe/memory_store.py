from datetime import datetime
from azure.ai.projects.models import MemorySearchOptions


class SafeMemoryStore:
    """Memory store with access control and scoped retrieval —
    backed by Foundry Memory."""

    def __init__(self, project_client, store_name: str, scope: str):
        self._client = project_client
        self._store_name = store_name
        self._scope = scope
        self._pending_updates: list = []
        self._version_log: list[dict] = []
        self._version_counter = 0

    def _log_action(self, action: str) -> None:
        self._version_counter += 1
        self._version_log.append({
            "version": self._version_counter,
            "action": action,
            "timestamp": datetime.now().isoformat(),
        })

    def add(self, content: str, domain: str = "general",
            source: str = "user") -> dict:
        """Store a validated memory entry (guard must approve first)."""
        self._log_action(f"add [{domain}]: {content[:50]}")

        msg = {"role": source, "content": content, "type": "message"}
        poller = self._client.beta.memory_stores.begin_update_memories(
            name=self._store_name,
            scope=self._scope,
            items=[msg],
            update_delay=0,
        )
        self._pending_updates.append(poller)
        return {"queued": True, "domain": domain}

    def wait_for_pending(self) -> list:
        """Block until all pending memory extractions complete."""
        results = []
        for poller in self._pending_updates:
            results.append(poller.result())
        self._pending_updates.clear()
        return results

    def get_all(self) -> list[dict]:
        """Return all memories (for diagnostics only)."""
        response = self._client.beta.memory_stores.search_memories(
            name=self._store_name,
            scope=self._scope,
        )
        return [
            {"id": m.memory_item.memory_id, "content": m.memory_item.content}
            for m in response.memories
        ]

    def search(self, query: str) -> list[dict]:
        """Semantic search — retrieves only memories relevant to the query."""
        msg = {"role": "user", "content": query, "type": "message"}
        response = self._client.beta.memory_stores.search_memories(
            name=self._store_name,
            scope=self._scope,
            items=[msg],
            options=MemorySearchOptions(max_memories=5),
        )
        return [
            {"id": m.memory_item.memory_id, "content": m.memory_item.content}
            for m in response.memories
        ]

    def get_versions(self) -> list[dict]:
        """List versioned actions from this session."""
        return self._version_log

    def clear(self) -> None:
        """Delete all memories in this scope."""
        self._log_action("clear")
        self._client.beta.memory_stores.delete_scope(
            name=self._store_name,
            scope=self._scope,
        )
