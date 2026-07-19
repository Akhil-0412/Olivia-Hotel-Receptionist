"""
app.py
======
NexCell Orchestrator — runs all three services in a single process:
  1. MCP Server (FastMCP, port 8000 via subprocess)
  2. Voice Worker (LiveKit agent, via subprocess)
  3. FastAPI Health / Payment server (uvicorn, port 7860)

The FastAPI app also:
  - Initialises the SQLite database on startup
  - Starts the 24-hour lock-expiry background daemon
  - Serves the mock Stripe payment portal under /pay/...
  - Serves static assets under /assets/...
"""
import asyncio
import contextlib
import os
import subprocess
import sys
import time

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

try:
    import spaces
    @spaces.GPU
    def _dummy_gpu_function():
        pass
except ImportError:
    pass

from src.database import init_db
from src.lock_scheduler import lock_expiry_daemon
from src.payment_portal import payment_routes
from src.mcp_server import invoice_routes

# ---------------------------------------------------------------------------
# Lifespan (startup/shutdown) — FastAPI 0.115+ compatible
# ---------------------------------------------------------------------------

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    init_db()
    print("[App] SQLite DB initialised.", flush=True)
    task = asyncio.create_task(lock_expiry_daemon())
    print("[App] Lock expiry daemon started.", flush=True)
    yield
    # --- shutdown ---
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(title="NexCell Hotel Backend", version="2026.1.0", lifespan=lifespan)

# Mount static assets (images, CSS, etc.)
_assets_dir = os.path.join(os.path.dirname(__file__), "assets")
if os.path.isdir(_assets_dir):
    app.mount("/api/assets", StaticFiles(directory=_assets_dir), name="assets")

# Mount Starlette payment routes & invoice routes
for route in payment_routes + invoice_routes:
    app.router.routes.append(route)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def read_root() -> str:
    return """
    <html><body style="font-family:sans-serif;padding:40px;background:#0f172a;color:#e2e8f0">
    <h1>🏨 NexCell Hotel Backend</h1>
    <p>MCP Server: <code>http://127.0.0.1:8000/sse</code></p>
    <p>Payment Portal: <code>/api/pay/&lt;reference&gt;</code></p>
    <p>Status: <strong style="color:#4ade80">Running ✓</strong></p>
    </body></html>
    """


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok", "service": "nexcell-backend"}


# ---------------------------------------------------------------------------
# Entry point — orchestrates all processes
# ---------------------------------------------------------------------------

def main() -> None:
    # 1. Determine project root
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    # 2. Prefer the virtual environment's Python if it exists
    if os.name == 'nt':
        venv_python = os.path.join(project_root, ".venv", "Scripts", "python.exe")
    else:
        venv_python = os.path.join(project_root, ".venv", "bin", "python")
        
    python_exe = venv_python if os.path.exists(venv_python) else sys.executable

    print("[Orchestrator] Starting MCP Server (port 8000)...", flush=True)
    mcp_process = subprocess.Popen(
        [python_exe, "-m", "src.mcp_server"],
        stdout=sys.stdout,
        stderr=sys.stderr,
        cwd=project_root,
    )

    print("[Orchestrator] Waiting for MCP Server to bind (5 s)...", flush=True)
    time.sleep(5)

    print("[Orchestrator] Starting Voice Worker...", flush=True)
    voice_process = subprocess.Popen(
        [python_exe, "-m", "src.voice_server", "dev"],
        stdout=sys.stdout,
        stderr=sys.stderr,
        cwd=project_root,
    )

    port = int(os.environ.get("PORT", 7860))
    print(f"[Orchestrator] Starting Payment/Health Server on port {port}...", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
