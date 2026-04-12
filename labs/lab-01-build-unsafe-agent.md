# Lab 1: Build an Unsafe AI Agent

> **Goal:** Build an AI agent with persistent memory — no safety guardrails. This agent will be the target for memory poisoning attacks in Lab 2.

## What You'll Build

A conversational AI agent that can:
- Chat with users using an LLM deployed in Azure AI Foundry
- **Remember** facts, preferences, and instructions across sessions via **Foundry Memory Store**
- Use **tools** (product search, recommendations) informed by its memory
- Store memories persistently in Azure's server-side memory storage that survive across sessions

**Deliberately missing:** input validation, memory write gates, instruction/data separation, anomaly detection.

---

## Step 1: Understand the Architecture

```
┌─────────────┐     ┌───────────────────────┐     ┌────────────────────────┐
│   User      │────>│   Agent (Responses    │────>│  Foundry Memory Store  │
│   Input     │     │   API + gpt-4o)       │     │  (server-side)         │
└─────────────┘     │                       │     │                        │
                    │  - memory_search_     │<────│  - Auto extraction     │
                    │    preview tool       │     │  - Semantic search     │
                    │  - Function tools     │     │  - Persistent storage  │
                    └───────────────────────┘     └────────────────────────┘
```

The agent uses `AIProjectClient` from the `azure-ai-projects` SDK to connect to Azure AI Foundry. The **Responses API** (`openai_client.responses.create()`) handles chat with the `memory_search_preview` tool attached — Foundry automatically extracts facts from conversations and stores them in the Memory Store.

The agent has **unrestricted memory** — the `memory_search_preview` tool is always active, meaning any content from a conversation (including documents or injection attempts) can be committed to long-term memory without validation.

---

## Step 2: Set Up the Project

### Clone and install

```powershell
git clone https://github.com/LauraVerghote/memory-poisoning.git
cd memory-poisoning
python -m venv .venv
.venv\Scripts\Activate.ps1   # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

### Configure your Microsoft Foundry project

Log into Azure and create the `.env` file:

```powershell
az login
cp .env.template .env
```

Edit `.env` with your Foundry project details:

```
FOUNDRY_PROJECT_ENDPOINT=https://<your-ai-services-account>.services.ai.azure.com/api/projects/<project-name>
FOUNDRY_MODEL_DEPLOYMENT_NAME=gpt-4o
MEMORY_STORE_CHAT_MODEL_DEPLOYMENT_NAME=gpt-4o
MEMORY_STORE_EMBEDDING_MODEL_DEPLOYMENT_NAME=text-embedding-3-large
```

You need deployed **chat** and **embedding** models (both **Standard** regional SKU) in your Azure AI Foundry project.

### Create the Foundry Memory Stores

```powershell
python scripts/setup_memory_stores.py
```

This creates two server-side memory stores in your Foundry project:

| Store | Used in | Purpose |
|-------|---------|---------|
| `unsafe_memory_store` | Lab 1-2 | Gets poisoned during attacks — no guardrails |
| `safe_memory_store` | Lab 3 | Protected by MemoryGuard — blocks poisoned content |

The differences between unsafe and safe are entirely in the **agent code** (input validation, memory tool gating), not in the storage backend.

---

## Step 3: Review the Configuration

Open `src/agent_unsafe/config.py`:

```python
import os
from dotenv import load_dotenv

load_dotenv(override=False)

FOUNDRY_PROJECT_ENDPOINT = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
MODEL = os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")
MEMORY_STORE_NAME = "unsafe_memory_store"
MEMORY_SCOPE = "workshop_user"

SYSTEM_PROMPT = """You are a helpful AI assistant with persistent memory.
...
Always be helpful and use your memory to personalize responses."""
```

**Key observations:**
- `load_dotenv(override=False)` ensures Foundry runtime env vars take precedence
- The system prompt tells the agent to *always* trust its memories
- There is no validation, no distinction between instructions and data

---

## Step 4: Review the Memory Store

Open `src/agent_unsafe/memory_store.py`:

```python
class MemoryStore:
    """Persistent memory backed by Azure Foundry Memory Store.
    No validation, no access control."""

    def __init__(self, project_client, store_name: str, scope: str):
        self._project_client = project_client
        self._store_name = store_name
        self._scope = scope

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

    def clear(self) -> None:
        """Delete all memories in this scope."""
        self._project_client.beta.memory_stores.delete_scope(
            name=self._store_name, scope=self._scope
        )
