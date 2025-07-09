"""
Tools module for GUI agents.

This module provides various tools for GUI agents to perform tasks such as web search,
context fusion, subtask planning, trajectory reflection, memory retrieval, grounding,
evaluation, and action generation.
"""

import os
import json
import base64
import requests
from typing import Dict, Any, Optional, List, Union
from abc import ABC, abstractmethod
import logging
from gui_agents.s2.tools.api_client import APIClientFactory

logger = logging.getLogger(__name__)

class BaseTool(ABC):
    """Base class for all tools."""
    
    def __init__(self, provider: str, model_name: str, prompt_path: str):
        """
        Initialize the base tool.
        
        Args:
            provider: API provider name (e.g., "gemini", "openai")
            model_name: Model name to use (e.g., "gemini-2.5-pro")
            prompt_path: Path to the prompt template file
        """
        self.provider = provider
        self.model_name = model_name
        self.prompt_path = prompt_path
        self._prompt_template = self._load_prompt_template()
        
    def _load_prompt_template(self) -> str:
        """
        Load the prompt template from the specified path.
        
        Returns:
            The prompt template as a string
        """
        try:
            with open(self.prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"Prompt template file not found: {self.prompt_path}")
            return ""
    
    @abstractmethod
    def execute(self, tool_input: Dict[str, Any]) -> str:
        """
        Execute the tool with the given input.
        
        Args:
            tool_input: Dictionary containing the input for the tool
                        Expected to have 'str_input' and/or 'img_input' keys
        
        Returns:
            The output of the tool as a string
        """
        pass


class ToolFactory:
    """Factory class for creating tools."""
    
    @staticmethod
    def create_tool(tool_name: str, provider: str, model_name: str) -> 'BaseTool':
        """
        Create a tool instance based on the tool name.
        
        Args:
            tool_name: Name of the tool to create
            provider: API provider name
            model_name: Model name to use
            
        Returns:
            An instance of the specified tool
        
        Raises:
            ValueError: If the tool name is not recognized
        """
        # Define the base directory for prompt templates
        base_prompt_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
        os.makedirs(base_prompt_dir, exist_ok=True)
        
        # Map tool names to their respective classes and prompt file names
        tool_map = {
            "websearch": (WebSearchTool, "websearch_prompt.txt"),
            "context_fusion": (ContextFusionTool, "context_fusion_prompt.txt"),
            "subtask_planner": (SubtaskPlannerTool, "subtask_planner_prompt.txt"),
            "traj_reflector": (TrajReflectorTool, "traj_reflector_prompt.txt"),
            "memory_retrival": (MemoryRetrievalTool, "memory_retrieval_prompt.txt"),
            "grounding": (GroundingTool, "grounding_prompt.txt"),
            "evaluator": (EvaluatorTool, "evaluator_prompt.txt"),
            "action_generator": (ActionGeneratorTool, "action_generator_prompt.txt")
        }
        
        if tool_name not in tool_map:
            raise ValueError(f"Unknown tool name: {tool_name}")
        
        tool_class, prompt_filename = tool_map[tool_name]
        prompt_path = os.path.join(base_prompt_dir, prompt_filename)
        
        # Create a placeholder prompt file if it doesn't exist
        if not os.path.exists(prompt_path):
            with open(prompt_path, 'w', encoding='utf-8') as f:
                f.write(f"# Default prompt template for {tool_name}\n")
                f.write("# Replace this with an actual prompt template\n")
        
        return tool_class(provider, model_name, prompt_path)


