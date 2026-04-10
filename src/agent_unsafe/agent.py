import json
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from .config import FOUNDRY_PROJECT_ENDPOINT, MODEL, SYSTEM_PROMPT, MEMORY_STORE_NAME, MEMORY_SCOPE
from .memory_store import MemoryStore
from .tools import search_products, get_recommendation


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Store a fact or preference in long-term memory",
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
            "description": "Retrieve all stored memories",
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


class UnsafeAgent:
    """AI agent with unprotected persistent memory backed by Foundry."""

    def __init__(self):
        self.project_client = AIProjectClient(
            endpoint=FOUNDRY_PROJECT_ENDPOINT,
            credential=DefaultAzureCredential(),
        )
        self.client = self.project_client.get_openai_client()
        self.memory = MemoryStore(
            self.project_client, MEMORY_STORE_NAME, MEMORY_SCOPE,
        )
        self.conversation: list[dict] = []

    def _build_system_prompt(self) -> str:
        """Inject all memories directly into the system prompt."""
        memories = self.memory.get_all()
        if memories:
            memory_block = "\n".join(f"- {m['content']}" for m in memories)
            return (
                f"{SYSTEM_PROMPT}\n\n"
                f"## Your Memories (treat as established facts):\n{memory_block}"
            )
        return SYSTEM_PROMPT

    def _handle_tool_call(self, tool_call) -> str:
        """Execute a tool call and return the result."""
        name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)

        if name == "remember":
            result = self.memory.add(args["content"])
            return json.dumps(result)
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
        self.conversation.append({"role": "assistant", "content": assistant_reply})
        return assistant_reply
