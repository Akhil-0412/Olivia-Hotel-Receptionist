"""
agent_brain.py
==============
NexCell AI – LangGraph Orchestration Layer (Chunk 1)
====================================================
Architecture overview
---------------------
                        ┌─────────────────────────────┐
  User terminal input   │   agent_brain.py            │
  ─────────────────────▶│                             │
                        │  LangGraph ReAct Agent      │
                        │  (create_react_agent)       │
                        │         │                   │
                        │         │ tool calls        │
                        │         ▼                   │
                        │  MultiServerMCPClient       │
                        │  (langchain-mcp-adapters)   │
                        └──────────┬──────────────────┘
                                   │ SSE transport
                                   │ GET  /sse
                                   │ POST /messages/
                                   ▼
                        ┌─────────────────────────────┐
                        │   mcp_server.py             │
                        │   FastMCP  :8000            │
                        │   • check_availability      │
                        │   • create_booking          │
                        │   • search_faq              │
                        └─────────────────────────────┘

How the MCP → LangChain adapter bridge works
--------------------------------------------
1. `MultiServerMCPClient` opens a persistent SSE connection to the FastMCP
   server's event stream (`GET /sse`).  The server sends a "tools/list" event
   containing JSON schema descriptors for every registered tool.

2. `await client.get_tools()` translates those MCP tool descriptors into
   standard `langchain_core.tools.StructuredTool` objects.  Each tool wraps
   an async callable that, when invoked by the agent, POSTs a JSON-RPC
   "tools/call" request to `POST /messages/` and awaits the SSE response.

3. `create_react_agent(llm, tools)` compiles a LangGraph StateGraph with two
   nodes: "agent" (LLM reasoning step) and "tools" (ToolNode).  The graph
   loops: agent decides → tools execute → agent reflects → … until the agent
   produces a final answer with no pending tool calls.

4. `handle_tool_errors=True` ensures that any exception raised inside an MCP
   tool is caught by the adapter and returned to the graph as a ToolMessage
   with `status="error"`, letting the LLM self-correct rather than crashing.

Environment variables (set in .env or shell):
    GROQ_API_KEY     – required for ChatGroq
    GROQ_MODEL       – optional, defaults to "llama-3.1-8b-instant"
    MCP_SERVER_URL   – optional, defaults to "http://localhost:8000/sse"

Run with uv:
    uv run python agent_brain.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import io

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain_core.callbacks import BaseCallbackHandler

class FallbackLogger(BaseCallbackHandler):
    def __init__(self, model_name: str):
        self.model_name = model_name
        
    def on_llm_start(self, serialized, prompts, **kwargs):
        print(f"\n[Agent] Attempting to serve request with model: {self.model_name}")

    def on_llm_error(self, error, **kwargs):
        err_str = str(error).split('\n')[0]
        print(f"[Agent] SKIPPED {self.model_name} due to error: {err_str}")

# ---------------------------------------------------------------------------
# Load .env (OPENAI_API_KEY, etc.) — silently ignored if file is absent
# ---------------------------------------------------------------------------
load_dotenv(override=True)

# ---------------------------------------------------------------------------
# Configuration – override via environment variables
# ---------------------------------------------------------------------------
MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL", "http://localhost:8000/sse")
GOOGLE_API_KEY: str | None = os.getenv("GOOGLE_API_KEY")

# ---------------------------------------------------------------------------
# Model rotation list
# ---------------------------------------------------------------------------
MODEL_PRIORITY: list[str] = [
    "gemini-3.1-flash-lite",
]

# Maximum number of human/assistant/tool turns to keep in the sliding window.
# The system message is always preserved. Older turns are dropped first.
# At ~50 tokens/turn, 12 turns ≈ 600 tokens — safely within budget.
MAX_HISTORY_MESSAGES: int = 6

# ---------------------------------------------------------------------------
# System prompt – strict hotel-receptionist persona
# ---------------------------------------------------------------------------
# NOTE: When used via voice_server.py, the detailed persona instructions are
# loaded from agent_instructions.md and injected by the LiveKit Agent.
# The SYSTEM_PROMPT below is ONLY used for the standalone terminal mode.
# It must NOT conflict with agent_instructions.md.
SYSTEM_PROMPT = SystemMessage(content="""\
You are Olivia, a professional and warm hotel receptionist at NexCell Hotels.
Your role is to assist guests with checking room availability, making bookings,
and answering questions about the hotel.

