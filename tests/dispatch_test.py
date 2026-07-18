import asyncio
import os
from livekit import api
from dotenv import load_dotenv

load_dotenv()

async def main():
    lkapi = api.LiveKitAPI(
        os.environ['LIVEKIT_URL'],
        os.environ['LIVEKIT_API_KEY'],
        os.environ['LIVEKIT_API_SECRET']
    )
    print("Dispatching agent...")
    await lkapi.agent_dispatch.create_dispatch(
        api.CreateAgentDispatchRequest(
            room='nexcell-lobby',
            agent_name='nexcell-receptionist'
        )
    )
    print("Dispatched!")
    await lkapi.aclose()

asyncio.run(main())
