#!/usr/bin/env python3
"""
MCP (Model Context Protocol) Server for GUI Agent

This server provides an MCP interface with Streamable HTTP endpoint to support remote calls
for GUI automation tasks. It implements Bearer Token authentication and exposes tools for:
- Creating sandboxes
- Getting sandbox screenshots  
- Executing agent instructions with real-time streaming
"""
import contextlib
import functools
import os
import sys
import logging
import asyncio
import datetime
from pathlib import Path
from typing import Optional, Any, Dict, AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from mcp.server import Server
from mcp import types
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.types import Scope, Send, Receive

# Load environment variables
env_path = Path(os.path.dirname(os.path.abspath(__file__))) / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    parent_env_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / '.env'
    if parent_env_path.exists():
        load_dotenv(dotenv_path=parent_env_path)

# Import agent components
import uvicorn

from lybic import LybicClient, LybicAuth, Sandbox

from gui_agents.agents.agent_s import AgentS2, AgentSFast, load_config
from gui_agents.agents.hardware_interface import HardwareInterface
from gui_agents.store.registry import Registry
from gui_agents.agents.global_state import GlobalState
from gui_agents.utils.analyze_display import analyze_display_json
import gui_agents.cli_app as cli_app

# Setup logging
logger = logging.getLogger(__name__)
level = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=level,
    format='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

# Get script directory
SCRIPT_DIR = Path(__file__).parent
ACCESS_TOKENS_FILE = SCRIPT_DIR / "access_tokens.txt"

# Store for active sandboxes (for tracking and monitoring)
active_sandboxes: Dict[str, Dict[str, Any]] = {}
active_tasks: set = set()


