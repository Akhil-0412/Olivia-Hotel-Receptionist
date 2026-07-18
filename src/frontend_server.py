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
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
    """
    try:
        req = await request.json()
        room_name = req.get("room", "nexcell-lobby")
        
        # Explicitly dispatch the agent to the room
        lkapi = livekit_api.LiveKitAPI(
            os.environ["LIVEKIT_URL"], 
            os.environ["LIVEKIT_API_KEY"], 
            os.environ["LIVEKIT_API_SECRET"]
        )
        await lkapi.agent_dispatch.create_dispatch(
            livekit_api.CreateAgentDispatchRequest(
                room=room_name,
                agent_name="nexcell-receptionist"
            )
        )
        await lkapi.aclose()
        return JSONResponse({"success": True, "message": "Agent dispatched successfully."})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

from src.payment_portal import payment_routes
from src.mcp_server import api_invoice, view_invoice

# Create the Starlette App
app = Starlette(debug=True, routes=[
    # The API endpoints
    Route("/api/token", get_token, methods=["GET"]),
    Route("/api/dispatch", dispatch_agent, methods=["POST"]),
    Route("/api/invoice", api_invoice, methods=["POST"]),
    Route("/invoice/{booking_id}", view_invoice, methods=["GET"]),
    
    # Static mount for images (logo.png) in the assets directory
    Mount("/assets", app=StaticFiles(directory=str(PROJECT_ROOT / "assets"), html=False), name="assets"),
] + payment_routes + [
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
