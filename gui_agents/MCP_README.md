# GUI Agent MCP Server

This document describes the MCP (Model Context Protocol) server for GUI Agent automation.

## Overview

The MCP server provides a standardized interface for GUI automation using the Lybic sandbox infrastructure. It exposes three main tools:

1. **create_sandbox** - Create a new sandbox environment
2. **get_sandbox_screenshot** - Capture screenshots from sandboxes
3. **execute_instruction** - Execute natural language instructions with real-time streaming

## Installation

The MCP server is included in the gui-agents package. Install with MCP support:

```bash
pip install lybic-guiagents[mcp]
```

Or install from source:

```bash
git clone https://github.com/lybic/agent
cd agent
pip install -e .
```

## Configuration

### Environment Variables

Create a `.env` file in the `gui_agents/` directory or set these environment variables:

```bash
# Lybic Cloud Configuration (required)
LYBIC_API_KEY=your_lybic_api_key
LYBIC_ORG_ID=your_lybic_org_id
LYBIC_API_ENDPOINT=https://api.lybic.cn/  # optional, defaults to this value

# LLM Provider Configuration (optional, can be passed per request)
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key

# Server Configuration (optional)
MCP_PORT=8000  # default port
MCP_HOST=0.0.0.0  # default host
LOG_LEVEL=INFO  # logging level
```

### Access Tokens

Create an `access_tokens.txt` file in the `gui_agents/` directory with valid Bearer tokens (one per line):

```
token_abc123xyz
another_token_456
# Lines starting with # are comments
```

## Usage

### Starting the Server

```bash
# Using the entry point
lybic-guiagent-mcp

# Or directly with Python
python -m gui_agents.mcp_app

# With custom port
MCP_PORT=8080 lybic-guiagent-mcp
```

The server will start on `http://0.0.0.0:8000` by default.

### API Endpoints

