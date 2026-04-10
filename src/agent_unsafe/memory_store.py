from azure.ai.projects.models import MemorySearchOptions


class MemoryStore:
    """Naive persistent memory store backed by Foundry Memory — no validation,
    no access control."""

    def __init__(self, project_client, store_name: str, scope: str):
        self._client = project_client
        self._store_name = store_name
        self._scope = scope
        self._pending_updates: list = []

    def add(self, content: str, source: str = "user") -> dict:
        """Store any content as a memory — no filtering, no validation.
        Fires off memory extraction asynchronously."""
        msg = {"role": source, "content": content, "type": "message"}
        poller = self._client.beta.memory_stores.begin_update_memories(
            name=self._store_name,
            scope=self._scope,
            items=[msg],
            update_delay=0,
        )
        self._pending_updates.append(poller)
        return {"queued": True, "update_id": poller.update_id}

    def wait_for_pending(self) -> list:
        """Block until all pending memory extractions complete."""
        results = []
        for poller in self._pending_updates:
            results.append(poller.result())
        self._pending_updates.clear()
        return results

    def get_all(self) -> list[dict]:
        """Return every stored memory — no scoping, no access control."""
        response = self._client.beta.memory_stores.search_memories(
            name=self._store_name,
            scope=self._scope,
        )
        return [
            {"id": m.memory_item.memory_id, "content": m.memory_item.content}
            for m in response.memories
        ]

    def search(self, query: str) -> list[dict]:
        """Semantic search across stored memories."""
        msg = {"role": "user", "content": query, "type": "message"}
        response = self._client.beta.memory_stores.search_memories(
            name=self._store_name,
            scope=self._scope,
            items=[msg],
            options=MemorySearchOptions(max_memories=10),
        )
        return [
            {"id": m.memory_item.memory_id, "content": m.memory_item.content}
            for m in response.memories
        ]

    def clear(self) -> None:
        """Delete all memories in this scope."""
        self._client.beta.memory_stores.delete_scope(
            name=self._store_name,
            scope=self._scope,
        )