class WebSearchTool(BaseTool):
    """Tool for performing web searches."""
    
    def execute(self, tool_input: Dict[str, Any]) -> str:
        """
        Execute a web search with the given query.
        
        Args:
            tool_input: Dictionary containing the search query
                        Expected to have 'str_input' key with the search query
        
        Returns:
            Search results as a string
        """
        query = tool_input.get('str_input', '')
        if not query:
            return "Error: No search query provided"
        
        # Implement web search based on the provider
        if self.provider == "serper":
            return self._search_with_serper(query)
        elif self.provider == "serpapi":
            return self._search_with_serpapi(query)
        else:
            return f"Web search with provider {self.provider} is not implemented"
    
    def _search_with_serper(self, query: str) -> str:
        """
        Perform a web search using Serper API.
        
        Args:
            query: Search query
            
        Returns:
            Search results as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to Serper
        return f"Serper search results for: {query}"
    
    def _search_with_serpapi(self, query: str) -> str:
        """
        Perform a web search using SerpAPI.
        
        Args:
            query: Search query
            
        Returns:
            Search results as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to SerpAPI
        return f"SerpAPI search results for: {query}"


class ContextFusionTool(BaseTool):
    """Tool for fusing multiple contexts together."""
    
    def execute(self, tool_input: Dict[str, Any]) -> str:
        """
        Fuse multiple contexts together.
        
        Args:
            tool_input: Dictionary containing the contexts to fuse
                        Expected to have 'str_input' key with JSON-formatted contexts
        
        Returns:
            Fused context as a string
        """
        contexts = tool_input.get('str_input', '')
        if not contexts:
            return "Error: No contexts provided"
        
        try:
            contexts_data = json.loads(contexts)
        except json.JSONDecodeError:
            return "Error: Invalid JSON format for contexts"
        
        # Call the appropriate model API based on the provider
        if self.provider == "openai":
            return self._fuse_with_openai(contexts_data)
        elif self.provider == "anthropic":
            return self._fuse_with_anthropic(contexts_data)
        elif self.provider == "gemini":
            return self._fuse_with_gemini(contexts_data)
        else:
            return f"Context fusion with provider {self.provider} is not implemented"
    
    def _fuse_with_openai(self, contexts_data: Dict[str, Any]) -> str:
        """
        Fuse contexts using OpenAI API.
        
        Args:
            contexts_data: Dictionary containing the contexts to fuse
            
        Returns:
            Fused context as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to OpenAI
        return f"Fused context using OpenAI: {len(contexts_data)} contexts combined"
    
    def _fuse_with_anthropic(self, contexts_data: Dict[str, Any]) -> str:
        """
        Fuse contexts using Anthropic API.
        
        Args:
            contexts_data: Dictionary containing the contexts to fuse
            
        Returns:
            Fused context as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to Anthropic
        return f"Fused context using Anthropic: {len(contexts_data)} contexts combined"
    
    def _fuse_with_gemini(self, contexts_data: Dict[str, Any]) -> str:
        """
        Fuse contexts using Gemini API.
        
        Args:
            contexts_data: Dictionary containing the contexts to fuse
            
        Returns:
            Fused context as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to Gemini
        return f"Fused context using Gemini: {len(contexts_data)} contexts combined"


class SubtaskPlannerTool(BaseTool):
    """Tool for planning subtasks."""
    
    def execute(self, tool_input: Dict[str, Any]) -> str:
        """
        Plan subtasks for a given task.
        
        Args:
            tool_input: Dictionary containing the task description
                        Expected to have 'str_input' key with the task description
                        May also have 'img_input' key with a screenshot
        
        Returns:
            Subtask plan as a string
        """
        task = tool_input.get('str_input', '')
        screenshot = tool_input.get('img_input')
        
        if not task:
            return "Error: No task description provided"
        
        # Call the appropriate model API based on the provider
        if self.provider == "openai":
            return self._plan_with_openai(task, screenshot)
        elif self.provider == "anthropic":
            return self._plan_with_anthropic(task, screenshot)
        elif self.provider == "gemini":
            return self._plan_with_gemini(task, screenshot)
        else:
            return f"Subtask planning with provider {self.provider} is not implemented"
    
    def _plan_with_openai(self, task: str, screenshot: Optional[bytes] = None) -> str:
        """
        Plan subtasks using OpenAI API.
        
        Args:
            task: Task description
            screenshot: Optional screenshot as bytes
            
        Returns:
            Subtask plan as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to OpenAI
        has_image = "with screenshot" if screenshot else "without screenshot"
        return f"Subtask plan using OpenAI {has_image} for: {task}"
    
    def _plan_with_anthropic(self, task: str, screenshot: Optional[bytes] = None) -> str:
        """
        Plan subtasks using Anthropic API.
        
        Args:
            task: Task description
            screenshot: Optional screenshot as bytes
            
        Returns:
            Subtask plan as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to Anthropic
        has_image = "with screenshot" if screenshot else "without screenshot"
        return f"Subtask plan using Anthropic {has_image} for: {task}"
    
    def _plan_with_gemini(self, task: str, screenshot: Optional[bytes] = None) -> str:
        """
        Plan subtasks using Gemini API.
        
        Args:
            task: Task description
            screenshot: Optional screenshot as bytes
            
        Returns:
            Subtask plan as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to Gemini
        has_image = "with screenshot" if screenshot else "without screenshot"
        return f"Subtask plan using Gemini {has_image} for: {task}"


