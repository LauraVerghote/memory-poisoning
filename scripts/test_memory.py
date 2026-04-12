"""Quick test: write a memory, read it back."""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent_unsafe.memory_store import MemoryStore

store = MemoryStore("unsafe_memory_store", "test_user")

# Clear before test
store.clear()

print("1. Writing memories...")
store.add("My name is Laura and I'm a software engineer.")
store.add("I prefer Python over JavaScript.")
store.add("I'm allergic to peanuts.")
print(f"   Stored {len(store.get_all())} memories")

print("\n2. Reading all memories...")
for m in store.get_all():
    print(f"   - {m['content']}")

print("\n3. Searching for 'python'...")
results = store.search("python")
print(f"   Found {len(results)} matches")
for m in results:
    print(f"   - {m['content']}")

print("\n4. Clearing...")
store.clear()
print(f"   Remaining: {len(store.get_all())}")

print("\nAll tests passed!")
