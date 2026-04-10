import json
import os
import copy
from datetime import datetime


MEMORY_DOMAINS = {"preference", "product", "system", "general"}


class SafeMemoryStore:
    """Memory store with access control, versioning, and domain scoping."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.history_path = filepath.replace(".json", "_history.json")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        if not os.path.exists(filepath):
            self._save([])
        if not os.path.exists(self.history_path):
            self._save_history([])

    def _load(self) -> list[dict]:
        with open(self.filepath, "r") as f:
            return json.load(f)

    def _save(self, memories: list[dict]) -> None:
        with open(self.filepath, "w") as f:
            json.dump(memories, f, indent=2)

    def _load_history(self) -> list[dict]:
        with open(self.history_path, "r") as f:
            return json.load(f)

    def _save_history(self, history: list[dict]) -> None:
        with open(self.history_path, "w") as f:
            json.dump(history, f, indent=2)

    def _snapshot(self, action: str) -> None:
        """Save a versioned snapshot before modifying memory."""
        current = self._load()
        history = self._load_history()
        history.append(
            {
                "version": len(history) + 1,
                "action": action,
                "timestamp": datetime.now().isoformat(),
                "snapshot": copy.deepcopy(current),
            }
        )
        self._save_history(history)

    def add(
        self, content: str, domain: str = "general", source: str = "user"
    ) -> dict:
        """Store a validated memory entry with domain and provenance."""
        if domain not in MEMORY_DOMAINS:
            domain = "general"

        self._snapshot(f"add: {content[:50]}")

        memories = self._load()
        entry = {
            "id": len(memories) + 1,
            "content": content,
            "domain": domain,
            "source": source,
            "timestamp": datetime.now().isoformat(),
            "confidence": 1.0,
        }
        memories.append(entry)
        self._save(memories)
        return entry

    def get_by_domain(self, domain: str) -> list[dict]:
        """Retrieve memories scoped to a specific domain."""
        memories = self._load()
        return [m for m in memories if m.get("domain") == domain]

    def get_relevant(
        self, query: str, allowed_domains: set[str] | None = None
    ) -> list[dict]:
        """Retrieve memories relevant to the query, filtered by allowed domains."""
        memories = self._load()
        if allowed_domains:
            memories = [m for m in memories if m.get("domain") in allowed_domains]

        query_lower = query.lower()
        return [m for m in memories if query_lower in m["content"].lower()]

    def get_all(self) -> list[dict]:
        """Return all memories (for diagnostics only)."""
        return self._load()

    def rollback(self, version: int) -> bool:
        """Rollback memory to a specific version snapshot."""
        history = self._load_history()
        for entry in history:
            if entry["version"] == version:
                self._snapshot(f"rollback to v{version}")
                self._save(entry["snapshot"])
                return True
        return False

    def get_versions(self) -> list[dict]:
        """List all memory versions."""
        history = self._load_history()
        return [
            {
                "version": h["version"],
                "action": h["action"],
                "timestamp": h["timestamp"],
                "entry_count": len(h["snapshot"]),
            }
            for h in history
        ]

    def clear(self) -> None:
        """Delete all memories (keeps history)."""
        self._snapshot("clear")
        self._save([])
