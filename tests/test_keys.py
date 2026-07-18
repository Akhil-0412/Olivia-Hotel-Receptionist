import os
import sys
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def test_all():
    print("==================================")
    print("Testing API Keys")
    print("==================================")
    
    # Test Cartesia
    try:
        from livekit.plugins import cartesia
        print("Testing Cartesia Synthesis...")
        tts = cartesia.TTS(
            voice="c46cf1f6-49a1-4d67-9a57-ff859a4046d3",
            model="sonic-3.5",
            api_key=os.environ.get("Cartesia_API_KEY"),
        )
        import livekit.agents.utils.http_context
        async with livekit.agents.utils.http_context.open():
            chunk = tts.synthesize("Hello! This is a test of the livekit plugins cartesia.")
            async for c in chunk:
                print(f"Received audio frame: {len(c.data)} bytes")
                break
        print("Cartesia TTS successfully instantiated and synthesized!")
    except Exception as e:
        import traceback
        print("Cartesia TTS failed:")
        traceback.print_exc()

    # Test Groq
    try:
        from livekit.plugins import openai
        print("Testing Groq STT...")
        stt = openai.STT(base_url="https://api.groq.com/openai/v1", api_key=os.environ.get("GROQ_API_KEY"), model="whisper-large-v3")
        print("Groq STT instantiated successfully!")
    except Exception as e:
        print(f"Groq STT failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_all())
