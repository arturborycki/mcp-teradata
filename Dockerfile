FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy uv configuration files
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
# Install dependencies
RUN uv sync --frozen

# Copy your MCP server code
#RUN pip install uvicorn teradatasql pyyaml pydantic mcp fastapi

# Expose the port your MCP server will run on
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app/src
ENV UV_SYSTEM_PYTHON=1
ENV MCP_TRANSPORT=streamable-http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
ENV MCP_PATH=/mcp/

# Run your MCP server
CMD ["uv", "run", "python", "-m", "teradata_mcp.server"]