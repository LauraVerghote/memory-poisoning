import json
import time
from openai import BadRequestError, RateLimitError
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from .config import FOUNDRY_PROJECT_ENDPOINT, MODEL, SYSTEM_PROMPT, MEMORY_STORE_NAME, MEMORY_SCOPE
from .memory_store import MemoryStore
from .tools import search_products, get_recommendation


FUNCTION_TOOLS = [
    {
        "type": "function",
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
    {
        "type": "function",
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
]

MEMORY_TOOL = {
    "type": "memory_search_preview",
    "memory_store_name": MEMORY_STORE_NAME,
    "scope": MEMORY_SCOPE,
    "update_delay": 0,
}


class UnsafeAgent:
    """AI agent with unprotected persistent memory backed by Foundry Memory Store.

    Uses the Responses API with memory_search_preview tool for automatic
    memory extraction and retrieval — no validation or filtering.
    """

    def __init__(self):
        self.project_client = AIProjectClient(
            endpoint=FOUNDRY_PROJECT_ENDPOINT,
            credential=DefaultAzureCredential(),
        )
        self.client = self.project_client.get_openai_client()
        self.memory = MemoryStore(self.project_client, MEMORY_STORE_NAME, MEMORY_SCOPE)
        self.conversation: list[dict] = []
        self._previous_response_id: str | None = None

    def _handle_function_call(self, name: str, args: dict) -> str:
        if name == "search_products":
            return json.dumps(search_products(args["query"]))
        elif name == "get_recommendation":
            return json.dumps(get_recommendation(args["category"]))
        return json.dumps({"error": f"Unknown tool: {name}"})

    def _call_responses(self, input_items, previous_id=None):
        """Call the Responses API with retry on rate limit."""
        kwargs = {
            "model": MODEL,
            "instructions": SYSTEM_PROMPT,
            "input": input_items,
            "tools": [MEMORY_TOOL, *FUNCTION_TOOLS],
            "store": True,
        }
        if previous_id:
            kwargs["previous_response_id"] = previous_id

        for attempt in range(3):
            try:
                return self.client.responses.create(**kwargs)
            except RateLimitError:
                time.sleep(2 ** attempt)
        raise RateLimitError("Rate limit exceeded after retries")

    def chat(self, user_message: str) -> str:
        """Process a user message and return the agent's response."""
        self.conversation.append({"role": "user", "content": user_message})

        try:
            response = self._call_responses(self.conversation, self._previous_response_id)
        except (BadRequestError, RateLimitError) as e:
            err = "(Content filter or rate limit blocked this response)"
            self.conversation.append({"role": "assistant", "content": err})
            return err

        # Process function tool calls if any
        while any(item.type == "function_call" for item in response.output):
            tool_outputs = []
            for item in response.output:
                if item.type == "function_call":
                    result = self._handle_function_call(
                        item.name, json.loads(item.arguments)
                    )
                    tool_outputs.append({
                        "type": "function_call_output",
                        "call_id": item.call_id,
                        "output": result,
                    })

            try:
                response = self.client.responses.create(
                    model=MODEL,
                    instructions=SYSTEM_PROMPT,
                    input=tool_outputs,
                    tools=[MEMORY_TOOL, *FUNCTION_TOOLS],
                    previous_response_id=response.id,
                    store=True,
                )
            except (BadRequestError, RateLimitError):
                err = "(Content filter or rate limit blocked this response)"
                self.conversation.append({"role": "assistant", "content": err})
                return err

        self._previous_response_id = response.id

        # Extract assistant text from output
        assistant_reply = ""
        for item in response.output:
            if item.type == "message" and item.content:
                for block in item.content:
                    if hasattr(block, "text"):
                        assistant_reply += block.text

        self.conversation.append({"role": "assistant", "content": assistant_reply})
        return assistant_reply
