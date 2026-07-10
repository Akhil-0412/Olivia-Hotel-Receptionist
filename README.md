# NexCell Voice Agent

An enterprise-grade, AI-powered voice receptionist designed to handle natural customer conversations, process real-time hotel bookings, and resolve customer inquiries. 

Unlike traditional interactive voice response (IVR) systems, this agent utilizes an **agentic architecture** coupled with the **Model Context Protocol (MCP)** to interact dynamically with backend business systems.

##  Features

- **Ultra-Low Latency Voice Interaction:** Built on WebRTC for real-time, asynchronous, duplex audio streaming.
- **Agentic Tool Execution:** Uses LangGraph to orchestrate state, memory, and intelligent tool routing, allowing the agent to break down complex tasks and execute functions on backend systems.
- **Preference Search:** Capable of recommending rooms and packages based on conversational preferences.
- **Decoupled Architecture:** Separation of the language reasoning layer, voice gateway, and business logic tools via FastMCP.

## 🛠️ Integrated MCP Tools

The agent performs actions through a decoupled FastMCP-compliant server that exposes the following capabilities:

1. **`check_availability`** 
   Real-time inventory lookup. Queries an in-memory inventory store by branch, date, and optional room filters to return per-night pricing and total costs.
2. **`create_booking`** 
   Reservation manager. Validates stock availability, deducts inventory, generates a secure UUID booking reference, and persists the record.
3. **`search_faq`** 
   Semantic knowledge retrieval. Token-scores keyword queries against a knowledge base to return relevance-ranked hotel policies and destination information.
4. **`send_invoice`** 
   Notification dispatch. Generates responsive, branded HTML invoices using Jinja2 templates and emails them directly to the guest securely via SMTP.

##  Architecture & Tech Stack

- **Voice/Streaming Pipeline:** [LiveKit WebRTC](https://livekit.io/) (Agents SDK) for robust real-time audio transport and Voice Activity Detection (Silero VAD).
- **LLM Orchestration:** [LangGraph](https://www.langchain.com/langgraph) & LangChain for robust state management and multi-step reasoning.
- **Inference Engines:** 
  - **STT:** Groq (`whisper-large-v3`)
  - **LLM:** Groq-hosted reasoning engine (`llama-3.1-70b-versatile`)
  - **TTS:** Cartesia AI 
- **Tool Protocol:** [FastMCP](https://github.com/jlowin/fastmcp) with SSE Transport, dynamically mapped into the LangChain ecosystem via `langchain-mcp-adapters`.
- **Frontend / UI:** Starlette / FastAPI for local state rendering and web UI delivery.

##  Setup Instructions

### 1. Requirements

Ensure you have Python 3.10+ and [`uv`](https://docs.astral.sh/uv/) installed on your machine for fast dependency management.

### 2. Environment Variables

Create a `.env` file in the root directory and configure your keys:

```env
# LiveKit Configuration
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

# Inference Providers
GROQ_API_KEY=your_groq_key
CARTESIA_API_KEY=your_cartesia_key

# Optional: Email dispatch configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_sender_email
SENDER_PASSWORD=your_app_password
```

### 3. Install Dependencies

```bash
uv sync
# Or manually install requirements:
uv pip install livekit-agents livekit-plugins-langchain livekit-plugins-openai livekit-plugins-cartesia livekit-plugins-silero fastmcp langchain-mcp-adapters langgraph jinja2
```

### 4. Running the Services

The system requires three core services running concurrently. 

**Terminal 1 (Start MCP Backend Tools):**
```bash
uv run python src/mcp_server.py
```
*(Initializes the FastMCP server with HTTP/SSE endpoints on port 8000)*

**Terminal 2 (Start Local Web UI / Frontend Server):**
```bash
uv run python src/frontend_server.py
```
*(Starts the Starlette web server on port 8001 to serve assets and control flows)*

**Terminal 3 (Start Voice Agent Gateway):**
```bash
uv run python src/voice_server.py dev
```
*(Connects the LangGraph intelligence to the LiveKit WebRTC room)*

### 5. Connect and Interact

Once all services are running, navigate to your web dashboard or the LiveKit Agents Playground to join the room and begin speaking to the AI Receptionist.

---
*Built for production scalability, maintaining ultra-low latency and deterministic tool execution.*
