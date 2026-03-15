"""End-to-end test: spawns the MCP server over stdio and exercises the protocol."""

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "notebooklm_mcp.server"],
    )

    print("=== Connecting to MCP server ===")
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Session initialized\n")

            # 1. List tools
            print("=== Listing tools ===")
            tools = await session.list_tools()
            tool_names = [t.name for t in tools.tools]
            print(f"Found {len(tool_names)} tools:")
            for name in sorted(tool_names):
                print(f"  - {name}")

            # 2. Check a tool schema
            print("\n=== Tool schema: chat_ask ===")
            chat_tool = next(t for t in tools.tools if t.name == "chat_ask")
            print(f"  Description: {chat_tool.description}")
            print(f"  Input schema: {json.dumps(chat_tool.inputSchema, indent=4)}")

            # 3. Try calling notebook_list (will fail without auth, but tests the call path)
            print("\n=== Calling notebook_list (expect auth error) ===")
            try:
                result = await session.call_tool("notebook_list", {})
                print(f"  Result: {result}")
            except Exception as e:
                print(f"  Error (expected): {type(e).__name__}: {e}")

            print("\n=== All protocol tests passed ===")


if __name__ == "__main__":
    asyncio.run(main())
