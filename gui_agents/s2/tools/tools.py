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
import time
from typing import Dict, Any, Optional, List, Union, Tuple
from abc import ABC, abstractmethod
import logging
from gui_agents.s2.core.mllm import LLMAgent, WebSearchAgent, EmbeddingAgent
import threading

logger = logging.getLogger(__name__)

class BaseTool(ABC):
    """Base class for all tools."""
    _prompts_json = None
    _prompts_json_lock = threading.Lock()

    @classmethod
    def _load_prompts_json(cls):
        if cls._prompts_json is None:
            with cls._prompts_json_lock:
                if cls._prompts_json is None:
                    prompts_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", "prompts.json")
                    try:
                        with open(prompts_path, 'r', encoding='utf-8') as f:
                            cls._prompts_json = json.load(f)
                    except Exception as e:
                        logger.error(f"Failed to load prompts.json: {e}")
                        cls._prompts_json = {}

    def __init__(self, provider: str, model_name: str, tool_name: str):
        """
        Initialize the base tool.
        Args:
            provider: API provider name (e.g., "gemini", "openai")
            model_name: Model name to use (e.g., "gemini-2.5-pro")
            tool_name: Name of the tool (used as key in prompts.json)
        """
        self.provider = provider
        self.model_name = model_name
        self.tool_name = tool_name
        self._load_prompts_json()
        self._prompt_template = self._get_prompt_template()
        # Create LLMAgent instance for tool usage
        self.engine_params = {
            "engine_type": provider,
            "model": model_name
        }
        self.llm_agent = LLMAgent(engine_params=self.engine_params, system_prompt=self._prompt_template)

    def _get_prompt_template(self) -> str:
        if self.tool_name is None:
            return ""
        prompts = self.__class__._prompts_json
        if prompts is None:
            return ""
        return prompts.get(self.tool_name, "")
    
    def _call_lmm(self, input_data: Dict[str, Any], temperature: float = 0.0):
        """
        Call the LMM model for inference using the prompt template with retry mechanism
        
        Args:
            input_data: Dictionary containing input data to format the prompt template
            temperature: Temperature parameter to control randomness of output
            
        Returns:
            Model response as text
        """
        # self.llm_agent.reset()
        
        # Extract text and image inputs
        text_input = input_data.get('str_input', '')
        image_input = input_data.get('img_input', None)
        
        # Add the message with the formatted prompt
        self.llm_agent.add_message(text_input, image_content=image_input, role="user")
        
        # Implement safe retry mechanism
        max_retries = 3
        attempt = 0
        content, total_tokens, cost_string = "", [0, 0, 0], ""
        
        while attempt < max_retries:
            try:
                content, total_tokens, cost_string = self.llm_agent.get_response(temperature=temperature)
                break  # If successful, break out of the loop
            except Exception as e:
                attempt += 1
                logger.error(f"LLM call attempt {attempt} failed: {str(e)}")
                if attempt == max_retries:
                    logger.error("Max retries reached. Returning error message.")
                    return f"Error: LLM call failed after {max_retries} attempts: {str(e)}"
                time.sleep(1.0)
        return content, total_tokens, cost_string
    
    @abstractmethod
    def execute(self, tool_input: Dict[str, Any]) -> Tuple[str, List[int], str]:
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
        tool_map = {
            "websearch": (WebSearchTool, None),
            "context_fusion": (ContextFusionTool, "context_fusion"),
            "subtask_planner": (SubtaskPlannerTool, "subtask_planner"),
            "traj_reflector": (TrajReflectorTool, "traj_reflector"),
            "grounding": (GroundingTool, "grounding"),
            "evaluator": (EvaluatorTool, "evaluator"),
            "action_generator": (ActionGeneratorTool, "action_generator"),
            "dag_translator": (DAGTranslatorTool, "dag_translator"),
            "embedding": (EmbeddingTool, None),
            "query_formulator": (QueryFormulatorTool, "query_formulator"),
            "text_span": (TextSpanTool, "text_span"),
            "narrative_summarization": (NarrativeSummarizationTool, "narrative_summarization"),
            "episode_summarization": (EpisodeSummarizationTool, "episode_summarization")
        }
        
        if tool_name not in tool_map:
            raise ValueError(f"Unknown tool name: {tool_name}")
        
        tool_class, prompt_key = tool_map[tool_name]
        
        # WebSearchTool and EmbeddingTool don't need a prompt
        if tool_name == "websearch":
            return tool_class(provider, model_name, None)
        if tool_name == "embedding":
            return tool_class(provider, model_name, None)
        
        return tool_class(provider, model_name, prompt_key)


