"""
Tools integration module for GUI agents.

This module provides integration between the tools module and the existing GUI agent code.
It allows the agent to use the tools without modifying the existing code.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List, Union

from gui_agents.s2.tools.tools import Tools

logger = logging.getLogger(__name__)

class ToolsIntegration:
    """Integration class for tools and existing GUI agent code."""
    
    def __init__(self):
        """Initialize the tools integration."""
        self.tools = Tools()
        self.registered_tools = set()
        
    def register_tool(self, tool_name: str, provider: str, model_name: str) -> None:
        """
        Register a tool with the specified parameters.
        
        Args:
            tool_name: Name of the tool to register
            provider: API provider name
            model_name: Model name to use
        """
        self.tools.register_tool(tool_name, provider, model_name)
        self.registered_tools.add(tool_name)
        logger.info(f"Registered tool: {tool_name} with provider: {provider} and model: {model_name}")
    
    def register_tools_from_config(self, config_path: str) -> None:
        """
        Register tools from a configuration file.
        
        Args:
            config_path: Path to the configuration file
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            for tool_config in config.get("tools", []):
                tool_name = tool_config.get("tool_name")
                provider = tool_config.get("provider")
                model_name = tool_config.get("model_name")
                
                if tool_name and provider and model_name:
                    self.register_tool(tool_name, provider, model_name)
                else:
                    logger.warning(f"Skipping invalid tool configuration: {tool_config}")
                    
            logger.info(f"Registered {len(self.registered_tools)} tools from config: {config_path}")
        except Exception as e:
            logger.error(f"Failed to load tools from config: {e}")
    
    def execute_tool(self, tool_name: str, str_input: Optional[str] = None, img_input: Optional[bytes] = None) -> str:
        """
        Execute a tool with the given input.
        
        Args:
            tool_name: Name of the tool to execute
            str_input: String input for the tool
            img_input: Image input for the tool as bytes
        
        Returns:
            The output of the tool as a string
        
        Raises:
            ValueError: If the tool is not registered
        """
        if tool_name not in self.registered_tools:
            raise ValueError(f"Tool {tool_name} is not registered")
        
        tool_input = {
            "str_input": str_input,
            "img_input": img_input
        }
        
        logger.info(f"Executing tool: {tool_name}")
        return self.tools.execute_tool(tool_name, tool_input)
    
    def websearch(self, query: str) -> str:
        """
        Perform a web search.
        
        Args:
            query: Search query
        
        Returns:
            Search results as a string
        """
        return self.execute_tool("websearch", str_input=query)
    
    def context_fusion(self, contexts: Dict[str, Any]) -> str:
        """
        Fuse multiple contexts together.
        
        Args:
            contexts: Dictionary containing the contexts to fuse
        
        Returns:
            Fused context as a string
        """
        return self.execute_tool("context_fusion", str_input=json.dumps(contexts))
    
    def subtask_planner(self, task: str, screenshot: Optional[bytes] = None) -> str:
        """
        Plan subtasks for a given task.
        
        Args:
            task: Task description
            screenshot: Optional screenshot as bytes
        
        Returns:
            Subtask plan as a string
        """
        return self.execute_tool("subtask_planner", str_input=task, img_input=screenshot)
    
    def traj_reflector(self, trajectory: str) -> str:
        """
        Reflect on an execution trajectory.
        
        Args:
            trajectory: Execution trajectory
        
        Returns:
            Reflection as a string
        """
        return self.execute_tool("traj_reflector", str_input=trajectory)
    
    def memory_retrieval(self, query: str) -> str:
        """
        Retrieve relevant memories based on a query.
        
        Args:
            query: Query for memory retrieval
        
        Returns:
            Retrieved memories as a string
        """
        return self.execute_tool("memory_retrival", str_input=query)
    
    def grounding(self, action: str, screenshot: bytes) -> str:
        """
        Ground agent actions in the environment.
        
        Args:
            action: Action to ground
            screenshot: Screenshot as bytes
        
        Returns:
            Grounded action as a string
        """
        return self.execute_tool("grounding", str_input=action, img_input=screenshot)
    
    def evaluator(self, eval_data: Dict[str, Any]) -> str:
        """
        Evaluate agent performance.
        
        Args:
            eval_data: Evaluation data as a dictionary
        
        Returns:
            Evaluation result as a string
        """
        return self.execute_tool("evaluator", str_input=json.dumps(eval_data))
    
    def action_generator(self, action_request: str, screenshot: Optional[bytes] = None) -> str:
        """
        Generate executable actions.
        
        Args:
            action_request: Action request
            screenshot: Optional screenshot as bytes
        
        Returns:
            Generated action as a string
        """
        return self.execute_tool("action_generator", str_input=action_request, img_input=screenshot)


# Example configuration file structure
EXAMPLE_CONFIG = {
  "tools": [
        {
        "tool_name": "websearch",
        "provider": "exa",
        "model_name": "exa-research"
        },
        {
        "tool_name": "context_fusion",
        "provider": "gemini",
        "model_name": "gemini-2.5-pro"
        },
        {
        "tool_name": "subtask_planner",
        "provider": "gemini",
        "model_name": "gemini-2.5-pro"
        },
        {
        "tool_name": "traj_reflector",
        "provider": "gemini",
        "model_name": "gemini-2.5-pro"
        },
        {
        "tool_name": "memory_retrival",
        "provider": "gemini",
        "model_name": "gemini-2.5-pro"
        },
        {
        "tool_name": "grounding",
        "provider": "gemini",
        "model_name": "gemini-2.5-pro"
        },
        {
        "tool_name": "evaluator",
        "provider": "gemini",
        "model_name": "gemini-2.5-pro"
        },
        {
        "tool_name": "action_generator",
        "provider": "gemini",
        "model_name": "gemini-2.5-pro"
        }
    ]
} 

def create_example_config(config_path: str = "tools_config.json") -> None:
    """
    Create an example configuration file.
    
    Args:
        config_path: Path to save the configuration file
    """
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(EXAMPLE_CONFIG, f, indent=2)
    
    logger.info(f"Created example configuration file at: {config_path}")


def get_tools_integration(config_path: Optional[str] = None) -> ToolsIntegration:
    """
    Get a configured ToolsIntegration instance.
    
    Args:
        config_path: Path to the configuration file
    
    Returns:
        A configured ToolsIntegration instance
    """
    integration = ToolsIntegration()
    
    if config_path and os.path.exists(config_path):
        integration.register_tools_from_config(config_path)
    else:
        # Register default tools
        integration.register_tool("websearch", "bocha", "default")
        integration.register_tool("grounding", "anthropic", "claude-3-5-sonnet")
        integration.register_tool("action_generator", "anthropic", "claude-3-5-sonnet")
    
    return integration 