STRICT RULES:
1. TOOL FIRST: You MUST use your tools for any question about availability,
   bookings, or hotel FAQs — never guess or fabricate data.
2. AVAILABILITY: Always call check_availability before quoting prices or
   confirming that rooms exist. Do NOT invent room types or prices.
3. BOOKING: Only call create_booking AFTER the guest has confirmed ALL of:
   — their full name, desired branch, room type, arrival date, and number of nights.
   If any detail is missing, ask for it before proceeding.
4. NEVER skip steps. You must collect: Name → Branch → Date → Room → Nights → Check Availability → Confirm → Book.
5. ERRORS: If a tool returns an ERROR, relay it clearly and offer alternatives.
6. TONE: Be professional, concise, and friendly. Use British English.
7. SCOPE: Politely decline anything unrelated to NexCell Hotels.

Valid branches: London, Manchester, Edinburgh.
Valid room types: standard_twin, deluxe_double, executive_suite.
Dates must be in YYYY-MM-DD format (you may reformat natural-language dates).
""".strip())


# ---------------------------------------------------------------------------
# Build MCP client connection config
# ---------------------------------------------------------------------------

def _build_mcp_connections() -> dict:
    """
    Returns the MultiServerMCPClient connection dict.

    SSE transport details:
    - "url"       → FastMCP's SSE event-stream endpoint (GET /sse)
    - "transport" → "sse" tells the adapter to use httpx-sse for the stream
                    and HTTP POST for outbound tool calls (/messages/)
    """
    return {
        "nexcell_pms": {
            "transport": "sse",
            # FastMCP exposes the SSE stream at /sse when run with transport="sse"
            "url": MCP_SERVER_URL,
        }
    }


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

async def build_agent(client: MultiServerMCPClient, system_prompt=None):
    """
    Fetch MCP tools via the adapter and compile the LangGraph ReAct agent.

    When called from voice_server.py, system_prompt can be passed as None
    to let the LiveKit Agent instructions take over (avoiding conflicts).
    When called standalone (agent_brain.py __main__), the default SYSTEM_PROMPT
    is used.
    """
    # Step 1 – Discover and adapt MCP tools into LangChain StructuredTools
    mcp_tools = await client.get_tools()

    print(f"\n[Agent] Connected to MCP server.  Tools available: "
          f"{[t.name for t in mcp_tools]}\n")

    # Step 2 – Initialise the LLM with automatic model rotation on rate limits.
    # We build a chain using LangChain's .with_fallbacks() so that if the
    # primary model hits a 429 (rate limit) or decommission error, the next
    # model in the priority list is tried automatically without crashing.
    if not GOOGLE_API_KEY:
        print("Error: GOOGLE_API_KEY is missing from environment.", file=sys.stderr)
        raise EnvironmentError(
            "GOOGLE_API_KEY is not set.  "
            "Add it to a .env file or export it in your shell."
        )

    def _make_llm(model_id: str):
        return ChatGoogleGenerativeAI(
            model=model_id,
            google_api_key=GOOGLE_API_KEY,
            temperature=0.3,
            max_retries=2,
            callbacks=[FallbackLogger(model_id)]
        )

    # Build primary LLM
    primary_model = MODEL_PRIORITY[0]
    llm = _make_llm(primary_model)
    print(f"[Agent] Primary LLM: {primary_model}")

    # Step 3 – Compile the ReAct agent graph
    agent_kwargs = {
        "model": llm,
        "tools": mcp_tools,
    }
    # Only inject the system prompt if one is provided (standalone mode).
    # In voice mode, the LiveKit Agent instructions handle the persona.
    # In langgraph, system prompts are passed via prompt (in version 1.2.4)
    if system_prompt is not None:
        agent_kwargs["prompt"] = system_prompt

    agent_graph = create_react_agent(**agent_kwargs)

    return agent_graph


# ---------------------------------------------------------------------------
# Interactive terminal loop
# ---------------------------------------------------------------------------

async def main() -> None:
    """
    Opens the MCP SSE connection, compiles the agent, then enters an
    interactive guest-service loop until the user types 'quit' or 'exit'.

    Conversation history is maintained in `chat_history` so the agent
    retains context across multiple turns (multi-turn conversation support).
    """
    print("\n" + "=" * 60)
    print("  NexCell AI Hotel Receptionist")
    print("  Connecting to MCP server at:", MCP_SERVER_URL)
    print("=" * 60)

    # MultiServerMCPClient is instantiated directly.
    #
    # handle_tool_errors=True:  instead of raising an exception when a tool
    # fails, the adapter catches the error and returns a ToolMessage with
    # status="error".  The LLM then sees the error text and can self-correct
    # (e.g., retry with different arguments or apologise to the guest).
    client = MultiServerMCPClient(
        connections=_build_mcp_connections(),
        handle_tool_errors=True,   # graceful degradation on tool failures
    )

    agent_graph = await build_agent(client, system_prompt=SYSTEM_PROMPT)

    chat_history: list[BaseMessage] = []

    print("\nType your message below.  Type 'quit' or 'exit' to leave.\n")

    while True:
        try:
            user_input = input("Guest: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Receptionist] Thank you for contacting NexCell Hotels. Goodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in {"quit", "exit", "bye", "goodbye"}:
            print("\nOlivia: Thank you for contacting NexCell Hotels. "
                  "We hope to welcome you soon. Goodbye!")
            break

        # Append the new guest message to history
        chat_history.append(HumanMessage(content=user_input))

        # Apply sliding window — keep only the last MAX_HISTORY_MESSAGES turns
        # (system message is not part of chat_history so it is unaffected)
        if len(chat_history) > MAX_HISTORY_MESSAGES:
            chat_history = chat_history[-MAX_HISTORY_MESSAGES:]

        # ------------------------------------------------------------------
        # Invoke the agent graph with the full conversation history
        # The graph will:
        #   1. Pass history + system prompt to the LLM
        #   2. Execute any tool calls the LLM requests (via the MCP client)
        #   3. Reflect on tool results and produce a final AIMessage
        # ------------------------------------------------------------------
        try:
            result = await agent_graph.ainvoke(
                {"messages": chat_history},
                # config lets you add callbacks, tags, etc.
                config={"configurable": {"thread_id": "nexcell-session"}},
            )

            # Extract the agent's final response (last AIMessage in the list)
            response_messages: list[BaseMessage] = result.get("messages", [])

            # Find the last AIMessage that has non-empty text content
            agent_reply: str = "(No response generated)"
            for msg in reversed(response_messages):
                if isinstance(msg, AIMessage) and msg.content:
                    agent_reply = (
                        msg.content
                        if isinstance(msg.content, str)
                        else str(msg.content)
                    )
                    break

            # Append the agent reply to history for the next turn
            chat_history.append(AIMessage(content=agent_reply))

            print(f"\nAlex: {agent_reply}\n")

        except Exception as exc:  # noqa: BLE001
            # Surface errors clearly without crashing the loop
            print(f"\n[System Error] {type(exc).__name__}: {exc}")
            print("Please try rephrasing your request.\n")
            # Remove the failed HumanMessage so the history stays consistent
            if chat_history and isinstance(chat_history[-1], HumanMessage):
                chat_history.pop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Ensure UTF-8 output on Windows terminals
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    asyncio.run(main())