class TrajReflectorTool(BaseTool):
    """Tool for reflecting on execution trajectories."""
    
    def execute(self, tool_input: Dict[str, Any]) -> str:
        """
        Reflect on an execution trajectory.
        
        Args:
            tool_input: Dictionary containing the trajectory
                        Expected to have 'str_input' key with the trajectory
        
        Returns:
            Reflection as a string
        """
        trajectory = tool_input.get('str_input', '')
        if not trajectory:
            return "Error: No trajectory provided"
        
        # Call the appropriate model API based on the provider
        if self.provider == "openai":
            return self._reflect_with_openai(trajectory)
        elif self.provider == "anthropic":
            return self._reflect_with_anthropic(trajectory)
        elif self.provider == "gemini":
            return self._reflect_with_gemini(trajectory)
        else:
            return f"Trajectory reflection with provider {self.provider} is not implemented"
    
    def _reflect_with_openai(self, trajectory: str) -> str:
        """
        Reflect on a trajectory using OpenAI API.
        
        Args:
            trajectory: Execution trajectory
            
        Returns:
            Reflection as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to OpenAI
        return f"Reflection using OpenAI on trajectory of length {len(trajectory)}"
    
    def _reflect_with_anthropic(self, trajectory: str) -> str:
        """
        Reflect on a trajectory using Anthropic API.
        
        Args:
            trajectory: Execution trajectory
            
        Returns:
            Reflection as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to Anthropic
        return f"Reflection using Anthropic on trajectory of length {len(trajectory)}"
    
    def _reflect_with_gemini(self, trajectory: str) -> str:
        """
        Reflect on a trajectory using Gemini API.
        
        Args:
            trajectory: Execution trajectory
            
        Returns:
            Reflection as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to Gemini
        return f"Reflection using Gemini on trajectory of length {len(trajectory)}"


class MemoryRetrievalTool(BaseTool):
    """Tool for retrieving relevant memories."""
    
    def execute(self, tool_input: Dict[str, Any]) -> str:
        """
        Retrieve relevant memories based on a query.
        
        Args:
            tool_input: Dictionary containing the query
                        Expected to have 'str_input' key with the query
        
        Returns:
            Retrieved memories as a string
        """
        query = tool_input.get('str_input', '')
        if not query:
            return "Error: No query provided"
        
        # Call the appropriate model API based on the provider
        if self.provider == "openai":
            return self._retrieve_with_openai(query)
        elif self.provider == "anthropic":
            return self._retrieve_with_anthropic(query)
        elif self.provider == "gemini":
            return self._retrieve_with_gemini(query)
        else:
            return f"Memory retrieval with provider {self.provider} is not implemented"
    
    def _retrieve_with_openai(self, query: str) -> str:
        """
        Retrieve memories using OpenAI API.
        
        Args:
            query: Query for memory retrieval
            
        Returns:
            Retrieved memories as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to OpenAI
        return f"Retrieved memories using OpenAI for query: {query}"
    
    def _retrieve_with_anthropic(self, query: str) -> str:
        """
        Retrieve memories using Anthropic API.
        
        Args:
            query: Query for memory retrieval
            
        Returns:
            Retrieved memories as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to Anthropic
        return f"Retrieved memories using Anthropic for query: {query}"
    
    def _retrieve_with_gemini(self, query: str) -> str:
        """
        Retrieve memories using Gemini API.
        
        Args:
            query: Query for memory retrieval
            
        Returns:
            Retrieved memories as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to Gemini
        return f"Retrieved memories using Gemini for query: {query}"


