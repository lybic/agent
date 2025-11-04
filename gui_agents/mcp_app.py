#!/usr/bin/env python3
"""
MCP (Model Context Protocol) Server for GUI Agent

This server provides an MCP interface with Streamable HTTP endpoint to support remote calls
for GUI automation tasks. It implements Bearer Token authentication and exposes tools for:
- Creating sandboxes
- Getting sandbox screenshots  
- Executing agent instructions with real-time streaming
"""

import os
import sys
import logging
import asyncio
import datetime
import tempfile
from pathlib import Path
from typing import Optional, Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp import types

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
from gui_agents.agents.Action import Screenshot
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

# Store for active sandboxes and tasks
active_sandboxes: Dict[str, Dict[str, Any]] = {}
active_tasks: Dict[str, Dict[str, Any]] = {}


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
    endpoint = os.environ.get("LYBIC_API_ENDPOINT", "https://api.lybic.cn/")
    
    if not api_key or not org_id:
        raise ValueError("Lybic API key and Org ID are required (provide as parameters or set LYBIC_API_KEY and LYBIC_ORG_ID environment variables)")
    
    return LybicAuth(
        org_id=org_id,
        api_key=api_key,
        endpoint=endpoint
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
                        "description": "LLM provider to use (e.g., 'openai', 'anthropic', 'google')"
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
async def call_tool(name: str, arguments: Any) -> list[types.TextContent]:
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
        raise


async def handle_get_sandbox_screenshot(arguments: dict) -> list[types.TextContent]:
    """Get screenshot from sandbox"""
    sandbox_id = arguments["sandbox_id"]
    apikey = arguments.get("apikey")
    orgid = arguments.get("orgid")
    
    try:
        lybic_auth = get_lybic_auth(apikey, orgid)
        
        # Create hardware interface
        hwi = HardwareInterface(
            backend='lybic',
            platform='Windows',
            precreate_sid=sandbox_id,
            org_id=lybic_auth.org_id,
            api_key=lybic_auth.api_key,
            endpoint=lybic_auth.endpoint
        )
        
        # Take screenshot
        screenshot = hwi.dispatch(Screenshot())
        
        # Save screenshot to temporary location (cross-platform)
        temp_base = Path(tempfile.gettempdir())
        temp_dir = temp_base / "mcp_screenshots"
        temp_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = temp_dir / f"{sandbox_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        screenshot.save(screenshot_path)
        
        logger.info(f"Screenshot saved to: {screenshot_path}")
        
        return [types.TextContent(
            type="text",
            text=f"Screenshot captured successfully!\n\nSaved to: {screenshot_path}\nSize: {screenshot.width}x{screenshot.height}"
        )]
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
    
    # Initialize task_id to None so exception handler can check if cleanup is needed
    task_id = None
    
    try:
        lybic_auth = get_lybic_auth(apikey, orgid)
        
        # Create or get sandbox
        if not sandbox_id:
            logger.info("No sandbox_id provided, creating new sandbox")
            lybic_client = LybicClient(lybic_auth)
            sandbox_service = Sandbox(lybic_client)
            result = await sandbox_service.create(shape="beijing-2c-4g-cpu")
            sandbox = await sandbox_service.get(result.id)
            sandbox_id = sandbox.sandbox.id
            await lybic_client.close()
            logger.info(f"Created new sandbox: {sandbox_id}")
        
        # Setup task
        task_id = f"mcp_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
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
                if tool_name not in ['embedding', 'grounding']:
                    tools_dict[tool_name]['provider'] = llm_provider
                    tools_dict[tool_name]['model_name'] = llm_model
                    tools_dict[tool_name]['model'] = llm_model
                    if llm_api_key:
                        tools_dict[tool_name]['api_key'] = llm_api_key
                    if llm_endpoint:
                        tools_dict[tool_name]['base_url'] = llm_endpoint
                        tools_dict[tool_name]['endpoint_url'] = llm_endpoint
            
            # Sync back to tools_config
            for tool_entry in tools_config['tools']:
                tool_name = tool_entry['tool_name']
                if tool_name in tools_dict:
                    for key in ['provider', 'model_name', 'model', 'api_key', 'base_url']:
                        if key in tools_dict[tool_name]:
                            tool_entry[key] = tools_dict[tool_name][key]
        
        if mode == "fast":
            agent = AgentSFast(
                platform="windows",
                screen_size=[1280, 720],
                enable_takeover=False,
                enable_search=False,
                tools_config=tools_config
            )
        else:
            agent = AgentS2(
                platform="windows",
                screen_size=[1280, 720],
                enable_takeover=False,
                enable_search=False,
                tools_config=tools_config
            )
        
        # Create hardware interface
        hwi = HardwareInterface(
            backend='lybic',
            platform='Windows',
            precreate_sid=sandbox_id,
            org_id=lybic_auth.org_id,
            api_key=lybic_auth.api_key,
            endpoint=lybic_auth.endpoint
        )
        
        # Reset agent
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
        
        # Cleanup registry
        Registry.remove_task_registry(task_id)
        
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
        # Cleanup on error
        if task_id:
            Registry.remove_task_registry(task_id)
        raise


# Create FastAPI app for SSE transport
app = FastAPI(title="GUI Agent MCP Server")


@app.post("/sse")
async def handle_sse(request: Request):
    """Handle SSE endpoint for MCP communication"""
    # Authenticate request
    await authenticate_request(request)
    
    # Create SSE transport
    async with SseServerTransport("/messages") as transport:
        await mcp_server.run(
            transport[0],
            transport[1],
            mcp_server.create_initialization_options()
        )


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
            "sse": "/sse (POST) - MCP SSE endpoint (requires Bearer token)",
            "health": "/health (GET) - Health check",
        },
        "authentication": "Bearer token required (configured in access_tokens.txt)",
        "tools": [
            "create_sandbox - Create a new sandbox environment",
            "get_sandbox_screenshot - Get screenshot from sandbox",
            "execute_instruction - Execute agent instruction with streaming"
        ]
    }


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
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=level.lower()
    )


if __name__ == "__main__":
    main()
