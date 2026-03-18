import asyncio
import json
from langchain_core.tools import tool
from pydantic import BaseModel, Field

class MockAsyncSession:
    pass

@tool
async def tool_lookup_route(query: str, session: MockAsyncSession = None, client_id: int = None):
    """
    Look up route.
    """
    return "ok"

@tool
async def tool_lookup_route_kwargs(query: str, **kwargs):
    """
    Look up route.
    """
    return "ok"

class ArgSchema(BaseModel):
    query: str = Field(description="Query")

@tool(args_schema=ArgSchema)
async def tool_lookup_route_pydantic(query: str, session: MockAsyncSession = None, client_id: int = None):
    """
    Look up route.
    """
    return "ok"

try:
    print("Default Tool:")
    print(tool_lookup_route.args_schema.schema())
except Exception as e:
    print("Error default:", type(e))

try:
    print("Kwargs Tool:")
    print(tool_lookup_route_kwargs.args_schema.schema())
except Exception as e:
    print("Error kwargs:", type(e))

try:
    print("Pydantic Tool:")
    print(tool_lookup_route_pydantic.args_schema.schema())
except Exception as e:
    print("Error pydantic:", type(e))
    
async def run():
    print("Invoke Kwargs:", await tool_lookup_route_kwargs.ainvoke({"query": "hi", "session": "test"}))
    try:
        print("Invoke Pydantic:", await tool_lookup_route_pydantic.ainvoke({"query": "hi", "session": "test"}))
    except Exception as e:
        print("Error Invoke Pydantic:", e)

asyncio.run(run())
