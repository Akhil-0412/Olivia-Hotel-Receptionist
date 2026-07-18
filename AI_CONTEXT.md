# AI Project Memory: NexCell / Olivia Hotel Receptionist

This file serves as a quick-context memory bank for any AI assistant interacting with this project. By reading this file, the AI can instantly understand the architecture, deployment locations, and operational state without consuming excessive context tokens.

## 1. Project Overview
- **Name:** NexCell Voice Agent (deployed as Olivia Hotel Receptionist)
- **Purpose:** An AI voice receptionist for hotels. Guests connect over WebRTC, speak naturally, and the agent handles real bookings, availability checks, FAQ lookups, and invoice delivery through a backend tool server.

## 2. Deployments & Links
- **Backend (Voice Agent & MCP Server):** 
  - Hosted on **Hugging Face Spaces**: [Akhil-008/olivia-hotel-receptionist](https://huggingface.co/spaces/Akhil-008/olivia-hotel-receptionist?logs=container)
- **Frontend (Web Dashboard):** 
  - Hosted on **Vercel**: [akhil-0412s-projects/olivia-hotel-receptionist](https://vercel.com/akhil-0412s-projects/olivia-hotel-receptionist)

## 3. Local Development Architecture
The project is split into three main components, managed via `uv`, that run in separate terminals locally:
1. **MCP Tool Server (`src/mcp_server.py`):** Runs the FastMCP server on port 8000. It manages tools like availability, booking, FAQs, and invoicing. It uses a local SQLite database (`data/nexcell.db`).
2. **Web Dashboard (`src/frontend_server.py`):** Runs the Starlette/UI server on port 7860/8001. Provides the LiveKit connection token to the browser. *Note: It does NOT automatically spawn the background agent worker locally.*
3. **Voice Agent Worker (`src/voice_server.py start`):** Runs the LiveKit Agent worker. Connects to LiveKit Cloud, listens for jobs in the `nexcell-lobby` room, and handles the STT -> LLM -> TTS pipeline.

## 4. Tech Stack & APIs
- **WebRTC/Transport:** LiveKit
- **STT (Speech-to-Text):** Groq (`whisper-large-v3`) via OpenAI plugin.
- **LLM:** Google Gemini (`gemini-3.1-flash-lite`) orchestrated via LangGraph.
- **TTS (Text-to-Speech):** Cartesia.
- **Tool Protocol:** FastMCP (SSE transport).

## 5. Critical Notes for Local Testing
- **LiveKit Clash Warning:** If the local `.env` uses the same `LIVEKIT_URL` and API keys as the Hugging Face production deployment, the local `voice_server.py` will compete with the production agent for connections. For isolated local testing, a separate LiveKit Dev project should be used.
- **Module Paths:** `mcp_server.py` was recently patched locally to include `sys.path.append(str(PROJECT_ROOT))` to resolve `ModuleNotFoundError: No module named 'src'` when run directly.
