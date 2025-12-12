"""
Utilities for extracting and restoring conversation history from agents.

This module provides functions to:
- Extract conversation history from agents (excluding images/screenshots)
- Restore conversation history to agents
- Serialize/deserialize conversation history for storage
"""
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def strip_images_from_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove image content from a message while keeping text content.
    
    Args:
        message: Message dictionary with role and content
        
    Returns:
        Message dictionary with images removed from content
    """
    if "content" not in message:
        return message
    
    # Handle case where content is a string (simple text message)
    if isinstance(message["content"], str):
        return message.copy()
    
    cleaned_message = message.copy()
    cleaned_message["content"] = []
    
    # Handle case where content is a list
    if isinstance(message["content"], list):
        # Filter out image content
        for content_item in message["content"]:
            if isinstance(content_item, dict):
                # Keep text content, skip image content
                if content_item.get("type") == "text":
                    cleaned_message["content"].append(content_item)
                # Skip image_url content
                elif content_item.get("type") == "image_url":
                    continue
                # Skip image content (for Anthropic format)
                elif content_item.get("type") == "image":
                    continue
    
    return cleaned_message


def extract_conversation_history_from_llm_agent(llm_agent) -> List[Dict[str, Any]]:
    """
    Extract conversation history from an LLMAgent instance, excluding images.
    
    Args:
        llm_agent: LLMAgent instance with messages attribute
        
    Returns:
        List of message dictionaries with images removed
    """
    if not hasattr(llm_agent, "messages"):
        logger.warning("LLMAgent does not have messages attribute")
        return []
    
    conversation_history = []
    for message in llm_agent.messages:
        cleaned_message = strip_images_from_message(message)
        conversation_history.append(cleaned_message)
    
    return conversation_history


def extract_conversation_history_from_tool(tool) -> List[Dict[str, Any]]:
    """
    Extract conversation history from a BaseTool instance.
    
    Args:
        tool: BaseTool instance with llm_agent attribute
        
    Returns:
        List of message dictionaries with images removed
    """
    if not hasattr(tool, "llm_agent"):
        logger.warning("Tool does not have llm_agent attribute")
        return []
    
    return extract_conversation_history_from_llm_agent(tool.llm_agent)


def extract_all_conversation_history_from_agent(agent) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extract conversation history from all LLM tools in an agent.
    
    This extracts conversation history from:
    - Manager's tools (subtask_planner, dag_translator, etc.)
    - Worker's tools (action_generator, traj_reflector, etc.)
    
    Args:
        agent: AgentS2 or AgentSFast instance
        
    Returns:
        Dictionary mapping tool names to their conversation histories
    """
    all_histories = {}
    
    # Extract from manager tools
    if hasattr(agent, "manager") and agent.manager:
        manager = agent.manager
        
        # List of tools to extract from manager
        manager_tool_names = [
            "generator_agent",
            "dag_translator_agent",
            "narrative_summarization_agent",
            "episode_summarization_agent"
        ]
        
        for tool_attr in manager_tool_names:
            if hasattr(manager, tool_attr):
                tool = getattr(manager, tool_attr)
                if hasattr(tool, "registered_tools") and tool.registered_tools:
                    # Tools is a container with registered_tools dict
                    for tool_name, tool_instance in tool.registered_tools.items():
                        history = extract_conversation_history_from_tool(tool_instance)
                        if history:
                            all_histories[f"manager_{tool_name}"] = history
    
    # Extract from worker tools
    if hasattr(agent, "worker") and agent.worker:
        worker = agent.worker
        
        # List of tools to extract from worker
        worker_tool_names = [
            "generator_agent",
            "reflection_agent"
        ]
        
        for tool_attr in worker_tool_names:
            if hasattr(worker, tool_attr):
                tool = getattr(worker, tool_attr)
                if hasattr(tool, "registered_tools") and tool.registered_tools:
                    # Tools is a container with registered_tools dict
                    for tool_name, tool_instance in tool.registered_tools.items():
                        history = extract_conversation_history_from_tool(tool_instance)
                        if history:
                            all_histories[f"worker_{tool_name}"] = history
    
    return all_histories


def restore_conversation_history_to_llm_agent(llm_agent, conversation_history: List[Dict[str, Any]]) -> None:
    """
    Restore conversation history to an LLMAgent instance.
    
    Args:
        llm_agent: LLMAgent instance to restore history to
        conversation_history: List of message dictionaries (without images)
    """
    if not hasattr(llm_agent, "messages"):
        logger.warning("LLMAgent does not have messages attribute")
        return
    
    # Clear existing messages and extend with restored history
    # This preserves any external references to the messages list
    llm_agent.messages.clear()
    llm_agent.messages.extend(conversation_history)
    logger.info(f"Restored {len(conversation_history)} messages to LLMAgent")


def restore_conversation_history_to_tool(tool, conversation_history: List[Dict[str, Any]]) -> None:
    """
    Restore conversation history to a BaseTool instance.
    
    Args:
        tool: BaseTool instance with llm_agent attribute
        conversation_history: List of message dictionaries (without images)
    """
    if not hasattr(tool, "llm_agent"):
        logger.warning("Tool does not have llm_agent attribute")
        return
    
    restore_conversation_history_to_llm_agent(tool.llm_agent, conversation_history)


def restore_all_conversation_history_to_agent(agent, all_histories: Dict[str, List[Dict[str, Any]]]) -> None:
    """
    Restore conversation history to all LLM tools in an agent.
    
    This restores conversation history to:
    - Manager's tools (subtask_planner, dag_translator, etc.)
    - Worker's tools (action_generator, traj_reflector, etc.)
    
    Args:
        agent: AgentS2 or AgentSFast instance
        all_histories: Dictionary mapping tool names to their conversation histories
    """
    restored_count = 0
    
    # Restore to manager tools
    if hasattr(agent, "manager") and agent.manager:
        manager = agent.manager
        
        manager_tool_names = [
            "generator_agent",
            "dag_translator_agent",
            "narrative_summarization_agent",
            "episode_summarization_agent"
        ]
        
        for tool_attr in manager_tool_names:
            if hasattr(manager, tool_attr):
                tool = getattr(manager, tool_attr)
                if hasattr(tool, "registered_tools") and tool.registered_tools:
                    for tool_name, tool_instance in tool.registered_tools.items():
                        history_key = f"manager_{tool_name}"
                        if history_key in all_histories:
                            restore_conversation_history_to_tool(tool_instance, all_histories[history_key])
                            restored_count += 1
    
    # Restore to worker tools
    if hasattr(agent, "worker") and agent.worker:
        worker = agent.worker
        
        worker_tool_names = [
            "generator_agent",
            "reflection_agent"
        ]
        
        for tool_attr in worker_tool_names:
            if hasattr(worker, tool_attr):
                tool = getattr(worker, tool_attr)
                if hasattr(tool, "registered_tools") and tool.registered_tools:
                    for tool_name, tool_instance in tool.registered_tools.items():
                        history_key = f"worker_{tool_name}"
                        if history_key in all_histories:
                            restore_conversation_history_to_tool(tool_instance, all_histories[history_key])
                            restored_count += 1
    
    logger.info(f"Restored conversation history to {restored_count} tools")
