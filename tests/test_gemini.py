import asyncio
from agent_brain import build_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

async def test():
    mcp = MultiServerMCPClient(connections={})
    agent = await build_agent(mcp)
    print('Invoking agent...')
    res = await agent.ainvoke({'messages': [('user', 'Hello')]})
    print(res['messages'][-1].content)

asyncio.run(test())
