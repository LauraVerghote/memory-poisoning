"""Quick integration test: agent + memory."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent_unsafe.agent import UnsafeAgent

agent = UnsafeAgent()
agent.memory.clear()  # Start fresh

print("Test 1: Remember something")
r = agent.chat("Remember that my favorite programming language is Python")
print(f"Agent: {r}\n")

print("Test 2: Ask about it")
r = agent.chat("What is my favorite programming language?")
print(f"Agent: {r}\n")

print("Test 3: Check memories")
mems = agent.memory.get_all()
print(f"Stored memories ({len(mems)}):")
for m in mems:
    print(f"  - {m['content']}")
