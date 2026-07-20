"""
app.py
======
NexCell Orchestrator — runs services in a single process for memory efficiency:
  1. MCP Server (FastMCP, in-process async task on port 8000)
  2. Voice Worker (LiveKit agent, subprocess — needs its own event loop)
  3. FastAPI Health / Payment server (uvicorn, port from $PORT env)

The FastAPI app also:
  - Initialises the SQLite database on startup
  - Starts the 24-hour lock-expiry background daemon
  - Serves the mock Stripe payment portal under /pay/...
  - Serves static assets under /assets/...

Optimised for Render.com free tier (512 MB RAM / 0.1 vCPU).
"""
import asyncio
import contextlib
import os
import subprocess
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.database import init_db
from src.lock_scheduler import lock_expiry_daemon
from src.payment_portal import payment_routes
from src.mcp_server import invoice_routes, mcp

# ---------------------------------------------------------------------------
# Lifespan (startup/shutdown) — FastAPI 0.115+ compatible
# ---------------------------------------------------------------------------

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    init_db()
    print("[App] SQLite DB initialised.", flush=True)

    # Start lock expiry daemon
    lock_task = asyncio.create_task(lock_expiry_daemon())
    print("[App] Lock expiry daemon started.", flush=True)

    # Start MCP server in-process (saves ~100 MB vs subprocess)
    mcp_task = asyncio.create_task(
        mcp.run_async(transport="sse", host="127.0.0.1", port=8000)
    )
    print("[App] MCP Server started in-process on port 8000.", flush=True)

    # Start Voice Worker as subprocess (needs its own event loop)
    voice_process = None
    if os.environ.get("LIVEKIT_URL"):
        print("[App] Starting Voice Worker subprocess...", flush=True)
        voice_process = subprocess.Popen(
            [sys.executable, "-m", "src.voice_server", "start"],
            stdout=sys.stdout,
            stderr=sys.stderr,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        print("[App] Voice Worker started.", flush=True)
    else:
        print("[App] LIVEKIT_URL not set — voice worker skipped.", flush=True)

    yield

    # --- shutdown ---
    lock_task.cancel()
    mcp_task.cancel()
    if voice_process:
        voice_process.terminate()
    for t in [lock_task, mcp_task]:
        try:
            await t
        except (asyncio.CancelledError, Exception):
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
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"[Orchestrator] Starting NexCell on port {port}...", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