class WebSearchTool(BaseTool):
    """Tool for performing web searches."""
    
    def __init__(self, provider: str, model_name: str, tool_name: str):
        """
        Initialize the web search tool.
        
        Args:
            provider: API provider name (e.g., "bocha", "exa")
            model_name: Model name to use (not used for WebSearchAgent)
            tool_name: Name of the tool (used as key in prompts.json)
        """
        self.provider = provider
        
        # Create WebSearchAgent instance for search
        self.engine_params = {
            "engine_type": provider,
            "model": model_name,
        }
        
        # Initialize WebSearchAgent
        self.search_agent = WebSearchAgent(engine_params=self.engine_params)
    
    def execute(self, tool_input: Dict[str, Any]) -> Tuple[str, List[int], str]:
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
            return "Error: No search query provided", [0, 0, 0], ""
        
        try:
            # Get the answer from the search results
            answer, total_tokens, cost = self.search_agent.get_answer(query)
            
            # Return just the answer
            return answer, total_tokens, cost # type: ignore
        
        except Exception as e:
            logger.error(f"Error during web search: {str(e)}")
            return f"Error: Web search failed: {str(e)}", [0, 0, 0], ""


class ContextFusionTool(BaseTool):
    """Tool for fusing multiple contexts together."""
    
    def execute(self, tool_input: Dict[str, Any]):
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
        
        # Use the prompt template and LMM for context fusion
        return self._call_lmm(tool_input)


class SubtaskPlannerTool(BaseTool):
    """Tool for planning subtasks."""
    
    def execute(self, tool_input: Dict[str, Any]):
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
        if not task:
            return "Error: No task description provided"
        
        # Use the prompt template and LMM for subtask planning
        return self._call_lmm(tool_input)


class NarrativeSummarizationTool(BaseTool):
    """Tool for summarizing narrative memories."""
    
    def execute(self, tool_input: Dict[str, Any]):
        """
        Summarize narrative memories.
        
        Args:
            tool_input: Dictionary containing the narrative memory data
                        Expected to have 'str_input' key with the narrative memory data
                        May also have 'img_input' key with relevant images
        
        Returns:
            Summarized narrative as a string
        """
        narrative_data = tool_input.get('str_input', '')
        if not narrative_data:
            return "Error: No narrative memory data provided"
        
        # Use the prompt template and LMM for narrative summarization
        return self._call_lmm(tool_input)


class EpisodeSummarizationTool(BaseTool):
    """Tool for summarizing episodic memories."""
    
    def execute(self, tool_input: Dict[str, Any]):
        """
        Summarize episodic memories.
        
        Args:
            tool_input: Dictionary containing the episodic memory data
                        Expected to have 'str_input' key with the episodic memory data
                        May also have 'img_input' key with relevant images
        
        Returns:
            Summarized episode as a string
        """
        episode_data = tool_input.get('str_input', '')
        if not episode_data:
            return "Error: No episodic memory data provided"
        
        # Use the prompt template and LMM for episode summarization
        return self._call_lmm(tool_input)


class TextSpanTool(BaseTool):
    """Tool for processing text spans."""
    
    def execute(self, tool_input: Dict[str, Any]):
        """
        Process text spans for a given input.
        
        Args:
            tool_input: Dictionary containing the text input
                        Expected to have 'str_input' key with the text content
                        May also have 'img_input' key with a screenshot
        
        Returns:
            Processed text spans as a string
        """
        text = tool_input.get('str_input', '')
        if not text:
            return "Error: No text content provided"
        
        # Use the prompt template and LMM for text span processing
        return self._call_lmm(tool_input)


class DAGTranslatorTool(BaseTool):
    """Tool for translating task descriptions into a DAG (Directed Acyclic Graph) structure."""
    
    def execute(self, tool_input: Dict[str, Any]):
        """
        Translate task descriptions into a DAG structure.
        
        Args:
            tool_input: Dictionary containing the task description
                        Expected to have 'str_input' key with the task description
                        May also have 'img_input' key with a screenshot
        
        Returns:
            DAG representation as a string
        """
        task = tool_input.get('str_input', '')
        if not task:
            return "Error: No task description provided"
        
        # Use the prompt template and LMM for DAG translation
        return self._call_lmm(tool_input)