@functools.lru_cache(maxsize=None)
def load_access_tokens() -> set:
    """Load valid access tokens from access_tokens.txt"""
    tokens = set()
    if ACCESS_TOKENS_FILE.exists():
        with open(ACCESS_TOKENS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith('#'):
                    tokens.add(line)
    return tokens


def verify_bearer_token(authorization: Optional[str]) -> bool:
    """Verify Bearer token from Authorization header"""
    if not authorization:
        return False
    
    # Check if it starts with "Bearer "
    if not authorization.startswith("Bearer "):
        return False
    
    # Extract token
    token = authorization[7:]  # Remove "Bearer " prefix
    
    # Load valid tokens
    valid_tokens = load_access_tokens()
    
    return token in valid_tokens


async def authenticate_request(request: Request):
    """Middleware to authenticate requests"""
    authorization = request.headers.get("Authorization")
    if not verify_bearer_token(authorization):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_lybic_auth(apikey: Optional[str] = None, orgid: Optional[str] = None) -> LybicAuth:
    """Get Lybic authentication, using parameters or environment variables"""
    api_key = apikey or os.environ.get("LYBIC_API_KEY")
    org_id = orgid or os.environ.get("LYBIC_ORG_ID")

    if not api_key or not org_id:
        raise ValueError("Lybic API key and Org ID are required (provide as parameters or set LYBIC_API_KEY and LYBIC_ORG_ID environment variables)")

    return LybicAuth(
        org_id=org_id,
        api_key=api_key
    )


# Create MCP server
mcp_server = Server("gui-agent-mcp-server")


@mcp_server.list_tools()
async def list_tools() -> list[types.Tool]:
    """List available tools"""
    return [
        types.Tool(
            name="create_sandbox",
            description="Create a new sandbox environment for GUI automation. Returns sandbox ID that can be used for subsequent operations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "apikey": {
                        "type": "string",
                        "description": "Lybic API key (optional, will use LYBIC_API_KEY env var if not provided)"
                    },
                    "orgid": {
                        "type": "string",
                        "description": "Lybic Organization ID (optional, will use LYBIC_ORG_ID env var if not provided)"
                    },
                    "shape": {
                        "type": "string",
                        "description": "Sandbox shape/configuration (default: 'beijing-2c-4g-cpu')",
                        "default": "beijing-2c-4g-cpu"
                    }
                }
            }
        ),
        types.Tool(
            name="get_sandbox_screenshot",
            description="Get a screenshot from a sandbox environment",
            inputSchema={
                "type": "object",
                "properties": {
                    "sandbox_id": {
                        "type": "string",
                        "description": "Sandbox ID returned from create_sandbox"
                    },
                    "apikey": {
                        "type": "string",
                        "description": "Lybic API key (optional, will use LYBIC_API_KEY env var if not provided)"
                    },
                    "orgid": {
                        "type": "string",
                        "description": "Lybic Organization ID (optional, will use LYBIC_ORG_ID env var if not provided)"
                    }
                },
                "required": ["sandbox_id"]
            }
        ),
        types.Tool(
            name="execute_instruction",
            description="Execute an agent instruction in a sandbox with real-time streaming of results. This is the main tool for running GUI automation tasks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "instruction": {
                        "type": "string",
                        "description": "Natural language instruction for the agent to execute"
                    },
                    "sandbox_id": {
                        "type": "string",
                        "description": "Sandbox ID to execute in (optional, will create new sandbox if not provided)"
                    },
                    "apikey": {
                        "type": "string",
                        "description": "Lybic API key (optional, will use LYBIC_API_KEY env var if not provided)"
                    },
                    "orgid": {
                        "type": "string",
                        "description": "Lybic Organization ID (optional, will use LYBIC_ORG_ID env var if not provided)"
                    },
                    "mode": {
                        "type": "string",
                        "description": "Agent mode: 'normal' for full reasoning or 'fast' for quicker execution (default: 'fast')",
                        "enum": ["normal", "fast"],
                        "default": "fast"
                    },
                    "max_steps": {
                        "type": "integer",
                        "description": "Maximum number of steps to execute (default: 50)",
                        "default": 50
                    },
                    "llm_provider": {
                        "type": "string",
                        "description": "LLM provider to use (e.g., 'openai', 'anthropic', 'google', 'doubao', 'qwen')"
                    },
                    "llm_model": {
                        "type": "string",
                        "description": "LLM model name (e.g., 'gpt-4', 'claude-3-sonnet')"
                    },
                    "llm_api_key": {
                        "type": "string",
                        "description": "API key for the LLM provider"
                    },
                    "llm_endpoint": {
                        "type": "string",
                        "description": "Custom endpoint URL for the LLM provider"
                    }
                },
                "required": ["instruction"]
            }
        )
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[types.ContentBlock]:
    """Handle tool calls"""
    try:
        if name == "create_sandbox":
            return await handle_create_sandbox(arguments)
        elif name == "get_sandbox_screenshot":
            return await handle_get_sandbox_screenshot(arguments)
        elif name == "execute_instruction":
            return await handle_execute_instruction(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
    except Exception as e:
        logger.error(f"Error in tool '{name}': {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


async def handle_create_sandbox(arguments: dict) -> list[types.TextContent]:
    """Create a new sandbox"""
    apikey = arguments.get("apikey")
    orgid = arguments.get("orgid")
    shape = arguments.get("shape", "beijing-2c-4g-cpu")
    
    try:
        lybic_auth = get_lybic_auth(apikey, orgid)
        lybic_client = LybicClient(lybic_auth)
        sandbox_service = Sandbox(lybic_client)

        # Create sandbox
        logger.info(f"Creating sandbox with shape: {shape}")
        result = await sandbox_service.create(shape=shape)
        sandbox = await sandbox_service.get(result.id)
        await lybic_client.close()
        
        # Store sandbox info
        sandbox_info = {
            "id": sandbox.sandbox.id,
            "shape": shape,
            "os": str(sandbox.sandbox.shape.os),
            "created_at": datetime.datetime.now().isoformat()
        }
        active_sandboxes[sandbox.sandbox.id] = sandbox_info
        
        logger.info(f"Created sandbox: {sandbox.sandbox.id}")
        
        return [types.TextContent(
            type="text",
            text=f"Sandbox created successfully!\n\nSandbox ID: {sandbox.sandbox.id}\nOS: {sandbox_info['os']}\nShape: {shape}\n\nUse this sandbox_id for subsequent operations."
        )]
    except Exception as e:
        logger.error(f"Failed to create sandbox: {e}", exc_info=True)
        return [
            types.TextContent(
                type="text",
                text=f"Error creating sandbox: {str(e)}"
            )
        ]


async def handle_get_sandbox_screenshot(arguments: dict) -> list[types.ContentBlock]:
    """Get screenshot from sandbox"""
    sandbox_id = arguments["sandbox_id"]
    apikey = arguments.get("apikey")
    orgid = arguments.get("orgid")

    lybic_auth = get_lybic_auth(apikey, orgid)

    async with LybicClient(lybic_auth) as lybic_client:
        sandbox_service = Sandbox(lybic_client)
        try:
            screenshot = await sandbox_service.get_screenshot_base64(sandbox_id)
            return [
                types.TextContent(
                    type="text",
                    text=f"Success get screenshot from sandbox {sandbox_id}:"
                ),
                types.ImageContent(
                    type="image",
                    data=screenshot,
                    mimeType="image/webp"
            ),
            ]
        except Exception as e:
            logger.error(f"Failed to get screenshot: {e}", exc_info=True)
            raise

async def handle_execute_instruction(arguments: dict) -> list[types.TextContent]:
    """Execute agent instruction with streaming"""
    instruction = arguments["instruction"]
    sandbox_id = arguments.get("sandbox_id")
    apikey = arguments.get("apikey")
    orgid = arguments.get("orgid")
    mode = arguments.get("mode", "fast")
    max_steps = arguments.get("max_steps", 50)

    # LLM configuration
    llm_provider = arguments.get("llm_provider")
    llm_model = arguments.get("llm_model")
    llm_api_key = arguments.get("llm_api_key")
    llm_endpoint = arguments.get("llm_endpoint")

    task_id = None
    try:
        lybic_auth = get_lybic_auth(apikey, orgid)

        # Create or get sandbox
        if not sandbox_id:
            logger.info("No sandbox_id provided, creating new sandbox")
            async with LybicClient(lybic_auth) as lybic_client:
                sandbox_service = Sandbox(lybic_client)
                result = await sandbox_service.create(shape="beijing-2c-4g-cpu")
                sandbox = await sandbox_service.get(result.id)
                sandbox_id = sandbox.sandbox.id
                # Store sandbox info
                sandbox_info = {
                    "id": sandbox.sandbox.id,
                    "shape": "beijing-2c-4g-cpu",
                    "os": str(sandbox.sandbox.shape.os),
                    "created_at": datetime.datetime.now().isoformat()
                }
                active_sandboxes[sandbox.sandbox.id] = sandbox_info
            logger.info(f"Created new sandbox: {sandbox_id}")

        # Setup task
        task_id = f"mcp_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        active_tasks.add(task_id)
        log_dir = Path("runtime")
        timestamp_dir = log_dir / f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{task_id[:8]}"
        cache_dir = timestamp_dir / "cache" / "screens"
        state_dir = timestamp_dir / "state"

        cache_dir.mkdir(parents=True, exist_ok=True)
        state_dir.mkdir(parents=True, exist_ok=True)

        # Create task-specific registry
        task_registry = Registry()
        global_state = GlobalState(
            screenshot_dir=str(cache_dir),
            tu_path=str(state_dir / "tu.json"),
            search_query_path=str(state_dir / "search_query.json"),
            completed_subtasks_path=str(state_dir / "completed_subtasks.json"),
            failed_subtasks_path=str(state_dir / "failed_subtasks.json"),
            remaining_subtasks_path=str(state_dir / "remaining_subtasks.json"),
            termination_flag_path=str(state_dir / "termination_flag.json"),
            running_state_path=str(state_dir / "running_state.json"),
            display_info_path=str(timestamp_dir / "display.json"),
            agent_log_path=str(timestamp_dir / "agent_log.json")
        )

        task_registry.register_instance("GlobalStateStore", global_state)
        Registry.set_task_registry(task_id, task_registry)

        # Create agent with custom LLM config if provided
        tools_config, tools_dict = load_config()

        if llm_provider and llm_model:
            logger.info(f"Applying custom LLM configuration: {llm_provider}/{llm_model}")
            for tool_name in tools_dict:
                if tool_name not in ['embedding', 'grounding']: # General visual model
                    tools_dict[tool_name]['provider'] = llm_provider
                    tools_dict[tool_name]['model_name'] = llm_model
                    tools_dict[tool_name]['model'] = llm_model
                    if llm_api_key:
                        tools_dict[tool_name]['api_key'] = llm_api_key
                    if llm_endpoint:
                        tools_dict[tool_name]['base_url'] = llm_endpoint
                        tools_dict[tool_name]['endpoint_url'] = llm_endpoint

            # Special handling for grounding and embedding models:
            tools_dict['grounding']['provider'] = 'doubao'
            tools_dict['grounding']['model_name'] = "doubao-1-5-ui-tars-250428"
            tools_dict['grounding']['model'] = "doubao-1-5-ui-tars-250428"
            if llm_api_key:
                tools_dict['grounding']['api_key'] = llm_api_key
            if llm_endpoint:
                tools_dict['grounding']['base_url'] = llm_endpoint
                tools_dict['grounding']['endpoint_url'] = llm_endpoint
            tools_dict['embedding']['provider'] = 'doubao'
            tools_dict['embedding']['model_name'] = "doubao-embedding-text-240715"
            tools_dict['embedding']['model'] = "doubao-embedding-text-240715"
            if llm_api_key:
                tools_dict['embedding']['api_key'] = llm_api_key
            if llm_endpoint:
                tools_dict['embedding']['base_url'] = llm_endpoint
                tools_dict['embedding']['endpoint_url'] = llm_endpoint

            # Sync all modifications back to tools_config
            for tool_entry in tools_config['tools']:
                tool_name = tool_entry['tool_name']
                if tool_name in tools_dict:
                    modified_data = tools_dict[tool_name]
                    # Ensure all modified fields are synced back to tools_config
                    for key, value in modified_data.items():
                        if key in ['provider', 'model_name', 'api_key', 'base_url', 'model', 'endpoint_url']:
                            tool_entry[key] = value

        if mode == "fast":
            agent = AgentSFast(
                platform="windows",
                screen_size=[1280, 720],
                enable_takeover=False,
                enable_search=False,
                tools_config=tools_config,
                enable_reflection=True,
            )
        else:
            agent = AgentS2(
                platform="windows",
                screen_size=[1280, 720],
                enable_takeover=False,
                enable_search=False,
                tools_config=tools_config
            )

        # Set task_id before calling reset()
        agent.task_id = task_id

        # Create hardware interface
        hwi = HardwareInterface(
            backend='lybic',
            platform='Windows',
            precreate_sid=sandbox_id,
            org_id=lybic_auth.org_id,
            api_key=lybic_auth.api_key,
            endpoint=lybic_auth.endpoint
        )

        # Reset agent (now it has task_id set)
        agent.reset()

        # Execute in thread
        logger.info(f"Executing instruction in {mode} mode: {instruction}")

        if mode == "fast":
            await asyncio.to_thread(
                cli_app.run_agent_fast,
                agent, instruction, hwi, max_steps, False,
                task_id=task_id, task_registry=task_registry
            )
        else:
            await asyncio.to_thread(
                cli_app.run_agent_normal,
                agent, instruction, hwi, max_steps, False,
                task_id=task_id, task_registry=task_registry
            )

        # Analyze results
        display_json_path = timestamp_dir / "display.json"
        result_text = f"Instruction executed successfully!\n\nSandbox ID: {sandbox_id}\nMode: {mode}\nMax steps: {max_steps}\n"

        if display_json_path.exists():
            try:
                analysis = analyze_display_json(str(display_json_path))
                if analysis:
                    result_text += f"\nExecution Statistics:\n"
                    result_text += f"- Steps: {analysis.get('fast_action_count', 0)}\n"
                    result_text += f"- Duration: {analysis.get('total_duration', 0):.2f}s\n"
                    result_text += f"- Input tokens: {analysis.get('total_input_tokens', 0)}\n"
                    result_text += f"- Output tokens: {analysis.get('total_output_tokens', 0)}\n"
                    result_text += f"- Cost: {analysis.get('currency_symbol', '¥')}{analysis.get('total_cost', 0):.4f}\n"
            except Exception as e:
                logger.warning(f"Failed to analyze execution: {e}")

        result_text += f"\nLog directory: {timestamp_dir}\n"

        return [types.TextContent(
            type="text",
            text=result_text
        )]

    except Exception as e:
        logger.error(f"Failed to execute instruction: {e}", exc_info=True)
        raise
    finally:
        # Cleanup registry and active task
        if task_id:
            Registry.remove_task_registry(task_id)
            if task_id in active_tasks:
                active_tasks.remove(task_id)

session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        event_store=None,
        json_response=False,
        stateless=True,
)

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Context manager for session manager."""
    async with session_manager.run():
        logger.info("Application started with StreamableHTTP session manager!")
        try:
            yield
        finally:
            logger.info("Application shutting down...")

# Create FastAPI app for Streamable HTTP transport
title = "GUI Agent MCP Server"
app = FastAPI(title=title, lifespan=lifespan)

async def handle_streamable_http(scope: Scope, receive: Receive, send: Send) -> None:
    await session_manager.handle_request(scope, receive, send)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "server": "gui-agent-mcp-server",
        "active_sandboxes": len(active_sandboxes),
        "active_tasks": len(active_tasks)
    }



@app.get("/")
async def root():
    """Root endpoint with server information"""
    return {
        "name": "GUI Agent MCP Server",
        "description": "MCP server for GUI automation with Lybic sandboxes",
        "version": "1.0.0",
        "endpoints": {
            "mcp_stream": "/mcp (POST) - MCP Streamable HTTP endpoint (requires Bearer token)",
            "health": "/health (GET) - Health check",
        },
        "authentication": "Bearer token required (configured in access_tokens.txt)",
        "tools": [
            "create_sandbox - Create a new sandbox environment",
            "get_sandbox_screenshot - Get screenshot from sandbox",
            "execute_instruction - Execute agent instruction with streaming"
        ]
    }

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path == "/mcp":
            try:
                await authenticate_request(request)
            except HTTPException as exc:
                # Return proper JSON response for authentication errors
                from starlette.responses import JSONResponse
                return JSONResponse(
                    status_code=exc.status_code,
                    content={"detail": exc.detail},
                    headers=exc.headers
                )
        return await call_next(request)

def main():
    """Main entry point for MCP server"""
    # Check for access tokens file
    if not ACCESS_TOKENS_FILE.exists():
        logger.warning(f"Access tokens file not found at {ACCESS_TOKENS_FILE}")
        logger.warning("Creating default access_tokens.txt file")
        with open(ACCESS_TOKENS_FILE, 'w', encoding='utf-8') as f:
            f.write("# Access tokens for MCP server authentication\n")
            f.write("# Each line represents a valid Bearer token\n")
            f.write("default_token_for_testing\n")
    
    # Check environment compatibility
    has_display, pyautogui_available, env_error = cli_app.check_display_environment()
    compatible_backends, incompatible_backends = cli_app.get_compatible_backends(has_display, pyautogui_available)
    
    # Log environment information if there are any warnings
    if env_error:
        logger.info(f"Environment note: {env_error}")
    
    try:
        cli_app.validate_backend_compatibility('lybic', compatible_backends, incompatible_backends)
    except Exception as e:
        logger.error(f"Backend validation failed: {e}")
        logger.error("MCP server requires Lybic backend support")
        sys.exit(1)
    
    port = int(os.environ.get("MCP_PORT", 8000))
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    
    logger.info(f"Starting MCP server on {host}:{port}")
    logger.info(f"Access tokens file: {ACCESS_TOKENS_FILE}")

    # Create a single FastAPI app to handle all routing
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AuthMiddleware)

    # Create an ASGI wrapper class for the MCP endpoint
    class MCPApp:
        """ASGI wrapper for MCP streamable HTTP handler"""
        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http" and scope["method"] == "POST":
                await handle_streamable_http(scope, receive, send)
            else:
                # Method not allowed
                await send({
                    "type": "http.response.start",
                    "status": 405,
                    "headers": [[b"content-type", b"text/plain"]],
                })
                await send({
                    "type": "http.response.body",
                    "body": b"Method Not Allowed",
                })

    # Mount the MCP ASGI app
    app.mount("/mcp", MCPApp())


    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=level.lower()
    )


if __name__ == "__main__":
    main()
