---
title: NexCell Voice Agent
emoji: 🏨
colorFrom: blue
colorTo: indigo
sdk: docker
app_file: app.py
pinned: false
---

# NexCell Voice Agent

An AI voice receptionist for NexCell Hotels. Guests connect over WebRTC, speak naturally, and the agent handles real bookings, availability checks, FAQ lookups, and invoice delivery through a backend tool server, rather than just answering scripted questions.

## Tech Stack

| Layer            | Technology                                                            |
|------------------|------------------------------------------------------------------------|
| Voice transport  | LiveKit Agents SDK (WebRTC), Silero VAD                               |
| STT              | Groq (`whisper-large-v3`)                                             |
| LLM              | Google Gemini (`gemini-3.1-flash-lite`) via `langchain-google-genai`  |
| Orchestration    | LangGraph (`langchain.agents.create_agent`)                          |
| TTS              | Cartesia                                                              |
| Tool protocol    | FastMCP (SSE transport) + `langchain-mcp-adapters`                    |
| Invoicing        | Jinja2 templates + SMTP (`smtplib`)                                   |
| Frontend         | Starlette web dashboard (LiveKit Components)                          |
| Dependency mgmt  | `uv`                                                                   |

## Architecture

Guest audio flows from the browser dashboard into the voice worker, which runs a LangGraph agent backed by Gemini. The agent never touches inventory, bookings, or email directly; it only calls MCP tools and reacts to their results. That keeps the reasoning layer, tool execution layer, and web frontend as fully decoupled processes that can be modified independently.

**Flow:**

1. Browser dashboard (LiveKit Components UI) opens a WebRTC session.
2. `frontend_server.py` connects the browser to the room and dynamically spawns a `voice_server.py` worker process.
3. `voice_server.py` runs the LangGraph agent (Gemini), which interprets the conversation and decides which tool to call.
4. Tool calls go out over SSE to `mcp_server.py` (FastMCP), which exposes:
   - `check_availability`
   - `create_booking`
   - `search_faq`
   - `send_invoice`
5. `send_invoice` renders a Jinja2 HTML template and sends it to the guest over SMTP.

The agent's persona, step-by-step booking flow, and guardrails (no hallucinated prices, no invented booking references, no skipped steps) are defined in `agent_instructions_compact.md` and injected as the system prompt on every turn.

## Implemented MCP Tools

Defined in `src/mcp_server.py`, backed by in-memory inventory and booking stores. This project implements four distinct tools from the suggested categories:

1. **Availability Checker** (`check_availability`) — looks up per-night pricing and remaining units for a branch, arrival date, and optional room type filter.
2. **Booking System** (`create_booking`) — validates availability, deducts inventory, generates a booking reference, and persists the reservation.
3. **FAQ Search** (`search_faq`) — keyword/tag-matches a guest query against a static FAQ knowledge base and returns ranked results.
4. **Email Sender** (`send_invoice`) — renders a branded HTML invoice from a Jinja2 template with embedded room images, and emails it to the guest over SMTP.

## Setup Instructions

### Requirements

Python 3.11+, [`uv`](https://docs.astral.sh/uv/).

### 1. Environment variables

Create a `.env` file in the project root:

```env
# LiveKit
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

# Inference
GROQ_API_KEY=your_groq_key
GOOGLE_API_KEY=your_gemini_key
CARTESIA_API_KEY=your_cartesia_key

# Invoice email (SMTP)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_sender_email
SENDER_PASSWORD=your_app_password
```

### 2. Install dependencies

```bash
uv sync
```

### 3. Run the services

You only need two terminals, because the web UI automatically handles spawning the voice agent securely in the background when a guest connects.

**Terminal 1 — MCP tool server**

```bash
uv run python src/mcp_server.py
```

Starts FastMCP on `http://127.0.0.1:8000` (SSE transport).

**Terminal 2 — Web dashboard & Orchestrator**

```bash
uv run python src/frontend_server.py
```

Serves the connection dashboard at `http://127.0.0.1:8001` and listens for connection requests to dynamically spawn voice workers.

### 4. Connect and talk

Open `http://127.0.0.1:8001` in your browser, click Connect, and speak to the receptionist. Live transcription and agent state are shown in the dashboard as the conversation progresses.

## Testing

```bash
uv run python tests/test_mcp_client.py   # availability, booking, FAQ tools
uv run python tests/test_email.py        # SMTP + Jinja2 invoice pipeline
uv run python tests/test_gemini.py       # LLM configuration
```
