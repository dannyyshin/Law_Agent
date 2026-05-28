import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import json

async def main():
    server_params = StdioServerParameters(
        command="cmd",
        args=["/c", "korean-law-mcp"],
        env=None
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_response = await session.list_tools()
            tools = [{"name": t.name, "description": t.description, "inputSchema": t.inputSchema} for t in tools_response.tools]
            with open("mcp_tools.json", "w", encoding="utf-8") as f:
                json.dump(tools, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
