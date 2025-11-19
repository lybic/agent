#!/usr/bin/env python3
"""
Example MCP client for GUI Agent server

This script demonstrates how to use the MCP client to interact with the GUI Agent server.
It shows how to:
1. Connect to the MCP server
2. Create a sandbox
3. Execute instructions
4. Get screenshots

Prerequisites:
- MCP server running (python -m gui_agents.mcp_app)
- Valid Bearer token in access_tokens.txt
- Environment variables set (LYBIC_API_KEY, LYBIC_ORG_ID)
"""

import asyncio
import sys
from typing import Optional

try:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
except ImportError:
    print("Error: MCP client library not installed")
    print("Install with: pip install mcp")
    sys.exit(1)

LYBIC_MCP_SERVER_API_KEY = "default_token_for_testing"

class MCPGUIAgentClient:
    """Simple wrapper for MCP GUI Agent client"""
    
    def __init__(self, server_command: str = "lybic-guiagent-mcp"):
        """
        Initialize MCP client
        
        Args:
            server_command: Command to start the MCP server
        """
    
    async def connect(self):
        """Connect to MCP server and initialize session"""
        self.client = streamablehttp_client('http://localhost:8000', headers={"Authorization": f"Bearer {LYBIC_MCP_SERVER_API_KEY}"})
        self.read, self.write, _ = await self.client.__aenter__()
        self.session = ClientSession(self.read, self.write)
        await self.session.__aenter__()
        
        # Initialize the session
        await self.session.initialize()
        print("✓ Connected to MCP server")
    
    async def disconnect(self):
        """Disconnect from MCP server"""
        if hasattr(self, 'session'):
            await self.session.__aexit__(None, None, None)
        if hasattr(self, 'client'):
            await self.client.__aexit__(None, None, None)
        print("✓ Disconnected from MCP server")
    
    async def list_tools(self):
        """List available tools"""
        result = await self.session.list_tools()
        return result.tools
    
    async def create_sandbox(
        self, 
        apikey: Optional[str] = None, 
        orgid: Optional[str] = None,
        shape: str = "beijing-2c-4g-cpu"
    ) -> str:
        """
        Create a new sandbox
        
        Args:
            apikey: Lybic API key (optional)
            orgid: Lybic Org ID (optional)
            shape: Sandbox shape/configuration
            
        Returns:
            Sandbox ID
        """
        args = {"shape": shape}
        if apikey:
            args["apikey"] = apikey
        if orgid:
            args["orgid"] = orgid
        
        result = await self.session.call_tool("create_sandbox", args)
        
        # Extract sandbox ID from result text
        for content in result.content:
            if hasattr(content, 'text') and 'Sandbox ID:' in content.text:
                # Parse sandbox ID from text
                lines = content.text.split('\n')
                for line in lines:
                    if 'Sandbox ID:' in line:
                        sandbox_id = line.split('Sandbox ID:')[1].strip()
                        return sandbox_id
        
        raise ValueError("Could not extract sandbox ID from response")
    
    async def get_screenshot(
        self,
        sandbox_id: str,
        apikey: Optional[str] = None,
        orgid: Optional[str] = None
    ) -> str:
        """
        Get screenshot from sandbox
        
        Args:
            sandbox_id: Sandbox ID
            apikey: Lybic API key (optional)
            orgid: Lybic Org ID (optional)
            
        Returns:
            Screenshot information text
        """
        args = {"sandbox_id": sandbox_id}
        if apikey:
            args["apikey"] = apikey
        if orgid:
            args["orgid"] = orgid
        
        result = await self.session.call_tool("get_sandbox_screenshot", args)
        
        # Return the text content
        for content in result.content:
            if hasattr(content, 'text'):
                return content.text
        
        return "No screenshot information available"
    
    async def execute_instruction(
        self,
        instruction: str,
        sandbox_id: Optional[str] = None,
        mode: str = "fast",
        max_steps: int = 50,
        apikey: Optional[str] = None,
        orgid: Optional[str] = None,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        llm_api_key: Optional[str] = None
    ) -> str:
        """
        Execute an instruction in a sandbox
        
        Args:
            instruction: Natural language task description
            sandbox_id: Existing sandbox ID (optional, will create new if not provided)
            mode: Agent mode ('normal' or 'fast')
            max_steps: Maximum steps to execute
            apikey: Lybic API key (optional)
            orgid: Lybic Org ID (optional)
            llm_provider: LLM provider (optional)
            llm_model: LLM model name (optional)
            llm_api_key: LLM API key (optional)
            
        Returns:
            Execution result text
        """
        args = {
            "instruction": instruction,
            "mode": mode,
            "max_steps": max_steps
        }
        
        if sandbox_id:
            args["sandbox_id"] = sandbox_id
        if apikey:
            args["apikey"] = apikey
        if orgid:
            args["orgid"] = orgid
        if llm_provider:
            args["llm_provider"] = llm_provider
        if llm_model:
            args["llm_model"] = llm_model
        if llm_api_key:
            args["llm_api_key"] = llm_api_key
        
        result = await self.session.call_tool("execute_instruction", args)
        
        # Return the text content
        for content in result.content:
            if hasattr(content, 'text'):
                return content.text
        
        return "No execution result available"


