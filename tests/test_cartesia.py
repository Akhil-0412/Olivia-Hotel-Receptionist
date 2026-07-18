import os
import asyncio
from dotenv import load_dotenv
from livekit.plugins import cartesia

load_dotenv()

async def test():
    print("Testing Cartesia with specific voice...")
    try:
        tts = cartesia.TTS(api_key=os.environ.get('Cartesia_API_KEY'), voice="02aeee94-c02b-456e-be7a-659672acf82d")
        print("TTS instantiated.")
        chunk = tts.synthesize('hello')
        print("Synthesize called.")
        async for c in chunk:
            print("Received bytes:", len(c.data))
            break
        print("Cartesia synthesis SUCCESS")
    except Exception as e:
        print("Cartesia synthesis FAILED:", e)

asyncio.run(test())