class TrajReflectorTool(BaseTool):
    """Tool for reflecting on execution trajectories."""
    
    def execute(self, tool_input: Dict[str, Any]):
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
        
        # Use the prompt template and LMM for trajectory reflection
        return self._call_lmm(tool_input)

class GroundingTool(BaseTool):
    """Tool for grounding agent actions in the environment."""
    
    def execute(self, tool_input: Dict[str, Any]):
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
        
        # Use the prompt template and LMM for action grounding
        return self._call_lmm(tool_input)
    
    def get_grounding_wh(self):
        """
        Get grounding width and height based on provider and model name.
        
        Returns:
            If provider is doubao and model_name contains 'ui-tars', returns two values:
            grounding_width (int): Width value (1024)
            grounding_height (int): Height value (768)
            Otherwise returns None, None
        """
        if self.provider == "doubao" and "ui-tars" in self.model_name:
            grounding_width = 1000
            grounding_height = 1000
            return grounding_width, grounding_height
        return None, None


class EvaluatorTool(BaseTool):
    """Tool for evaluating agent performance."""
    
    def execute(self, tool_input: Dict[str, Any]):
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
        
        # Use the prompt template and LMM for performance evaluation
        return self._call_lmm(tool_input)


class ActionGeneratorTool(BaseTool):
    """Tool for generating executable actions."""
    
    def execute(self, tool_input: Dict[str, Any]):
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
        if not action_request:
            return "Error: No action request provided"
        
        # Use the prompt template and LMM for action generation
        return self._call_lmm(tool_input)


class EmbeddingTool(BaseTool):
    """Tool for generating text embeddings."""
    
    def __init__(self, provider: str, model_name: str, tool_name: str):
        """
        Initialize the embedding tool.
        
        Args:
            provider: API provider name (e.g., "openai", "gemini")
            model_name: Model name to use
            tool_name: Name of the tool (used as key in prompts.json)
        """
        self.provider = provider
        self.model_name = model_name
        self.tool_name = tool_name
        
        # Create EmbeddingAgent instance
        self.engine_params = {
            "engine_type": provider,
            "embedding_model": model_name
        }
        
        # Initialize EmbeddingAgent
        self.embedding_agent = EmbeddingAgent(engine_params=self.engine_params)
    
    def execute(self, tool_input: Dict[str, Any]):
        """
        Generate embeddings for the given text.
        
        Args:
            tool_input: Dictionary containing the text to embed
                        Expected to have 'str_input' key with the text
        
        Returns:
            Embeddings as a JSON string
        """
        text = tool_input.get('str_input', '')
        
        if not text:
            return "Error: No text provided for embedding", [0, 0, 0], ""
        
        try:
            # Get embeddings for the text
            embeddings, total_tokens, cost_string = self.embedding_agent.get_embeddings(text)
            return embeddings, total_tokens, cost_string
                
        except Exception as e:
            logger.error(f"Error during embedding operation: {str(e)}")
            return f"Error: Embedding operation failed: {str(e)}", [0, 0, 0], ""

class QueryFormulatorTool(BaseTool):
    """Tool for formulating queries from tasks or contexts."""
    
    def execute(self, tool_input: Dict[str, Any]):
        """
        Formulate a query for a given task or context.
        
        Args:
            tool_input: Dictionary containing the task or context description
                        Expected to have 'str_input' key with the description
                        May also have 'img_input' key with a screenshot
        
        Returns:
            Formulated query as a string
        """
        task = tool_input.get('str_input', '')
        if not task:
            return "Error: No task or context description provided"
        
        # Use the prompt template and LMM for query formulation
        return self._call_lmm(tool_input)

class Tools:
    """Main Tools class that provides access to all available tools."""
    
    def __init__(self):
        """Initialize the Tools class."""
        self.tools = {}
    
    def register_tool(self, tool_name: str, provider: str, model_name: str):
        """
        Register a tool with the specified parameters.
        
        Args:
            tool_name: Name of the tool to register
            provider: API provider name
            model_name: Model name to use
        """
        tool: BaseTool = ToolFactory.create_tool(tool_name, provider, model_name)
        self.tools[tool_name] = tool
    
    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]):
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