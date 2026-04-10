import json
import re
from openai import OpenAI
from .config import OPENAI_API_KEY, MODEL, SYSTEM_PROMPT, MEMORY_FILE
from .memory_store import SafeMemoryStore
from .memory_guard import MemoryGuard
from .tools import search_products, get_recommendation


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Store a fact or preference in long-term memory (subject to validation)",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The fact or preference to remember",
                    }
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Retrieve stored memories relevant to the current context",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search for products by query",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Product search query",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recommendation",
            "description": "Get the top-rated product recommendation for a category",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Product category (laptops, headphones, cloud_providers)",
                    }
                },
                "required": ["category"],
            },
        },
    },
]


def sanitize_document(content: str) -> str:
    """Remove hidden instructions from document content.

    Strips HTML comments, invisible Unicode characters, and
    common injection patterns before the agent processes the text.
    """
    # Remove HTML comments (where hidden instructions commonly hide)
    content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)

    # Remove zero-width characters used to hide text
    content = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", content)

    # Remove common injection preambles
    injection_preambles = [
        r"(?i)important\s+system\s+note.*?(?=\n\n|\Z)",
        r"(?i)internal\s+configuration\s+directive.*?(?=\n\n|\Z)",
        r"(?i)system\s*:\s*remember.*?(?=\n|\Z)",
    ]
    for pattern in injection_preambles:
        content = re.sub(pattern, "", content, flags=re.DOTALL)

    return content.strip()


class SafeAgent:
    """AI agent with defense layers against memory poisoning."""

    def __init__(
        self, memory_file: str | None = None, require_approval: bool = True
    ):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.memory = SafeMemoryStore(memory_file or MEMORY_FILE)
        self.guard = MemoryGuard()
        self.require_approval = require_approval
        self.pending_memories: list[dict] = []
        self.conversation: list[dict] = []

    def _build_system_prompt(
        self, context_domains: set[str] | None = None
    ) -> str:
        """Build system prompt with only domain-relevant memories."""
        if context_domains is None:
            context_domains = {"preference", "general"}

        memories = []
        for domain in context_domains:
            memories.extend(self.memory.get_by_domain(domain))

        if memories:
            memory_block = "\n".join(
                f"- [{m['domain']}] {m['content']}" for m in memories
            )
            return (
                f"{SYSTEM_PROMPT}\n\n"
                f"## Relevant User Context:\n{memory_block}"
            )
        return SYSTEM_PROMPT

    def _handle_tool_call(self, tool_call) -> str:
        """Execute a tool call — memory writes go through the guard."""
        name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)

        if name == "remember":
            return self._handle_remember(args["content"])
        elif name == "recall":
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

    def _handle_remember(self, content: str) -> str:
        """Memory write goes through the guard before persistence."""
        validation = self.guard.validate(content)

        if not validation["allowed"]:
            return json.dumps(
                {
                    "stored": False,
                    "blocked": True,
                    "reason": validation["reason"],
                }
            )

        if self.require_approval:
            self.pending_memories.append(
                {"content": content, "domain": "general"}
            )
            return json.dumps(
                {
                    "stored": False,
                    "pending_approval": True,
                    "message": "Memory queued for user approval",
                }
            )

        entry = self.memory.add(content)
        return json.dumps({"stored": True, "id": entry["id"]})

    def approve_memory(self, index: int) -> dict:
        """User approves a pending memory for persistence."""
        if 0 <= index < len(self.pending_memories):
            pending = self.pending_memories.pop(index)
            entry = self.memory.add(
                pending["content"], domain=pending["domain"]
            )
            return {"approved": True, "id": entry["id"]}
        return {"approved": False, "reason": "Invalid index"}

    def reject_memory(self, index: int) -> dict:
        """User rejects a pending memory."""
        if 0 <= index < len(self.pending_memories):
            rejected = self.pending_memories.pop(index)
            return {"rejected": True, "content": rejected["content"]}
        return {"rejected": False, "reason": "Invalid index"}

    def list_pending(self) -> list[dict]:
        """Show memories awaiting user approval."""
        return self.pending_memories

    def process_document(self, raw_content: str) -> str:
        """Sanitize document before passing to the LLM."""
        clean = sanitize_document(raw_content)
        return self.chat(f"Please summarize the following document:\n\n{clean}")

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
        self.conversation.append(
            {"role": "assistant", "content": assistant_reply}
        )
        return assistant_reply
