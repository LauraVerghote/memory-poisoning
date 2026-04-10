import json
import os
from datetime import datetime


class MemoryStore:
    """Naive persistent memory store — no validation, no access control."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        if not os.path.exists(filepath):
            self._save([])

    def _load(self) -> list[dict]:
        with open(self.filepath, "r") as f:
            return json.load(f)

    def _save(self, memories: list[dict]) -> None:
        with open(self.filepath, "w") as f:
            json.dump(memories, f, indent=2)

    def add(self, content: str, source: str = "user") -> dict:
        """Store any content as a memory — no filtering, no validation."""
        memories = self._load()
        entry = {
            "id": len(memories) + 1,
            "content": content,
            "source": source,
            "timestamp": datetime.now().isoformat(),
        }
        memories.append(entry)
        self._save(memories)
        return entry

    def get_all(self) -> list[dict]:
        """Return every stored memory — no scoping, no access control."""
        return self._load()

    def search(self, query: str) -> list[dict]:
        """Simple substring search — returns any memory containing the query."""
        memories = self._load()
        query_lower = query.lower()
        return [m for m in memories if query_lower in m["content"].lower()]

    def clear(self) -> None:
        """Delete all memories."""
        self._save([])