- **POST /mcp_stream** - MCP Streamable HTTP endpoint (requires Bearer token authentication)
- **GET /health** - Health check endpoint
- **GET /** - Server information and available tools

### Authentication

All requests to the MCP endpoints require Bearer token authentication:

```bash
curl -H "Authorization: Bearer your_token" http://localhost:8000/health
```

## MCP Tools

### 1. create_sandbox

Create a new sandbox environment for GUI automation.

**Parameters:**
- `apikey` (string, optional) - Lybic API key (uses LYBIC_API_KEY env var if not provided)
- `orgid` (string, optional) - Lybic Organization ID (uses LYBIC_ORG_ID env var if not provided)
- `shape` (string, optional) - Sandbox configuration, default: "beijing-2c-4g-cpu"

**Returns:**
- Sandbox ID and metadata

**Example:**
```json
{
  "tool": "create_sandbox",
  "arguments": {
    "shape": "beijing-2c-4g-cpu"
  }
}
```

### 2. get_sandbox_screenshot

Capture a screenshot from an existing sandbox.

**Parameters:**
- `sandbox_id` (string, required) - Sandbox ID from create_sandbox
- `apikey` (string, optional) - Lybic API key
- `orgid` (string, optional) - Lybic Organization ID

**Returns:**
- Screenshot file path and dimensions

**Example:**
```json
{
  "tool": "get_sandbox_screenshot",
  "arguments": {
    "sandbox_id": "SBX-01234567890"
  }
}
```

### 3. execute_instruction

Execute a natural language instruction in a sandbox with real-time streaming.

**Parameters:**
- `instruction` (string, required) - Natural language task description
- `sandbox_id` (string, optional) - Use existing sandbox or create new one
- `apikey` (string, optional) - Lybic API key
- `orgid` (string, optional) - Lybic Organization ID
- `mode` (string, optional) - Agent mode: "normal" or "fast" (default: "fast")
- `max_steps` (integer, optional) - Maximum execution steps (default: 50)
- `llm_provider` (string, optional) - LLM provider (e.g., "openai", "anthropic")
- `llm_model` (string, optional) - LLM model name (e.g., "gpt-4", "claude-3-sonnet")
- `llm_api_key` (string, optional) - API key for LLM provider
- `llm_endpoint` (string, optional) - Custom LLM endpoint URL

**Returns:**
- Execution results with statistics (steps, tokens, cost, duration)

**Example:**
```json
{
  "tool": "execute_instruction",
  "arguments": {
    "instruction": "Open calculator and compute 123 + 456",
    "mode": "fast",
    "max_steps": 50,
    "llm_provider": "openai",
    "llm_model": "gpt-4"
  }
}
```

## Example Client Usage

### Using MCP SDK

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Create MCP client
server_params = StdioServerParameters(
    command="lybic-guiagent-mcp",
    env={"LYBIC_API_KEY": "your_key", "LYBIC_ORG_ID": "your_org"}
)

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        # Initialize session
        await session.initialize()
        
        # Create sandbox
        result = await session.call_tool("create_sandbox", {
            "shape": "beijing-2c-4g-cpu"
        })
        sandbox_id = extract_sandbox_id(result)
        
        # Execute instruction
        result = await session.call_tool("execute_instruction", {
            "instruction": "Open notepad and type 'Hello World'",
            "sandbox_id": sandbox_id,
            "mode": "fast"
        })
        print(result)
```

### Using HTTP Directly

```python
import httpx

BASE_URL = "http://localhost:8000"
TOKEN = "your_bearer_token"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# Health check
response = httpx.get(f"{BASE_URL}/health", headers=headers)
print(response.json())

# MCP communication via Streamable HTTP
# (Requires a client that can handle streaming responses)
```

## Agent Modes

### Fast Mode (Recommended)
- Faster execution with direct action generation
- Lower token consumption
- Best for straightforward tasks
- Example: `"mode": "fast"`

### Normal Mode
- Full reasoning with hierarchical planning
- DAG modeling and memory systems
- Better for complex multi-step tasks
- Example: `"mode": "normal"`

## LLM Configuration

You can customize the LLM provider per request:

```json
{
  "tool": "execute_instruction",
  "arguments": {
    "instruction": "Your task here",
    "llm_provider": "anthropic",
    "llm_model": "claude-3-sonnet-20240229",
    "llm_api_key": "your_anthropic_key"
  }
}
```

Supported providers:
- **openai** - GPT-4, GPT-3.5, etc.
- **anthropic** - Claude models
- **google** - Gemini models
- And others configured in your tools_config

## Security

1. **Bearer Token Authentication**: All requests require a valid Bearer token from `access_tokens.txt`
2. **Environment Isolation**: Each task runs in a separate sandbox environment
3. **API Key Management**: API keys can be provided per-request or via environment variables

## Troubleshooting

### Connection Issues

```bash
# Check if server is running
curl http://localhost:8000/health

# Check authentication
curl -H "Authorization: Bearer your_token" http://localhost:8000/health
```

### Missing Dependencies

```bash
# Install all dependencies
pip install -e ".[mcp]"

# Or install specific packages
pip install mcp fastapi uvicorn
```

### Environment Variables

Verify your `.env` file is properly loaded:

```python
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('LYBIC_API_KEY'))"
```

## Development

### Running in Development Mode

```bash
# With auto-reload
uvicorn gui_agents.mcp_app:app --reload --port 8000

# With debug logging
LOG_LEVEL=DEBUG lybic-guiagent-mcp
```

### Adding New Tools

Edit `gui_agents/mcp_app.py`:

1. Add tool definition in `@mcp_server.list_tools()`
2. Implement handler function
3. Register in `@mcp_server.call_tool()`

## Performance Considerations

- **Sandbox Creation**: Creating a new sandbox takes ~30-60 seconds
- **Reuse Sandboxes**: Pass `sandbox_id` to reuse existing sandboxes
- **Fast Mode**: Use fast mode for better performance (50-70% faster)
- **Concurrent Tasks**: Multiple tasks can run in parallel with different sandboxes

## Monitoring

The server provides metrics through the `/health` endpoint:

```json
{
  "status": "healthy",
  "server": "gui-agent-mcp-server",
  "active_sandboxes": 2,
  "active_tasks": 1
}
```

## Related Documentation

- [Main README](../README.md) - General GUI Agent documentation
- [gRPC Server](./grpc_app.py) - Alternative gRPC interface
- [CLI Application](./cli_app.py) - Command-line interface
- [Lybic Documentation](https://docs.lybic.com/) - Sandbox platform docs

## License

Apache 2.0 - See [LICENSE](../LICENSE) for details.
