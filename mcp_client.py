import os
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Streamlit Tornado 루프와 충돌하지 않는 전용 비동기 스레드 풀
def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)

def get_mcp_server_params():
    """운영체제 및 환경변수(LAW_OC)를 반영한 MCP 서버 실행 파라미터 반환"""
    env = os.environ.copy()
    law_oc = os.environ.get("LAW_OC") or os.environ.get("KOREAN_LAW_OPEN_API_KEY", "")
    if law_oc:
        env["LAW_OC"] = law_oc

    if os.name == "nt":
        # Windows 로컬 환경
        return StdioServerParameters(command="cmd", args=["/c", "korean-law-mcp"], env=env)
    else:
        # Linux / Streamlit Community Cloud 환경
        return StdioServerParameters(command="npx", args=["-y", "korean-law-mcp"], env=env)

def clean_schema(s):
    """Gemini API 형식에 맞게 JSON 스키마에서 비표준 키 제거"""
    if not isinstance(s, dict):
        return
    allowed_keys = {"type", "format", "description", "nullable", "enum", "properties", "required", "items"}
    keys_to_remove = [k for k in list(s.keys()) if k not in allowed_keys]
    for k in keys_to_remove:
        s.pop(k, None)
    if "properties" in s:
        for key in list(s["properties"].keys()):
            clean_schema(s["properties"][key])
    if "items" in s:
        clean_schema(s["items"])

async def fetch_mcp_tools_async(timeout_sec: float = 15.0):
    """MCP 서버에서 도구 목록을 조회하여 Gemini Function Declarations 규격으로 변환"""
    params = get_mcp_server_params()
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=timeout_sec)
                tools_resp = await asyncio.wait_for(session.list_tools(), timeout=timeout_sec)
                
                gemini_functions = []
                for t in tools_resp.tools:
                    schema = t.inputSchema.copy()
                    if "apiKey" in schema.get("properties", {}):
                        del schema["properties"]["apiKey"]
                    if "apiKey" in schema.get("required", []):
                        schema["required"].remove("apiKey")
                    clean_schema(schema)
                    gemini_functions.append({
                        "name": t.name,
                        "description": t.description,
                        "parameters": schema
                    })
                return gemini_functions
    except Exception as e:
        print(f"[MCP 도구 로드 오류]: {e}")
        return []

async def call_mcp_tool_async(tool_name: str, args: dict, timeout_sec: float = 25.0) -> str:
    """지정된 MCP 도구를 비동기 호출하고 결과를 텍스트로 반환"""
    params = get_mcp_server_params()
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=10.0)
                result = await asyncio.wait_for(session.call_tool(tool_name, args), timeout=timeout_sec)
                if result.content:
                    return "\n".join([c.text for c in result.content if hasattr(c, 'text')])
                return str(result)
    except asyncio.TimeoutError:
        return f"[오류: 법제처 API 응답 지연 (타임아웃 {timeout_sec}초 초과)]"
    except Exception as e:
        return f"[MCP 도구 실행 오류: {str(e)}]"
