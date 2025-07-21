from fastapi import FastAPI, HTTPException, Request
from pydantic import AnyUrl, BaseModel
import asyncio
import os
from typing import Optional, Dict, Any

from . import server

app = FastAPI()

# Pydantic models for request/response
class CallRequest(BaseModel):
    method: str  # "tools/call", "prompts/get", "resources/read", etc.
    params: Optional[Dict[str, Any]] = None

@app.get("/")
async def root():
    return {"message": "Teradata MCP Server is running", "status": "ok"}

@app.get("/prompts")
async def list_prompts():
    return await server.handle_list_prompts()

@app.post("/prompt/{name}")
async def get_prompt(name: str, arguments: dict = None):
    try:
        return await server.handle_get_prompt(name, arguments)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/resources")
async def list_resources():
    return await server.handle_list_resources()

@app.get("/resource/")
async def read_resource(uri: AnyUrl):
    try:
        return await server.handle_read_resource(uri)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/tools")
async def list_tools():
    return await server.handle_list_tools()

@app.post("/tool/{name}")
async def call_tool(name: str, arguments: dict = None):
    try:
        return await server.handle_tool_call(name, arguments)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# NEW: Generic /call endpoint
@app.post("/call")
async def call_mcp(request: CallRequest):
    """
    Generic endpoint to handle any MCP operation
    Examples:
    - {"method": "tools/call", "params": {"name": "query", "arguments": {"query": "SELECT 1"}}}
    - {"method": "tools/list", "params": {}}
    - {"method": "prompts/get", "params": {"name": "Analyze_table", "arguments": {"database": "vs", "table": "test"}}}
    - {"method": "resources/list", "params": {}}
    - {"method": "resources/read", "params": {"uri": "teradata://table/test"}}
    """
    try:
        method = request.method
        params = request.params or {}
        
        if method == "tools/list":
            return await server.handle_list_tools()
            
        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments")
            if not name:
                raise HTTPException(status_code=400, detail="Tool name is required")
            return await server.handle_tool_call(name, arguments)
            
        elif method == "prompts/list":
            return await server.handle_list_prompts()
            
        elif method == "prompts/get":
            name = params.get("name")
            arguments = params.get("arguments")
            if not name:
                raise HTTPException(status_code=400, detail="Prompt name is required")
            return await server.handle_get_prompt(name, arguments)
            
        elif method == "resources/list":
            return await server.handle_list_resources()
            
        elif method == "resources/read":
            uri = params.get("uri")
            if not uri:
                raise HTTPException(status_code=400, detail="Resource URI is required")
            return await server.handle_read_resource(AnyUrl(uri))
            
        else:
            raise HTTPException(status_code=400, detail=f"Unknown method: {method}")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))