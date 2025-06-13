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

# Run your MCP server
CMD ["uv", "run", "uvicorn", "teradata_mcp.http_api:app", "--host", "0.0.0.0", "--port", "8000"]