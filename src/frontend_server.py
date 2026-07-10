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
        # Launch voice_server.py dev mode in the background
        # It connects to the LiveKit room and acts as the agent
        log_file = open(PROJECT_ROOT / "logs" / "voice_server.log", "w")
        subprocess.Popen(
            ["uv", "run", "python", str(PROJECT_ROOT / "src" / "voice_server.py"), "connect", "--room", "nexcell-lobby"],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        return JSONResponse({"success": True})
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
    print("\n" + "="*50)
    print("NexCell UI Server running!")
    print("-> Open http://127.0.0.1:8001 in your browser")
    print("="*50 + "\n")
    uvicorn.run(app, host="127.0.0.1", port=8001)
