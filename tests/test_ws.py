import os
import asyncio
import aiohttp
from dotenv import load_dotenv

load_dotenv()

async def t():
    print("Testing pure aiohttp websocket to Cartesia...")
    try:
        api_key = os.environ.get("Cartesia_API_KEY")
        url = f"wss://api.cartesia.ai/tts/websocket?api_key={api_key}&cartesia_version=2024-06-10"
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url) as ws:
                print("WebSocket Connected Successfully!")
                await ws.close()
    except Exception as e:
        print(f"WebSocket Error: {type(e).__name__} - {e}")

if __name__ == "__main__":
    asyncio.run(t())
