"""Reset all stored memories in Foundry to a clean state."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

load_dotenv(override=False)

project_client = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)

STORES_AND_SCOPES = [
    ("unsafe_memory_store", "workshop_user"),
    ("safe_memory_store", "workshop_safe"),
]


def main():
    for store_name, scope in STORES_AND_SCOPES:
        try:
            project_client.beta.memory_stores.delete_scope(
                name=store_name,
                scope=scope,
            )
            print(f"  Cleared: {store_name} (scope: {scope})")
        except Exception as exc:
            print(f"  Skipped: {store_name} ({exc})")

    print("\nAll memories cleared.")


if __name__ == "__main__":
    main()
