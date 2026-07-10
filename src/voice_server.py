"""
voice_server.py
===============
Chunk 2: The Voice & Async Streaming Layer

Architecture (LiveKit Agents 1.x SDK):
---------------------------------------
  AgentSession        ← orchestrates the full pipeline, joins the room
      ├── STT         : Groq Whisper (via OpenAI plugin redirected to Groq)
      ├── LLM         : LangGraph ReAct agent (wrapped via LLMAdapter)
      ├── TTS         : ElevenLabs (Rachel voice, free tier)
      └── VAD         : Silero (bundled, pre-warmed to avoid cold starts)

  Agent               ← holds the persona / instructions

Key fix vs v1 skeleton:
  WRONG: agent.start(ctx.room)   ← Agent has no .start() that joins a room
  RIGHT: AgentSession.start(agent=agent, room=ctx.room)
"""

from __future__ import annotations

import asyncio
import datetime
import os
import sys
import io
import httpx
from pathlib import Path

# Force UTF-8 for console output on Windows to prevent UnicodeEncodeError (e.g. from emojis)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
)
from livekit.plugins import elevenlabs, langchain, openai, silero, cartesia

# Fix import paths so the IDE and python can resolve it
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent_brain import _build_mcp_connections, build_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv(override=True)


# ---------------------------------------------------------------------------
# Prewarm: load Silero VAD once per worker process to avoid cold-start delay
# ---------------------------------------------------------------------------

def prewarm(proc) -> None:
    proc.userdata["vad"] = silero.VAD.load()


# ---------------------------------------------------------------------------
# Entrypoint: called once per room job
# ---------------------------------------------------------------------------

async def entrypoint(ctx: JobContext) -> None:
    # 1. Connect to the LiveKit room (audio only — we don't need video)
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # 2. STT — Groq Whisper via the OpenAI-compatible plugin
    stt = openai.STT(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.environ["GROQ_API_KEY"],
        model="whisper-large-v3",
    )

    # 3. TTS — Cartesia (free tier, no Inworld account needed)
    tts = cartesia.TTS(
        api_key=os.environ.get("Cartesia_API_KEY"),
    )

    # 4. Define the agent persona using our explicit instructions file
    prompt_path = Path(__file__).parent / "prompts" / "agent_instructions_compact.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        agent_instructions = f.read()

    try:
        today_str = datetime.date.today().strftime("%d %B %Y")
        if today_str.startswith("0"):
            today_str = today_str[1:]
    except Exception:
        today_str = datetime.date.today().isoformat()

    date_header = (
        f"## ⚠️ LIVE DATE CONTEXT — READ THIS FIRST\n"
        f"Today's date is **{today_str}**. This is the real, current date.\n"
        f"- You MUST use this date when telling guests the current date.\n"
        f"- You MUST reject any booking date that is before {today_str} as being in the past.\n"
        f"- Do NOT use your training data to guess the current year. The year is in this date.\n\n"
        f"---\n\n"
    )

    agent_instructions = date_header + agent_instructions

    # 5. LLM — build the LangGraph ReAct agent wrapped with MCP,
    #    then wrap it for LiveKit
    from langchain_core.messages import SystemMessage

    mcp_client = MultiServerMCPClient(
        connections=_build_mcp_connections(),
        handle_tool_errors=True,
    )

    # Retry loop to wait for mcp_server to boot up (especially in Docker/supervisor environments)
    langgraph_agent = None
    max_retries = 15
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[Voice Worker] Attempting to connect to MCP Server (attempt {attempt}/{max_retries})...")
            langgraph_agent = await build_agent(
                mcp_client,
                system_prompt=SystemMessage(content=agent_instructions)
            )
            break
        except Exception as e:
            if attempt == max_retries:
                print(f"[Voice Worker] Fatal error: Could not connect to MCP server after {max_retries} attempts.")
                raise e
            print(f"[Voice Worker] MCP Server not ready yet ({type(e).__name__}). Retrying in 2 seconds...")
            await asyncio.sleep(2)

    # Verification: Wrap the ainvoke method to log the first turn's messages
    original_ainvoke = langgraph_agent.ainvoke
    _first_turn_logged = False
    
    async def logging_ainvoke(*args, **kwargs):
        nonlocal _first_turn_logged
        if not _first_turn_logged:
            _first_turn_logged = True
            input_dict = args[0] if args else kwargs.get("input", {})
            messages = input_dict.get("messages", [])
            print("\n" + "="*80)
            print("VERIFICATION: Messages going into agent_graph.ainvoke() on first turn:")
            for idx, msg in enumerate(messages):
                print(f"[{idx}] {type(msg).__name__}: {str(msg.content)[:200]}...")
            print("="*80 + "\n")
        return await original_ainvoke(*args, **kwargs)
        
    langgraph_agent.ainvoke = logging_ainvoke

    llm_adapter = langchain.LLMAdapter(graph=langgraph_agent)

    agent = Agent(
        instructions=agent_instructions,
    )

    # 6. AgentSession wires STT → LLM → TTS and joins the room
    #    as a proper participant (this is what was missing before).
    session = AgentSession(
        stt=stt,
        llm=llm_adapter,
        tts=tts,
        vad=ctx.proc.userdata["vad"],
    )

    await session.start(agent=agent, room=ctx.room)

    # Proactive greeting
    greeting = "Welcome to NexCell Hotels! How can I help you today?"
    if ctx.room.remote_participants:
        session.say(greeting, allow_interruptions=True)
        
    @ctx.room.on("participant_connected")
    def on_participant_connected(participant):
        session.say(greeting, allow_interruptions=True)

    # 7. Block until the room disconnects (keeps MCP connection alive)
    shutdown_event = asyncio.Event()
    ctx.room.on("disconnected", shutdown_event.set)
    await shutdown_event.wait()


async def send_invoice_direct(booking_id: str, email_address: str) -> bool:
    """
    Call the MCP server's /api/invoice endpoint directly over HTTP.
    This bypasses the LLM entirely — zero tokens consumed.
    Returns True on success, False on failure.
    """
    url = "http://127.0.0.1:8000/api/invoice"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={
                "booking_id": booking_id,
                "email_address": email_address,
            })
            data = resp.json()
            if data.get("success"):
                print(f"[Invoice] Sent to {email_address}, file: {data.get('file')}")
                return True
            else:
                print(f"[Invoice] ERROR: {data.get('error')}")
                return False
    except Exception as e:
        print(f"[Invoice] HTTP call failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            agent_name="nexcell-receptionist",
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )
