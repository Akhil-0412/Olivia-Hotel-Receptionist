import os
import asyncio
from dotenv import load_dotenv
from livekit.plugins import google

load_dotenv()

async def test():
    print("Testing Google TTS...")
    try:
        tts = google.TTS(credentials_info=os.environ.get('GOOGLE_API_KEY'))
        print("TTS instantiated.")
        chunk = tts.synthesize('hello')
        print("Synthesize called.")
        async for c in chunk:
            print("Received bytes:", len(c.data))
            break
        print("Google synthesis SUCCESS")
    except Exception as e:
        print("Google synthesis FAILED:", e)

asyncio.run(test())
