"""
NBA MCP Server — exposes NBA tools to Hermes Agent via the Model Context Protocol.

Hermes Agent has native MCP support. Add this to ~/.hermes/config.yaml:

    mcp_servers:
      nba-tools:
        command: python
        args: ["mcp_server.py"]
        env:
          BALLDONTLIE_API_KEY: "${BALLDONTLIE_API_KEY}"

Then start Hermes normally — it will spawn this process and connect automatically.
"""

import inspect
import json
import sys
import os
import asyncio
from typing import Any

# MCP SDK — installed via: pip install mcp
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from tools import nba_tools, prediction_engine

app = Server("nba-tools")

# ── Load schemas ──────────────────────────────────────────────────────────────

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "tools", "schemas.json")
with open(_SCHEMA_PATH) as f:
    _SCHEMAS = json.load(f)

# ── Tool dispatcher ───────────────────────────────────────────────────────────

_TOOL_MAP: dict[str, Any] = {}
for _mod in (nba_tools, prediction_engine):
    for _name, _fn in inspect.getmembers(_mod, inspect.isfunction):
        _TOOL_MAP[_name] = _fn


def _dispatch(name: str, arguments: dict) -> Any:
    fn = _TOOL_MAP.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(**arguments)
    except Exception as exc:
        return {"error": str(exc)}


# ── MCP handlers ──────────────────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    tools = []
    for schema in _SCHEMAS:
        fn = schema["function"]
        tools.append(types.Tool(
            name=fn["name"],
            description=fn["description"],
            inputSchema=fn["parameters"],
        ))
    return tools


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    result = _dispatch(name, arguments)
    return [types.TextContent(
        type="text",
        text=json.dumps(result, default=str, indent=2),
    )]


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
