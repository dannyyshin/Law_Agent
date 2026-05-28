import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import json

async def main():
    # korean-law-mcp is the command, it is installed globally via npm
    server_params = StdioServerParameters(
        command="cmd",
        args=["/c", "korean-law-mcp"],
        env=None
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # List tools
                tools = await session.list_tools()
                print("Available tools:")
                for tool in tools.tools:
                    print(f"- {tool.name}: {tool.description}")
                    
                # Call a tool
                # result = await session.call_tool("search_law", {"query": "민법"})
                # print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
