import os
import subprocess
from starlette.applications import Starlette
from starlette.responses import JSONResponse, HTMLResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.requests import Request
from livekit import api as livekit_api
import uvicorn
from dotenv import load_dotenv
from pathlib import Path
import sys

# Load env variables so we can access LIVEKIT_API_KEY etc
load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent

async def get_token(request: Request):
    """
    Generates a LiveKit JWT token for the browser client.
    """
    name = request.query_params.get("name", "Guest")
    room_name = request.query_params.get("room", "nexcell-lobby")
    
    token = livekit_api.AccessToken(
        os.environ["LIVEKIT_API_KEY"],
        os.environ["LIVEKIT_API_SECRET"]
    ).with_grants(
        livekit_api.VideoGrants(room_join=True, room=room_name)
    ).with_identity(name).to_jwt()
    
    return JSONResponse({
        "token": token,
        "url": os.environ["LIVEKIT_URL"]
    })

async def dispatch_agent(request: Request):
    """
    Triggers the voice_server.py to join the room.
    In a real app, this might use the LiveKit Agents API to dispatch a worker.
    Here we just spawn the process if it's not already running.
    """
    try:
        # In a managed Docker environment, voice_server.py is running via supervisor.
        # We don't spawn a new process here to avoid duplicate agents.
        return JSONResponse({"success": True, "message": "Voice server is managed by supervisor."})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

# Create the Starlette App
app = Starlette(debug=True, routes=[
    # The API endpoints
    Route("/api/token", get_token, methods=["GET"]),
    Route("/api/dispatch", dispatch_agent, methods=["POST"]),
    
    # Static mount for images (logo.png) in the assets directory
    Mount("/assets", app=StaticFiles(directory=str(PROJECT_ROOT / "assets"), html=False), name="assets"),
    
    # Static mount for the frontend UI
    Mount("/", app=StaticFiles(directory=str(PROJECT_ROOT / "frontend"), html=True), name="frontend"),
])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    print("\n" + "="*50)
    print(f"NexCell UI Server running on port {port}!")
    print(f"-> Open http://127.0.0.1:{port} in your browser")
    print("="*50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
