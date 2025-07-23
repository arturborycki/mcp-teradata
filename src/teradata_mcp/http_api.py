from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import AnyUrl, BaseModel
import json
import os
from typing import Optional, Dict, Any

from . import server

# Optional authentication setup
KEYCLOAK_ENABLED = os.getenv("KEYCLOAK_ENABLED", "false").lower() == "true"

# Placeholder for authentication function
async def verify_authentication(request: Request) -> Optional[Dict[str, Any]]:
    """Verify authentication if enabled"""
    if not KEYCLOAK_ENABLED:
        return None
    
    # Extract Bearer token from Authorization header
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = auth_header.split(" ")[1]
    
    # TODO: Implement actual Keycloak token verification
    # For now, just return a placeholder user info
    return {
        "sub": "user-id",
        "preferred_username": "authenticated-user",
        "realm_access": {"roles": ["data_analyst", "admin"]}
    }

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
async def mcp_sse(request_body: dict, request: Request):
    """
    Server-Sent Events endpoint for MCP-over-HTTP with optional authentication
    """
    # Verify authentication if enabled
    user_info = await verify_authentication(request)
    
    async def generate_sse_response():
        try:
            method = request_body.get("method")
            params = request_body.get("params", {})
            id_val = request_body.get("id", 1)
            
            # Handle MCP initialization - REQUIRED!
            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": id_val,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {},
                            "prompts": {},
                            "resources": {}
                        },
                        "serverInfo": {
                            "name": "teradata-mcp",
                            "version": "1.0.0"
                        }
                    }
                }
                
            # Handle different MCP methods
            elif method == "tools/list":
                result = await server.handle_list_tools()
                # Clean conversion of Tool objects
                tools_dict = []
                for tool in result:
                    try:
                        if hasattr(tool, 'model_dump'):
                            tool_data = tool.model_dump()
                        else:
                            tool_data = {
                                "name": getattr(tool, 'name', ''),
                                "description": getattr(tool, 'description', ''),
                                "inputSchema": getattr(tool, 'inputSchema', {})
                            }
                        tools_dict.append(tool_data)
                    except Exception as e:
                        # Skip problematic tools
                        continue
                        
                response = {
                    "jsonrpc": "2.0",
                    "id": id_val,
                    "result": {"tools": tools_dict}
                }
                
            elif method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments", {})
                result = await server.handle_tool_call(name, arguments)
                
                # Safely convert content to simple strings
                content_dict = []
                for item in result:
                    try:
                        if hasattr(item, 'text'):
                            # Clean the text content
                            text_content = str(item.text).strip()
                            content_dict.append({
                                "type": "text",
                                "text": text_content
                            })
                        else:
                            # Convert to string and clean
                            text_content = str(item).strip()
                            content_dict.append({
                                "type": "text",
                                "text": text_content
                            })
                    except Exception as e:
                        content_dict.append({
                            "type": "text",
                            "text": f"Error processing result: {str(e)}"
                        })
                        
                response = {
                    "jsonrpc": "2.0",
                    "id": id_val,
                    "result": {"content": content_dict}
                }
                
            elif method == "prompts/list":
                result = await server.handle_list_prompts()
                prompts_dict = []
                for prompt in result:
                    try:
                        if hasattr(prompt, 'model_dump'):
                            prompt_data = prompt.model_dump()
                        else:
                            prompt_data = {
                                "name": getattr(prompt, 'name', ''),
                                "description": getattr(prompt, 'description', ''),
                                "arguments": getattr(prompt, 'arguments', [])
                            }
                        prompts_dict.append(prompt_data)
                    except Exception as e:
                        continue
                        
                response = {
                    "jsonrpc": "2.0",
                    "id": id_val,
                    "result": {"prompts": prompts_dict}
                }
                
            elif method == "resources/list":
                result = await server.handle_list_resources()
                resources_dict = []
                for resource in result:
                    try:
                        if hasattr(resource, 'model_dump'):
                            resource_data = resource.model_dump()
                        else:
                            resource_data = {
                                "uri": str(getattr(resource, 'uri', '')),
                                "name": getattr(resource, 'name', ''),
                                "description": getattr(resource, 'description', ''),
                                "mimeType": getattr(resource, 'mimeType', 'text/plain')
                            }
                        resources_dict.append(resource_data)
                    except Exception as e:
                        continue
                        
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
            
            # Use json.dumps with proper error handling and ensure_ascii
            try:
                json_response = json.dumps(response, ensure_ascii=True, separators=(',', ':'))
                yield f"data: {json_response}\n\n"
            except (TypeError, ValueError) as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": id_val,
                    "error": {"code": -32603, "message": f"JSON serialization error: {str(e)}"}
                }
                json_error = json.dumps(error_response, ensure_ascii=True, separators=(',', ':'))
                yield f"data: {json_error}\n\n"
            
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": request.get("id", 1),
                "error": {"code": -32603, "message": f"Server error: {str(e)}"}
            }
            try:
                json_error = json.dumps(error_response, ensure_ascii=True, separators=(',', ':'))
                yield f"data: {json_error}\n\n"
            except:
                yield f"data: {{'jsonrpc': '2.0', 'id': 1, 'error': {{'code': -32603, 'message': 'Critical JSON error'}}}}\n\n"
    
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

