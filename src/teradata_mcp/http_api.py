from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import AnyUrl, BaseModel
import asyncio
import json
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

@app.get("/call")
async def call_mcp_get():
    """Simple GET version that returns available methods"""
    return {
        "message": "Use POST to call MCP methods",
        "available_methods": [
            "tools/list",
            "tools/call", 
            "prompts/list",
            "prompts/get",
            "resources/list", 
            "resources/read"
        ],
        "example": {
            "method": "tools/list",
            "params": {}
        }
    }

# NEW: Generic /call endpoint
@app.post("/call")
async def call_mcp_post(request: CallRequest):
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

# Add these endpoints for MCP compatibility
@app.post("/mcp")
async def mcp_jsonrpc(request: dict):
    """
    MCP JSON-RPC compatible endpoint
    """
    try:
        method = request.get("method")
        params = request.get("params", {})
        id_val = request.get("id", 1)
        
        if method == "tools/list":
            result = await server.handle_list_tools()
            return {
                "jsonrpc": "2.0",
                "id": id_val,
                "result": {"tools": result}
            }
            
        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments")
            result = await server.handle_tool_call(name, arguments)
            return {
                "jsonrpc": "2.0", 
                "id": id_val,
                "result": {"content": result}
            }
            
        elif method == "prompts/list":
            result = await server.handle_list_prompts()
            return {
                "jsonrpc": "2.0",
                "id": id_val, 
                "result": {"prompts": result}
            }
            
        elif method == "resources/list":
            result = await server.handle_list_resources()
            return {
                "jsonrpc": "2.0",
                "id": id_val,
                "result": {"resources": result}
            }
            
        else:
            return {
                "jsonrpc": "2.0",
                "id": id_val,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            }
            
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": request.get("id", 1),
            "error": {"code": -32603, "message": str(e)}
        }

# Alternative: Direct tools endpoint that Flowise might expect
@app.get("/mcp/tools")
async def get_mcp_tools():
    """Return tools in MCP format for Flowise"""
    tools = await server.handle_list_tools()
    return {"tools": tools}

@app.post("/mcp/tools/call")
async def call_mcp_tool(request: dict):
    """Call a tool in MCP format"""
    try:
        name = request.get("name")
        arguments = request.get("arguments", {})
        result = await server.handle_tool_call(name, arguments)
        return {"content": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sse")
async def mcp_sse(request: dict):
    """
    Server-Sent Events endpoint for MCP-over-HTTP (Flowise compatible)
    """
    async def generate_sse_response():
        try:
            method = request.get("method")
            params = request.get("params", {})
            id_val = request.get("id", 1)
            
            # Handle different MCP methods
            if method == "tools/list":
                result = await server.handle_list_tools()
                # Convert Tool objects to dictionaries
                tools_dict = [tool.model_dump() if hasattr(tool, 'model_dump') else tool.__dict__ for tool in result]
                response = {
                    "jsonrpc": "2.0",
                    "id": id_val,
                    "result": {"tools": tools_dict}
                }
                
            elif method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments", {})
                result = await server.handle_tool_call(name, arguments)
                # Convert TextContent objects to dictionaries
                content_dict = [item.model_dump() if hasattr(item, 'model_dump') else item.__dict__ for item in result]
                response = {
                    "jsonrpc": "2.0",
                    "id": id_val,
                    "result": {"content": content_dict}
                }
                
            elif method == "prompts/list":
                result = await server.handle_list_prompts()
                # Convert Prompt objects to dictionaries
                prompts_dict = [prompt.model_dump() if hasattr(prompt, 'model_dump') else prompt.__dict__ for prompt in result]
                response = {
                    "jsonrpc": "2.0",
                    "id": id_val,
                    "result": {"prompts": prompts_dict}
                }
                
            elif method == "resources/list":
                result = await server.handle_list_resources()
                # Convert Resource objects to dictionaries
                resources_dict = [resource.model_dump() if hasattr(resource, 'model_dump') else resource.__dict__ for resource in result]
                response = {
                    "jsonrpc": "2.0",
                    "id": id_val,
                    "result": {"resources": resources_dict}
                }
                
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": id_val,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }
            
            # Send SSE formatted response
            yield f"data: {json.dumps(response)}\n\n"
            
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": request.get("id", 1),
                "error": {"code": -32603, "message": str(e)}
            }
            yield f"data: {json.dumps(error_response)}\n\n"
    
    return StreamingResponse(
        generate_sse_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

# Alternative GET-based SSE for tools discovery
@app.get("/sse")  
async def mcp_sse_get():
    """
    SSE endpoint for discovering available tools (GET request)
    """
    async def generate_tools_sse():
        try:
            tools = await server.handle_list_tools()
            # Convert Tool objects to dictionaries
            tools_dict = [tool.model_dump() if hasattr(tool, 'model_dump') else tool.__dict__ for tool in tools]
            response = {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"tools": tools_dict}
            }
            yield f"data: {json.dumps(response)}\n\n"
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0", 
                "id": 1,
                "error": {"code": -32603, "message": str(e)}
            }
            yield f"data: {json.dumps(error_response)}\n\n"
    
    return StreamingResponse(
        generate_tools_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )