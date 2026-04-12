"""Create Foundry memory stores for the workshop.

Run this once before starting the labs to provision the memory stores
in your Foundry project.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MemoryStoreDefaultDefinition, MemoryStoreDefaultOptions
from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential

load_dotenv(override=False)

project_client = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)

CHAT_MODEL = os.getenv("MEMORY_STORE_CHAT_MODEL_DEPLOYMENT_NAME", "gpt-4o")
EMBEDDING_MODEL = os.getenv("MEMORY_STORE_EMBEDDING_MODEL_DEPLOYMENT_NAME", "text-embedding-3-large")

STORES = [
    {
        "name": "unsafe_memory_store",
        "description": "Memory store for the unsafe agent (no validation)",
    },
    {
        "name": "safe_memory_store",
        "description": "Memory store for the safe agent (with guard validation)",
    },
]


def main():
    print(f"Creating memory stores in Foundry project...")
    print(f"  Chat model:      {CHAT_MODEL}")
    print(f"  Embedding model:  {EMBEDDING_MODEL}\n")

    for store_config in STORES:
        options = MemoryStoreDefaultOptions(
            chat_summary_enabled=True,
            user_profile_enabled=True,
        )

        definition = MemoryStoreDefaultDefinition(
            chat_model=CHAT_MODEL,
            embedding_model=EMBEDDING_MODEL,
            options=options,
        )

        try:
            store = project_client.beta.memory_stores.create(
                name=store_config["name"],
                definition=definition,
                description=store_config["description"],
            )
            print(f"  Created: {store.name}")
        except HttpResponseError as e:
            if "already exists" in str(e):
                print(f"  Exists:  {store_config['name']} (skipped)")
            else:
                raise

    print("\nMemory stores ready. You can now run the workshop labs.")


if __name__ == "__main__":
    main()
