from fastapi import FastAPI, HTTPException, Request
from pydantic import AnyUrl
import asyncio
import os

from . import server

app = FastAPI()

#@app.on_event("startup")
#async def startup_event():
#    # Ensure the MCP server is initialized
#    if not hasattr(server, "server"):
#        await server.main()

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