class GroundingTool(BaseTool):
    """Tool for grounding agent actions in the environment."""
    
    def execute(self, tool_input: Dict[str, Any]) -> str:
        """
        Ground agent actions in the environment.
        
        Args:
            tool_input: Dictionary containing the action and environment state
                        Expected to have 'str_input' key with the action
                        Expected to have 'img_input' key with a screenshot
        
        Returns:
            Grounded action as a string
        """
        action = tool_input.get('str_input', '')
        screenshot = tool_input.get('img_input')
        
        if not action:
            return "Error: No action provided"
        if not screenshot:
            return "Error: No screenshot provided"
        
        # Call the appropriate model API based on the provider
        if self.provider == "openai":
            return self._ground_with_openai(action, screenshot)
        elif self.provider == "anthropic":
            return self._ground_with_anthropic(action, screenshot)
        elif self.provider == "gemini":
            return self._ground_with_gemini(action, screenshot)
        else:
            return f"Grounding with provider {self.provider} is not implemented"
    
    def _ground_with_openai(self, action: str, screenshot: bytes) -> str:
        """
        Ground actions using OpenAI API.
        
        Args:
            action: Action to ground
            screenshot: Screenshot as bytes
            
        Returns:
            Grounded action as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to OpenAI
        return f"Grounded action using OpenAI: {action}"
    
    def _ground_with_anthropic(self, action: str, screenshot: bytes) -> str:
        """
        Ground actions using Anthropic API.
        
        Args:
            action: Action to ground
            screenshot: Screenshot as bytes
            
        Returns:
            Grounded action as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to Anthropic
        return f"Grounded action using Anthropic: {action}"
    
    def _ground_with_gemini(self, action: str, screenshot: bytes) -> str:
        """
        Ground actions using Gemini API.
        
        Args:
            action: Action to ground
            screenshot: Screenshot as bytes
            
        Returns:
            Grounded action as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to Gemini
        return f"Grounded action using Gemini: {action}"


class EvaluatorTool(BaseTool):
    """Tool for evaluating agent performance."""
    
    def execute(self, tool_input: Dict[str, Any]) -> str:
        """
        Evaluate agent performance.
        
        Args:
            tool_input: Dictionary containing the evaluation data
                        Expected to have 'str_input' key with the evaluation data
        
        Returns:
            Evaluation result as a string
        """
        eval_data = tool_input.get('str_input', '')
        if not eval_data:
            return "Error: No evaluation data provided"
        
        try:
            eval_data_obj = json.loads(eval_data)
        except json.JSONDecodeError:
            return "Error: Invalid JSON format for evaluation data"
        
        # Call the appropriate model API based on the provider
        if self.provider == "openai":
            return self._evaluate_with_openai(eval_data_obj)
        elif self.provider == "anthropic":
            return self._evaluate_with_anthropic(eval_data_obj)
        elif self.provider == "gemini":
            return self._evaluate_with_gemini(eval_data_obj)
        else:
            return f"Evaluation with provider {self.provider} is not implemented"
    
    def _evaluate_with_openai(self, eval_data_obj: Dict[str, Any]) -> str:
        """
        Evaluate using OpenAI API.
        
        Args:
            eval_data_obj: Evaluation data as a dictionary
            
        Returns:
            Evaluation result as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to OpenAI
        return f"Evaluation using OpenAI: {len(eval_data_obj)} data points analyzed"
    
    def _evaluate_with_anthropic(self, eval_data_obj: Dict[str, Any]) -> str:
        """
        Evaluate using Anthropic API.
        
        Args:
            eval_data_obj: Evaluation data as a dictionary
            
        Returns:
            Evaluation result as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to Anthropic
        return f"Evaluation using Anthropic: {len(eval_data_obj)} data points analyzed"
    
    def _evaluate_with_gemini(self, eval_data_obj: Dict[str, Any]) -> str:
        """
        Evaluate using Gemini API.
        
        Args:
            eval_data_obj: Evaluation data as a dictionary
            
        Returns:
            Evaluation result as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to Gemini
        return f"Evaluation using Gemini: {len(eval_data_obj)} data points analyzed"


