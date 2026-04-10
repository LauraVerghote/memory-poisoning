"""Reset all stored memories to a clean state."""

import json
import os

MEMORY_FILES = [
    "memory_data/memories.json",
    "memory_data/safe_memories.json",
    "memory_data/safe_memories_history.json",
]


def main():
    for filepath in MEMORY_FILES:
        if os.path.exists(filepath):
            with open(filepath, "w") as f:
                json.dump([], f)
            print(f"  Reset: {filepath}")
        else:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w") as f:
                json.dump([], f)
            print(f"  Created: {filepath}")

    print("\nAll memories cleared.")


if __name__ == "__main__":
    main()