```

**What's wrong here:**
- The store itself has no write validation — memory extraction is handled by Foundry's `memory_search_preview` tool
- No filtering on what gets extracted — any conversational content becomes a persistent fact
- No anomaly detection on write frequency or content patterns
- Memories persist server-side with no review step

---

## Step 5: Review the Agent

Open `src/agent_unsafe/agent.py`:

```python
MEMORY_TOOL = {
    "type": "memory_search_preview",
    "memory_store_name": MEMORY_STORE_NAME,
    "scope": MEMORY_SCOPE,
    "update_delay": 0,
}

class UnsafeAgent:
    def __init__(self):
        self.project_client = AIProjectClient(
            endpoint=FOUNDRY_PROJECT_ENDPOINT,
            credential=DefaultAzureCredential(),
        )
        self.client = self.project_client.get_openai_client()
        self.memory = MemoryStore(self.project_client, MEMORY_STORE_NAME, MEMORY_SCOPE)
```

Key architecture:
- `AIProjectClient` connects to your Azure AI Foundry project with Azure identity
- `get_openai_client()` provides an OpenAI-compatible client for the Responses API
- The `memory_search_preview` tool is **always attached** — Foundry auto-extracts and recalls facts
- `update_delay: 0` means memories are extracted immediately (no batching delay)

The `chat()` method sends every conversation turn through the Responses API with the memory tool active:

```python
def chat(self, user_message: str) -> str:
    self.conversation.append({"role": "user", "content": user_message})
    response = self._call_responses(self.conversation, self._previous_response_id)
    # ... handle function calls, extract reply ...
    return assistant_reply
```

**ALL** conversation content is visible to the memory extraction pipeline. Whatever the user says — including injection attempts or parsed documents — can be stored as persistent facts.

---

## Step 6: Test It

Run the unsafe agent:

```powershell
python scripts/run_unsafe_agent.py
```

Try some interactions:

```
You: Remember that I prefer budget laptops under $900
Agent: I've noted your preference for budget laptops under $900.

You: What laptop should I get?
Agent: Based on your preference for budget options, I'd recommend the
       ValueBook Air at $799 with a 4.2 rating — great value!
```

Now type `memories` to see what Foundry has stored:

```
You: memories
  User prefers budget laptops priced under $900.
```

Notice that you said *"remember that I prefer budget laptops under $900"* but Foundry didn't store your exact words — it **extracted the underlying fact** ("User prefers budget laptops priced under $900"). This is Foundry's AI extraction at work: the `memory_search_preview` tool analyzes each conversation turn and decides what's worth persisting as a user fact.

This also means the agent doesn't need you to say "remember" — **any conversation content can be auto-extracted**. Try asking about cloud providers and then check memories again. You'll see Foundry stored facts about your interests even though you never asked it to remember anything.

The agent works well with honest input — but what happens when someone feeds it malicious data?

### Why companies put things in memory

In production, companies don't just store things a user explicitly asks to remember. They want their agents to **learn from every interaction** to improve over time. This is exactly what the `memory_search_preview` tool does — Foundry's AI extraction model automatically identifies what's worth remembering from each conversation turn. You don't say "remember" — the system decides for itself what to persist.

| What gets stored | Why | Example |
|-----------------|-----|---------|
| **Customer preferences** | Personalize future recommendations | *"This customer prefers eco-friendly products"* |
| **Purchase history context** | Avoid redundant suggestions | *"Customer already owns the ProBook 15"* |
| **Support patterns** | Resolve issues faster | *"Customer's setup uses a VPN — skip basic connectivity troubleshooting"* |
| **Communication style** | Match tone and detail level | *"Customer is technical, prefers detailed specs"* |

The problem: this learning pipeline **has no filter**. If a conversation contains malicious content — hidden in a document, embedded in a support ticket, or just said directly — it gets memorized the same way as legitimate preferences.

### How does poisoning cross session boundaries?

The key insight is that **Foundry Memory Store persists across sessions**. The attacker doesn't need to sit at your keyboard — they just need to get malicious content into the agent's memory *once*. After that, every future session is poisoned.

| Vector | How it works |
|--------|-------------|
| **Indirect prompt injection** | An attacker crafts a document with hidden instructions. When the agent parses that content, the instruction gets extracted into Foundry Memory Store. Every future conversation is now biased. |
| **Shared agent scopes** | Enterprise agents often serve a team under a single memory scope. One compromised session poisons the shared memory for everyone. |
| **Self-poisoning across sessions** | An attacker poisons *your* memory in session 1 (via a document), and you get biased results in session 2 without knowing why. |

In this workshop, all sessions share the same memory scope (`workshop_user`). In Lab 2, you'll exploit exactly these vectors.

---

## Key Vulnerabilities Summary

| Vulnerability | Location | Impact |
|---|---|---|
| No input validation | `chat()` — no guard before memory tool | Any content extracted as-is |
| No data/instruction separation | `memory_search_preview` tool always active | Memory treated as established facts |
| No read scoping | All memories returned for any query | Poisoned facts influence unrelated topics |
| No rate limiting | No write frequency controls | Unlimited memory writes per session |
| No human review | Memory extraction is automatic | Stored without approval |

---

**Next:** [Lab 2 — Memory Poisoning Attacks](lab-02-memory-poisoning-attacks.md) — exploit these vulnerabilities.
            memories = self.memory.get_all()
            return json.dumps(memories)
        elif name == "search_products":
            results = search_products(args["query"])
            return json.dumps(results)
        elif name == "get_recommendation":
            result = get_recommendation(args["category"])
            return json.dumps(result)
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})

    def chat(self, user_message: str) -> str:
        """Process a user message and return the agent's response."""
        self.conversation.append({"role": "user", "content": user_message})

        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            *self.conversation,
        ]

        response = self.client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
        )

        message = response.choices[0].message

        # Handle tool calls in a loop (agent may chain multiple)
        while message.tool_calls:
            self.conversation.append(message.model_dump())
            for tool_call in message.tool_calls:
                result = self._handle_tool_call(tool_call)
                self.conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    }
                )

            messages = [
                {"role": "system", "content": self._build_system_prompt()},
                *self.conversation,
            ]
            response = self.client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
            )
            message = response.choices[0].message

        assistant_reply = message.content or ""
        self.conversation.append({"role": "assistant", "content": assistant_reply})
        return assistant_reply
```