class ActionGeneratorTool(BaseTool):
    """Tool for generating executable actions."""
    
    def execute(self, tool_input: Dict[str, Any]) -> str:
        """
        Generate executable actions.
        
        Args:
            tool_input: Dictionary containing the action request
                        Expected to have 'str_input' key with the action request
                        May also have 'img_input' key with a screenshot
        
        Returns:
            Generated action as a string
        """
        action_request = tool_input.get('str_input', '')
        screenshot = tool_input.get('img_input')
        
        if not action_request:
            return "Error: No action request provided"
        
        # Call the appropriate model API based on the provider
        if self.provider == "openai":
            return self._generate_with_openai(action_request, screenshot)
        elif self.provider == "anthropic":
            return self._generate_with_anthropic(action_request, screenshot)
        elif self.provider == "gemini":
            return self._generate_with_gemini(action_request, screenshot)
        else:
            return f"Action generation with provider {self.provider} is not implemented"
    
    def _generate_with_openai(self, action_request: str, screenshot: Optional[bytes] = None) -> str:
        """
        Generate actions using OpenAI API.
        
        Args:
            action_request: Action request
            screenshot: Optional screenshot as bytes
            
        Returns:
            Generated action as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to OpenAI
        has_image = "with screenshot" if screenshot else "without screenshot"
        return f"Generated action using OpenAI {has_image}: {action_request}"
    
    def _generate_with_anthropic(self, action_request: str, screenshot: Optional[bytes] = None) -> str:
        """
        Generate actions using Anthropic API.
        
        Args:
            action_request: Action request
            screenshot: Optional screenshot as bytes
            
        Returns:
            Generated action as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to Anthropic
        has_image = "with screenshot" if screenshot else "without screenshot"
        return f"Generated action using Anthropic {has_image}: {action_request}"
    
    def _generate_with_gemini(self, action_request: str, screenshot: Optional[bytes] = None) -> str:
        """
        Generate actions using Gemini API.
        
        Args:
            action_request: Action request
            screenshot: Optional screenshot as bytes
            
        Returns:
            Generated action as a string
        """
        # Placeholder implementation
        # In a real implementation, you would make an API call to Gemini
        has_image = "with screenshot" if screenshot else "without screenshot"
        return f"Generated action using Gemini {has_image}: {action_request}"


class Tools:
    """Main Tools class that provides access to all available tools."""
    
    def __init__(self):
        """Initialize the Tools class."""
        self.tools = {}
    
    def register_tool(self, tool_name: str, provider: str, model_name: str) -> None:
        """
        Register a tool with the specified parameters.
        
        Args:
            tool_name: Name of the tool to register
            provider: API provider name
            model_name: Model name to use
        """
        tool = ToolFactory.create_tool(tool_name, provider, model_name)
        self.tools[tool_name] = tool
    
    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """
        Execute a tool with the given input.
        
        Args:
            tool_name: Name of the tool to execute
            tool_input: Input for the tool
        
        Returns:
            The output of the tool as a string
        
        Raises:
            ValueError: If the tool is not registered
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool {tool_name} is not registered")
        
        return self.tools[tool_name].execute(tool_input) 