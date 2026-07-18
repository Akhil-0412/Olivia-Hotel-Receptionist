import asyncio
import httpx
from livekit import rtc

async def main():
    print("Fetching token...")
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://127.0.0.1:7860/api/token?name=Guest&room=nexcell-lobby")
        data = resp.json()
        token = data["token"]
        url = data["url"]

    print("Connecting to LiveKit Room...")
    room = rtc.Room()
    await room.connect(url, token)
    print("Connected to room as Guest!")

    print("Dispatching agent...")
    async with httpx.AsyncClient() as client:
        resp = await client.post("http://127.0.0.1:7860/api/dispatch", json={"room": "nexcell-lobby"})
        print(f"Dispatch response: {resp.json()}")

    print("Waiting for agent to speak...")
    # Just wait to see if any participant joins
    async def wait_for_agent():
        while True:
            for p in room.remote_participants.values():
                if "receptionist" in p.identity.lower() or "nexcell" in p.identity.lower():
                    print(f"Agent joined: {p.identity}")
                    # wait a bit for audio track
                    await asyncio.sleep(2)
                    for track_pub in p.track_publications.values():
                        print(f"Agent track published: {track_pub.sid}")
                    return
            await asyncio.sleep(1)
            
    await asyncio.wait_for(wait_for_agent(), timeout=30.0)
    print("Test passed!")
    await room.disconnect()

asyncio.run(main())