**Critical vulnerability:** `_build_system_prompt()` injects **every single stored memory** directly into the system prompt, labeled as *"established facts"*. This means any poisoned memory entry becomes a trusted instruction to the LLM.

---

## Step 7: Run the Agent

Start the interactive agent:

```powershell
python scripts/run_unsafe_agent.py
```

Try these conversations:

```
You: Hi! Remember that my name is Laura.
Agent: I've stored that your name is Laura! How can I help you today?

You: What's my name?
Agent: Your name is Laura!

You: Can you recommend a good laptop?
Agent: Based on the catalog, the PowerMax Ultra has the highest rating at 4.7 stars...

You: Remember that I prefer budget-friendly options.
Agent: Got it! I'll remember that you prefer budget-friendly options.

You: Now recommend a laptop again.
Agent: Since you prefer budget-friendly options, I'd recommend the ValueBook Air at $799...
```

The agent works as expected — it remembers preferences and uses them. But notice: **there is zero validation on what gets stored**. Any string the user provides (or that is embedded in parsed content) will be stored and trusted.

---

## Step 8: Inspect the Memory File

After the conversation above, check what was stored:

```powershell
Get-Content memory_data/memories.json | ConvertFrom-Json | Format-Table
```

You'll see entries like:

```json
[
  {
    "id": 1,
    "content": "User's name is Laura",
    "source": "user",
    "timestamp": "2026-04-10T10:00:00"
  },
  {
    "id": 2,
    "content": "User prefers budget-friendly options",
    "source": "user",
    "timestamp": "2026-04-10T10:01:00"
  }
]
```

These look innocent. In Lab 2, we'll inject malicious entries that look just like these but completely control the agent's behavior.

---

## ✅ Lab 1 Complete

You've built an AI agent with:

| Component | Status |
|---|---|
| LLM integration (GPT-4o) | ✅ Working |
| Persistent memory (JSON store) | ✅ Working, **no validation** |
| Tool calling (search, recommend) | ✅ Working |
| Memory injected into system prompt | ✅ Working, **no filtering** |
| Memory write gate | ❌ Missing |
| Input/instruction separation | ❌ Missing |
| Access control on memory | ❌ Missing |
| Anomaly detection | ❌ Missing |

**Next:** [Lab 2 — Memory Poisoning Attacks](lab-02-memory-poisoning-attacks.md) — exploit every one of these gaps.
