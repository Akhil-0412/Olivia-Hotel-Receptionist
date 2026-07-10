"""
test_mcp_client.py
==================
NexCell AI – MCP Server Integration Test
Connects to the running mcp_server.py via the MCP Python SDK (in-process
stdio transport) and invokes each of the three core tools:
  1. check_availability
  2. create_booking
  3. search_faq

Usage:
    # Terminal 1 – start the server (Streamable-HTTP mode):
    #   python mcp_server.py
    #
    # Terminal 2 – run this test (stdio in-process mode, no server needed):
    #   python test_mcp_client.py

The test uses the FastMCP in-process Client so it runs without a live HTTP
server, giving deterministic, zero-network-overhead results suitable for CI.
To test over HTTP instead, see the commented-out section at the bottom.
"""

from __future__ import annotations

import asyncio
import io
import sys
from typing import Any

# Force UTF-8 output on Windows to handle any unicode characters.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from fastmcp import Client  # noqa: E402

# ---------------------------------------------------------------------------
# Helper – pretty-print tool results
# ---------------------------------------------------------------------------


def _banner(title: str) -> None:
    width = 60
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}")


def _print_result(label: str, result: Any) -> None:
    """Extract and print the text content from a CallToolResult."""
    print(f"\n[RESULT] {label}")
    # FastMCP CallToolResult exposes a .content list of TextContent items
    if hasattr(result, "content") and isinstance(result.content, list):
        for item in result.content:
            text = getattr(item, "text", str(item))
            print(text)
    else:
        print(result)


# ---------------------------------------------------------------------------
# Main test coroutine
# ---------------------------------------------------------------------------


async def run_tests() -> None:
    """
    Connect to the MCP server (in-process via FastMCP Client) and invoke each
    of the three tools with representative payloads, printing the results.
    """
    # Import the FastMCP server object from mcp_server to run in-process.
    # This avoids requiring a running HTTP server for the test.
    from mcp_server import mcp as server_instance  # noqa: PLC0415

    async with Client(server_instance) as client:

        # ------------------------------------------------------------------
        # 1. List discovered tools
        # ------------------------------------------------------------------
        _banner("Discovered Tools")
        tools = await client.list_tools()
        for tool in tools:
            print(f"  • {tool.name}: {tool.description or '(no description)'}")

        # ------------------------------------------------------------------
        # 2. Tool: check_availability – successful case
        # ------------------------------------------------------------------
        _banner("Tool: check_availability (London, 2026-07-10, 3 nights)")
        result = await client.call_tool(
            "check_availability",
            {
                    "branch": "London",
                    "arrival_date": "2026-07-10",
                    "nights": 3,
                },
        )
        _print_result("London availability (all room types, 3 nights)", result)

        # ------------------------------------------------------------------
        # 3. Tool: check_availability – filtered by room type
        # ------------------------------------------------------------------
        _banner("Tool: check_availability (Manchester, executive_suite filter)")
        result = await client.call_tool(
            "check_availability",
            {
                    "branch": "Manchester",
                    "arrival_date": "2026-07-10",
                    "nights": "2",
                    "room_type": "executive_suite",
                },
        )
        _print_result("Manchester – executive_suite only", result)

        # ------------------------------------------------------------------
        # 4. Tool: check_availability – unknown branch (error path)
        # ------------------------------------------------------------------
        _banner("Tool: check_availability (error: unknown branch)")
        result = await client.call_tool(
            "check_availability",
            {
                    "branch": "Bristol",
                    "arrival_date": "2026-07-10",
                    "nights": "1",
                },
        )
        _print_result("Unknown branch error response", result)
        result_text = result.content[0].text if hasattr(result, "content") and isinstance(result.content, list) else str(result)
        assert "ERROR:" in result_text, f"Expected ERROR: in result, but got: {result_text}"

        # ------------------------------------------------------------------
        # 5. Tool: create_booking – successful booking
        # ------------------------------------------------------------------
        _banner("Tool: create_booking (Edinburgh, standard_twin)")
        result = await client.call_tool(
            "create_booking",
            {
                    "guest_full_name": "Akhileshwar Reddy",
                    "branch": "Edinburgh",
                    "room_type": "standard_twin",
                    "arrival_date": "2026-07-10",
                    "nights": "2",
                    "guest_email": "a.reddy@university.ac.uk",
                },
        )
        _print_result("Edinburgh booking confirmation", result)

        # ------------------------------------------------------------------
        # 6. Tool: create_booking – sold-out room (London executive_suite 2026-07-11)
        # ------------------------------------------------------------------
        _banner("Tool: create_booking (error: sold-out room)")
        
        # London executive_suite has capacity 1. Book it once to exhaust inventory.
        await client.call_tool(
            "create_booking",
            {
                    "guest_full_name": "VIP Guest",
                    "branch": "London",
                    "room_type": "executive_suite",
                    "arrival_date": "2026-07-11",
                    "nights": "1",
                },
        )
        
        # Try to book it again, which should fail
        result = await client.call_tool(
            "create_booking",
            {
                    "guest_full_name": "Jane Smith",
                    "branch": "London",
                    "room_type": "executive_suite",
                    "arrival_date": "2026-07-11",
                    "nights": "1",
                },
        )
        _print_result("Sold-out room error response", result)
        result_text = result.content[0].text if hasattr(result, "content") and isinstance(result.content, list) else str(result)
        assert "ERROR:" in result_text, f"Expected ERROR: in result, but got: {result_text}"

        # ------------------------------------------------------------------
        # 7. Tool: search_faq – keyword match
        # ------------------------------------------------------------------
        _banner("Tool: search_faq (query: 'cancellation refund')")
        result = await client.call_tool(
            "search_faq",
            {
                    "query": "cancellation refund",
                    "max_results": 2,
                },
        )
        _print_result("FAQ results – cancellation / refund", result)

        # ------------------------------------------------------------------
        # 8. Tool: search_faq – pets query
        # ------------------------------------------------------------------
        _banner("Tool: search_faq (query: 'pets dog allowed')")
        result = await client.call_tool(
            "search_faq",
            {
                    "query": "pets dog allowed",
                    "max_results": 3,
                },
        )
        _print_result("FAQ results – pets / dogs", result)

        # ------------------------------------------------------------------
        # 9. Tool: search_faq – no match (error path)
        # ------------------------------------------------------------------
        _banner("Tool: search_faq (no match: 'swimming pool gym')")
        result = await client.call_tool(
            "search_faq",
            {
                    "query": "swimming pool gym",
                    "max_results": 3,
                },
        )
        _print_result("FAQ – no match fallback response", result)

    print(f"\n{'=' * 60}")
    print("  All test cases completed successfully.")
    print(f"{'=' * 60}\n")


# ---------------------------------------------------------------------------
# HTTP transport variant (requires running server on localhost:8000)
# ---------------------------------------------------------------------------
# Uncomment the block below and comment-out run_tests() to test over HTTP.
#
# async def run_tests_http() -> None:
#     from fastmcp import Client
#     from fastmcp.client.transports import StreamableHttpTransport
#
#     transport = StreamableHttpTransport("http://127.0.0.1:8000/mcp/")
#     async with Client(transport) as client:
#         tools = await client.list_tools()
#         for tool in tools:
#             print(f"  • {tool.name}")
#
#         result = await client.call_tool(
#             "check_availability",
#             {"branch": "London", "arrival_date": "2026-07-10", "nights": 1},
#         )
#         print(result)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(run_tests())
