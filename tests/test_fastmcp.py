import sys
print("Before FastMCP:", sys.path)
from fastmcp import FastMCP
mcp = FastMCP("Test")
print("After FastMCP:", sys.path)
