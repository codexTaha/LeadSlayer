from __future__ import annotations

import os
import sys
from pathlib import Path

from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.models.schemas import MCPStatusResponse

BACKEND_DIR = Path(__file__).resolve().parents[2]


def build_mcp_server_params() -> StdioServerParameters:
    env = dict(os.environ)
    existing_pp = env.get("PYTHONPATH", "")
    backend_str = str(BACKEND_DIR)
    env["PYTHONPATH"] = (
        f"{backend_str}{os.pathsep}{existing_pp}" if existing_pp else backend_str
    )
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_server"],
        cwd=backend_str,
        env=env,
    )


def build_adk_mcp_toolset(timeout: float = 15.0) -> McpToolset:
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=build_mcp_server_params(),
            timeout=timeout,
        )
    )


async def inspect_mcp_server() -> MCPStatusResponse:
    """Connects over stdio to LeadSlayer's MCP server and verifies live tool discovery."""
    params = build_mcp_server_params()
    try:
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                names = [t.name for t in (tools_result.tools or [])]
                return MCPStatusResponse(
                    connected=len(names) > 0,
                    server_name="leadslayer-ops-mcp",
                    transport="stdio",
                    tools=names,
                )
    except Exception as exc:
        return MCPStatusResponse(
            connected=False,
            server_name="leadslayer-ops-mcp",
            transport="stdio",
            tools=[],
            error=str(exc)[:240],
        )