# Authentication endpoint with X-Client-* headers
async def verify_client_credentials(request: Request) -> Optional[Dict[str, Any]]:
    """Verify client credentials from X-Client-* headers"""
    if not KEYCLOAK_ENABLED:
        return None
    
    client_id = request.headers.get("X-Client-ID", "").strip()
    client_secret = request.headers.get("X-Client-Secret", "").strip()
    
    if not client_id or not client_secret:
        raise HTTPException(status_code=401, detail="Client credentials required")
    
    # Verify against your expected client credentials
    expected_client_id = os.getenv("KEYCLOAK_CLIENT_ID", "mcp-teradata")
    expected_client_secret = os.getenv("KEYCLOAK_CLIENT_SECRET", "")
    
    if client_id != expected_client_id or client_secret != expected_client_secret:
        raise HTTPException(status_code=401, detail="Invalid client credentials")
    
    # Return service account user info
    return {
        "sub": "service-account-mcp-teradata",
        "preferred_username": "service-account",
        "realm_access": {"roles": ["admin", "data_analyst", "data_reader"]}
    }

@app.post("/auth/sse")
async def auth_sse(request_body: dict, request: Request):
    """
    Authentication-based SSE endpoint for MCP-over-HTTP
    Uses X-Client-ID and X-Client-Secret headers for authentication
    """
    # Verify client credentials
    user_info = await verify_client_credentials(request)
    
    async def generate_sse_response():
        try:
            method = request_body.get("method")
            params = request_body.get("params", {})
            id_val = request_body.get("id", 1)
            
            # Handle MCP initialization - REQUIRED!
            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": id_val,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {},
                            "prompts": {},
                            "resources": {}
                        },
                        "serverInfo": {
                            "name": "teradata-mcp",
                            "version": "1.0.0"
                        }
                    }
                }
                
            # Handle different MCP methods
            elif method == "tools/list":
                result = await server.handle_list_tools()
                # Clean conversion of Tool objects
                tools_dict = []
                for tool in result:
                    try:
                        if hasattr(tool, 'model_dump'):
                            tool_data = tool.model_dump()
                        else:
                            tool_data = {
                                "name": getattr(tool, 'name', ''),
                                "description": getattr(tool, 'description', ''),
                                "inputSchema": getattr(tool, 'inputSchema', {})
                            }
                        tools_dict.append(tool_data)
                    except Exception:
                        # Skip problematic tools
                        continue
                        
                response = {
                    "jsonrpc": "2.0",
                    "id": id_val,
                    "result": {"tools": tools_dict}
                }
                
            elif method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments", {})
                result = await server.handle_tool_call(name, arguments)
                
                # Safely convert content to simple strings
                content_dict = []
                for item in result:
                    try:
                        if hasattr(item, 'text'):
                            # Clean the text content
                            text_content = str(item.text).strip()
                            content_dict.append({
                                "type": "text",
                                "text": text_content
                            })
                        else:
                            # Convert to string and clean
                            text_content = str(item).strip()
                            content_dict.append({
                                "type": "text",
                                "text": text_content
                            })
                    except Exception as e:
                        content_dict.append({
                            "type": "text",
                            "text": f"Error processing result: {str(e)}"
                        })
                        
                response = {
                    "jsonrpc": "2.0",
                    "id": id_val,
                    "result": {"content": content_dict}
                }
                
            elif method == "prompts/list":
                result = await server.handle_list_prompts()
                prompts_dict = []
                for prompt in result:
                    try:
                        if hasattr(prompt, 'model_dump'):
                            prompt_data = prompt.model_dump()
                        else:
                            prompt_data = {
                                "name": getattr(prompt, 'name', ''),
                                "description": getattr(prompt, 'description', ''),
                                "arguments": getattr(prompt, 'arguments', [])
                            }
                        prompts_dict.append(prompt_data)
                    except Exception:
                        continue
                        
                response = {
                    "jsonrpc": "2.0",
                    "id": id_val,
                    "result": {"prompts": prompts_dict}
                }
                
            elif method == "resources/list":
                result = await server.handle_list_resources()
                resources_dict = []
                for resource in result:
                    try:
                        if hasattr(resource, 'model_dump'):
                            resource_data = resource.model_dump()
                        else:
                            resource_data = {
                                "uri": str(getattr(resource, 'uri', '')),
                                "name": getattr(resource, 'name', ''),
                                "description": getattr(resource, 'description', ''),
                                "mimeType": getattr(resource, 'mimeType', 'text/plain')
                            }
                        resources_dict.append(resource_data)
                    except Exception:
                        continue
                        
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
            
            # Use json.dumps with proper error handling and ensure_ascii
            try:
                json_response = json.dumps(response, ensure_ascii=True, separators=(',', ':'))
                yield f"data: {json_response}\n\n"
            except (TypeError, ValueError) as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": id_val,
                    "error": {"code": -32603, "message": f"JSON serialization error: {str(e)}"}
                }
                json_error = json.dumps(error_response, ensure_ascii=True, separators=(',', ':'))
                yield f"data: {json_error}\n\n"
            
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": request_body.get("id", 1),
                "error": {"code": -32603, "message": f"Server error: {str(e)}"}
            }
            try:
                json_error = json.dumps(error_response, ensure_ascii=True, separators=(',', ':'))
                yield f"data: {json_error}\n\n"
            except Exception:
                yield "data: {\"jsonrpc\": \"2.0\", \"id\": 1, \"error\": {\"code\": -32603, \"message\": \"Critical JSON error\"}}\n\n"
    
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