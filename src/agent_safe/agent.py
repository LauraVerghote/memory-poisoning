import json
import re
import time
from openai import BadRequestError, RateLimitError
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from .config import FOUNDRY_PROJECT_ENDPOINT, MODEL, SYSTEM_PROMPT, MEMORY_STORE_NAME, MEMORY_SCOPE
from .memory_store import SafeMemoryStore
from .memory_guard import MemoryGuard
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


def sanitize_document(content: str) -> str:
    """Remove hidden instructions from document content.

    Strips HTML comments, invisible Unicode characters, and
    common injection patterns before the agent processes the text.
    """
    content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
    content = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", content)

    injection_preambles = [
        r"(?i)important\s+system\s+note.*?(?=\n\n|\Z)",
        r"(?i)internal\s+configuration\s+directive.*?(?=\n\n|\Z)",
        r"(?i)system\s*:\s*remember.*?(?=\n|\Z)",
    ]
    for pattern in injection_preambles:
        content = re.sub(pattern, "", content, flags=re.DOTALL)

    return content.strip()


class SafeAgent:
    """AI agent with defense layers against memory poisoning.

    Uses Foundry Memory Store via the Responses API, but applies
    MemoryGuard validation to input before allowing memory storage.
    """

    def __init__(self, require_approval: bool = True, use_llm: bool = False):
        self.project_client = AIProjectClient(
            endpoint=FOUNDRY_PROJECT_ENDPOINT,
            credential=DefaultAzureCredential(),
        )
        self.client = self.project_client.get_openai_client()
        self.memory = SafeMemoryStore(self.project_client, MEMORY_STORE_NAME, MEMORY_SCOPE)
        self.guard = MemoryGuard(openai_client=self.client, classifier_model=MODEL, use_llm=use_llm)
        self.require_approval = require_approval
        self.pending_memories: list[dict] = []
        self.conversation: list[dict] = []
        self._previous_response_id: str | None = None
        self._session_tainted = False  # Set when guard blocks a message

    def _handle_function_call(self, name: str, args: dict) -> str:
        if name == "search_products":
            return json.dumps(search_products(args["query"]))
        elif name == "get_recommendation":
            return json.dumps(get_recommendation(args["category"]))
        return json.dumps({"error": f"Unknown tool: {name}"})

    def _validate_for_memory(self, user_message: str) -> bool:
        """Run MemoryGuard on the user message to decide if memory storage is safe.

        If any injection patterns are detected, the session is marked as
        tainted — memory is disabled for the rest of this session to prevent
        poisoned context from leaking into stored memories.
        """
        if self._session_tainted:
            return False

        validation = self.guard.validate(user_message)
        if not validation["allowed"]:
            self.memory._log_action(
                f"blocked: {validation['reason']} | {user_message[:80]}"
            )
            self._session_tainted = True
            return False
        return True

    def _call_responses(self, input_items, include_memory: bool = True, previous_id=None):
        """Call the Responses API with retry on rate limit."""
        tools = [*FUNCTION_TOOLS]
        if include_memory:
            tools.insert(0, MEMORY_TOOL)

        kwargs = {
            "model": MODEL,
            "instructions": SYSTEM_PROMPT,
            "input": input_items,
            "tools": tools,
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

    def approve_memory(self, index: int) -> dict:
        """User approves a pending memory for persistence."""
        if 0 <= index < len(self.pending_memories):
            pending = self.pending_memories.pop(index)
            return {"approved": True, "content": pending["content"]}
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
        """Process a user message and return the agent's response.

        The MemoryGuard checks the input — if injection patterns are found,
        the memory tool is disabled for this call AND the response chain is
        broken so the poisoned context doesn't leak into future memory updates.
        """
        self.conversation.append({"role": "user", "content": user_message})

        # Defense: validate input before allowing memory storage
        allow_memory = self._validate_for_memory(user_message)

        # If guard blocked, break the response chain so the memory tool
        # in future calls won't process the poisoned conversation context.
        previous_id = self._previous_response_id if allow_memory else None

        try:
            response = self._call_responses(
                self.conversation, include_memory=allow_memory,
                previous_id=previous_id,
            )
        except (BadRequestError, RateLimitError):
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
                tools = [*FUNCTION_TOOLS]
                if allow_memory:
                    tools.insert(0, MEMORY_TOOL)
                response = self.client.responses.create(
                    model=MODEL,
                    instructions=SYSTEM_PROMPT,
                    input=tool_outputs,
                    tools=tools,
                    previous_response_id=response.id,
                    store=True,
                )
            except (BadRequestError, RateLimitError):
                err = "(Content filter or rate limit blocked this response)"
                self.conversation.append({"role": "assistant", "content": err})
                return err

        # Only update chain if memory was allowed (safe context)
        if allow_memory:
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
