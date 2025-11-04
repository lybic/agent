"""
Tests for MCP server functionality

These tests verify the MCP server's authentication, tool definitions, and basic functionality.
"""

import pytest
import os
from unittest.mock import patch


# Test access token management
def test_load_access_tokens(tmp_path):
    """Test loading access tokens from file"""
    # Create temporary access tokens file
    tokens_file = tmp_path / "access_tokens.txt"
    tokens_file.write_text("""
# This is a comment
token1
token2
# Another comment

token3
    """)
    
    # Mock the ACCESS_TOKENS_FILE
    with patch('gui_agents.mcp_app.ACCESS_TOKENS_FILE', tokens_file):
        from gui_agents.mcp_app import load_access_tokens
        tokens = load_access_tokens()
    
    assert len(tokens) == 3
    assert "token1" in tokens
    assert "token2" in tokens
    assert "token3" in tokens
    assert "# This is a comment" not in tokens


def test_verify_bearer_token(tmp_path):
    """Test Bearer token verification"""
    tokens_file = tmp_path / "access_tokens.txt"
    tokens_file.write_text("valid_token\n")
    
    with patch('gui_agents.mcp_app.ACCESS_TOKENS_FILE', tokens_file):
        from gui_agents.mcp_app import verify_bearer_token
        
        # Valid token
        assert verify_bearer_token("Bearer valid_token") is True
        
        # Invalid token
        assert verify_bearer_token("Bearer invalid_token") is False
        
        # Missing Bearer prefix
        assert verify_bearer_token("valid_token") is False
        
        # None authorization
        assert verify_bearer_token(None) is False


def test_get_lybic_auth():
    """Test Lybic authentication construction"""
    from gui_agents.mcp_app import get_lybic_auth
    
    # Test with provided credentials
    auth = get_lybic_auth(apikey="test_key", orgid="test_org")
    assert auth.api_key == "test_key"
    assert auth.org_id == "test_org"
    
    # Test with environment variables
    with patch.dict(os.environ, {
        'LYBIC_API_KEY': 'env_key',
        'LYBIC_ORG_ID': 'env_org',
        'LYBIC_API_ENDPOINT': 'https://test.api.com/'
    }):
        auth = get_lybic_auth()
        assert auth.api_key == "env_key"
        assert auth.org_id == "env_org"
        assert auth.endpoint == "https://test.api.com/"
    
    # Test missing credentials
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="Lybic API key and Org ID are required"):
            get_lybic_auth()


@pytest.mark.asyncio
async def test_list_tools():
    """Test MCP tools listing"""
    from gui_agents.mcp_app import mcp_server
    
    # Get list of tools
    tools = await mcp_server._list_tools_handler()
    
    # Verify we have the expected tools
    tool_names = [tool.name for tool in tools]
    assert "create_sandbox" in tool_names
    assert "get_sandbox_screenshot" in tool_names
    assert "execute_instruction" in tool_names
    
    # Verify tool schemas
    for tool in tools:
        assert hasattr(tool, 'name')
        assert hasattr(tool, 'description')
        assert hasattr(tool, 'inputSchema')
        assert tool.inputSchema['type'] == 'object'
        assert 'properties' in tool.inputSchema


@pytest.mark.asyncio
async def test_create_sandbox_tool_schema():
    """Test create_sandbox tool schema"""
    from gui_agents.mcp_app import mcp_server
    
    tools = await mcp_server._list_tools_handler()
    create_sandbox = next(t for t in tools if t.name == "create_sandbox")
    
    # Verify schema structure
    props = create_sandbox.inputSchema['properties']
    assert 'apikey' in props
    assert 'orgid' in props
    assert 'shape' in props
    assert props['shape']['default'] == "beijing-2c-4g-cpu"


@pytest.mark.asyncio
async def test_get_sandbox_screenshot_tool_schema():
    """Test get_sandbox_screenshot tool schema"""
    from gui_agents.mcp_app import mcp_server
    
    tools = await mcp_server._list_tools_handler()
    screenshot_tool = next(t for t in tools if t.name == "get_sandbox_screenshot")
    
    # Verify required parameters
    assert 'sandbox_id' in screenshot_tool.inputSchema.get('required', [])
    
    # Verify optional parameters
    props = screenshot_tool.inputSchema['properties']
    assert 'apikey' in props
    assert 'orgid' in props


@pytest.mark.asyncio
async def test_execute_instruction_tool_schema():
    """Test execute_instruction tool schema"""
    from gui_agents.mcp_app import mcp_server
    
    tools = await mcp_server._list_tools_handler()
    exec_tool = next(t for t in tools if t.name == "execute_instruction")
    
    # Verify required parameters
    assert 'instruction' in exec_tool.inputSchema.get('required', [])
    
    # Verify optional parameters
    props = exec_tool.inputSchema['properties']
    assert 'sandbox_id' in props
    assert 'mode' in props
    assert 'max_steps' in props
    assert 'llm_provider' in props
    assert 'llm_model' in props
    assert 'llm_api_key' in props
    
    # Verify defaults
    assert props['mode']['default'] == "fast"
    assert props['max_steps']['default'] == 50
    assert props['mode']['enum'] == ["normal", "fast"]


def test_fastapi_app_creation():
    """Test FastAPI app is created correctly"""
    from gui_agents.mcp_app import app
    
    assert app.title == "GUI Agent MCP Server"
    
    # Check routes exist
    routes = [route.path for route in app.routes]
    assert "/mcp" in routes
    assert "/health" in routes
    assert "/" in routes


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health check endpoint"""
    from gui_agents.mcp_app import health_check, active_tasks

    # Mock active tasks
    active_tasks.add("task1")
    
    result = await health_check()
    
    assert result['status'] == 'healthy'
    assert result['server'] == 'gui-agent-mcp-server'
    assert 'active_sandboxes' in result
    assert result['active_tasks'] == 1

    # Clear mock
    active_tasks.clear()


@pytest.mark.asyncio
async def test_root_endpoint():
    """Test root information endpoint"""
    from gui_agents.mcp_app import root
    
    result = await root()
    
    assert result['name'] == "GUI Agent MCP Server"
    assert 'description' in result
    assert 'version' in result
    assert 'endpoints' in result
    assert 'authentication' in result
    assert 'tools' in result
    assert len(result['tools']) == 3


def test_access_tokens_file_location():
    """Test that access_tokens.txt is in the correct location"""
    from gui_agents.mcp_app import ACCESS_TOKENS_FILE
    
    assert ACCESS_TOKENS_FILE.name == "access_tokens.txt"
    assert ACCESS_TOKENS_FILE.parent.name == "gui_agents"


@pytest.mark.asyncio
async def test_call_tool_unknown():
    """Test calling an unknown tool"""
    from gui_agents.mcp_app import call_tool
    from mcp import types
    
    result = await call_tool("unknown_tool", {})
    
    assert len(result) == 1
    assert isinstance(result[0], types.TextContent)
    assert "Error" in result[0].text
    assert "Unknown tool" in result[0].text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