async def example_usage():
    """Example usage of the MCP client"""
    
    print("=" * 80)
    print("MCP GUI Agent Client Example")
    print("=" * 80)
    
    # Create client
    client = MCPGUIAgentClient()
    
    try:
        # Connect to server
        print("\n1. Connecting to MCP server...")
        await client.connect()
        
        # List available tools
        print("\n2. Listing available tools...")
        tools = await client.list_tools()
        for tool in tools:
            print(f"   - {tool.name}: {tool.description}")
        
        # Create a sandbox
        print("\n3. Creating sandbox...")
        sandbox_id = await client.create_sandbox()
        print(f"   Sandbox ID: {sandbox_id}")
        
        # Execute a simple instruction
        print("\n4. Executing instruction...")
        instruction = "Open calculator application"
        print(f"   Instruction: {instruction}")
        result = await client.execute_instruction(
            instruction=instruction,
            sandbox_id=sandbox_id,
            mode="fast",
            max_steps=10
        )
        print(f"\n   Result:\n{result}")
        
        # Get screenshot
        print("\n5. Getting screenshot...")
        screenshot_info = await client.get_screenshot(sandbox_id)
        print(f"   {screenshot_info}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Disconnect
        print("\n6. Disconnecting...")
        await client.disconnect()
    
    print("\n" + "=" * 80)
    print("Example completed!")
    print("=" * 80)


async def interactive_mode():
    """Interactive mode for testing MCP client"""
    
    print("=" * 80)
    print("MCP GUI Agent Client - Interactive Mode")
    print("=" * 80)
    print("\nCommands:")
    print("  create - Create a new sandbox")
    print("  execute <instruction> - Execute an instruction")
    print("  screenshot - Get a screenshot")
    print("  list - List available tools")
    print("  quit - Exit")
    print("=" * 80)
    
    client = MCPGUIAgentClient()
    sandbox_id = None
    
    try:
        # Connect
        await client.connect()
        
        while True:
            try:
                command = input("\n> ").strip()
                
                if not command:
                    continue
                
                if command == "quit":
                    break
                
                elif command == "list":
                    tools = await client.list_tools()
                    for tool in tools:
                        print(f"  {tool.name}: {tool.description}")
                
                elif command == "create":
                    sandbox_id = await client.create_sandbox()
                    print(f"Sandbox created: {sandbox_id}")
                
                elif command.startswith("execute "):
                    if not sandbox_id:
                        print("Error: Create a sandbox first with 'create' command")
                        continue
                    
                    instruction = command[8:].strip()
                    if not instruction:
                        print("Error: Please provide an instruction")
                        continue
                    
                    print(f"Executing: {instruction}")
                    result = await client.execute_instruction(
                        instruction=instruction,
                        sandbox_id=sandbox_id,
                        mode="fast"
                    )
                    print(result)
                
                elif command == "screenshot":
                    if not sandbox_id:
                        print("Error: Create a sandbox first with 'create' command")
                        continue
                    
                    screenshot_info = await client.get_screenshot(sandbox_id)
                    print(screenshot_info)
                
                else:
                    print(f"Unknown command: {command}")
                    print("Type 'quit' to exit or see available commands above")
            
            except KeyboardInterrupt:
                print("\n\nInterrupted by user")
                break
            except Exception as e:
                print(f"Error: {e}")
    
    finally:
        await client.disconnect()


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP GUI Agent Client Example")
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    parser.add_argument(
        "--server-command",
        default="lybic-guiagent-mcp",
        help="Command to start MCP server (default: lybic-guiagent-mcp)"
    )
    
    args = parser.parse_args()
    
    if args.interactive:
        await interactive_mode()
    else:
        await example_usage()


if __name__ == "__main__":
    asyncio.run(main())
