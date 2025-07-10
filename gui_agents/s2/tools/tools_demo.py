#!/usr/bin/env python3
"""
Demonstration script for integrating the Tools class with existing code.

This script shows how to integrate the Tools class with the existing GUI agent code.
It provides examples of using different tools for various tasks.
"""

import os
import io
import sys
import argparse
import pyautogui
from PIL import Image
import numpy as np

from gui_agents.s2.tools.tools_integration import ToolsIntegration, get_tools_integration

def take_screenshot():
    """
    Take a screenshot using pyautogui.
    
    Returns:
        Screenshot as bytes
    """
    screenshot = pyautogui.screenshot()
    buffered = io.BytesIO()
    screenshot.save(buffered, format="PNG")
    return buffered.getvalue()

def demo_websearch(tools_integration):
    """
    Demonstrate the web search tool.
    
    Args:
        tools_integration: ToolsIntegration instance
    """
    print("\n=== Web Search Demo ===")
    
    query = "latest advancements in GUI agents"
    print(f"Query: {query}")
    
    result = tools_integration.websearch(query)
    print("Result:")
    print(result)

def demo_subtask_planner(tools_integration):
    """
    Demonstrate the subtask planner tool.
    
    Args:
        tools_integration: ToolsIntegration instance
    """
    print("\n=== Subtask Planner Demo ===")
    
    task = "Create a PowerPoint presentation about climate change"
    print(f"Task: {task}")
    
    # Take a screenshot
    screenshot = take_screenshot()
    
    result = tools_integration.subtask_planner(task, screenshot)
    print("Result:")
    print(result)

def demo_dag_translator(tools_integration):
    """
    Demonstrate the DAG translator tool.
    
    Args:
        tools_integration: ToolsIntegration instance
    """
    print("\n=== DAG Translator Demo ===")
    
    task = "Create a data visualization dashboard with user authentication, data import, and interactive charts"
    print(f"Task: {task}")
    
    # Take a screenshot
    screenshot = take_screenshot()
    
    result = tools_integration.dag_translator(task, screenshot)
    print("Result:")
    print(result)

def demo_grounding(tools_integration):
    """
    Demonstrate the grounding tool.
    
    Args:
        tools_integration: ToolsIntegration instance
    """
    print("\n=== Grounding Demo ===")
    
    action = "Click the search button"
    print(f"Action: {action}")
    
    # Take a screenshot
    screenshot = take_screenshot()
    
    result = tools_integration.grounding(action, screenshot)
    print("Result:")
    print(result)

def demo_action_generator(tools_integration):
    """
    Demonstrate the action generator tool.
    
    Args:
        tools_integration: ToolsIntegration instance
    """
    print("\n=== Action Generator Demo ===")
    
    action_request = "Open the settings menu"
    print(f"Action Request: {action_request}")
    
    # Take a screenshot
    screenshot = take_screenshot()
    
    result = tools_integration.action_generator(action_request, screenshot)
    print("Result:")
    print(result)

def demo_trajectory_reflection(tools_integration):
    """
    Demonstrate the trajectory reflection tool.
    
    Args:
        tools_integration: ToolsIntegration instance
    """
    print("\n=== Trajectory Reflection Demo ===")
    
    trajectory = """
    Task: Find a file named 'report.pdf' on the desktop
    
    Action 1: Look at the desktop
    Result 1: Many icons visible, but report.pdf not immediately visible
    
    Action 2: Search for 'report.pdf' using search bar
    Result 2: Found report.pdf in Documents folder
    
    Action 3: Open report.pdf
    Result 3: File opened successfully
    """
    print(f"Trajectory: {trajectory}")
    
    result = tools_integration.traj_reflector(trajectory)
    print("Result:")
    print(result)

def demo_memory_retrieval(tools_integration):
    """
    Demonstrate the memory retrieval tool.
    
    Args:
        tools_integration: ToolsIntegration instance
    """
    print("\n=== Memory Retrieval Demo ===")
    
    query = "How to open settings in Windows?"
    print(f"Query: {query}")
    
    result = tools_integration.memory_retrieval(query)
    print("Result:")
    print(result)

def demo_context_fusion(tools_integration):
    """
    Demonstrate the context fusion tool.
    
    Args:
        tools_integration: ToolsIntegration instance
    """
    print("\n=== Context Fusion Demo ===")
    
    contexts = {
        "user_query": "How to create a new folder?",
        "screenshot_description": "Desktop with file explorer open",
        "system_info": "Windows 11, File Explorer",
        "previous_actions": ["Opened File Explorer", "Navigated to Documents"]
    }
    print(f"Contexts: {contexts}")
    
    result = tools_integration.context_fusion(contexts)
    print("Result:")
    print(result)

def demo_evaluator(tools_integration):
    """
    Demonstrate the evaluator tool.
    
    Args:
        tools_integration: ToolsIntegration instance
    """
    print("\n=== Evaluator Demo ===")
    
    eval_data = {
        "task": "Find a file named 'report.pdf' on the desktop",
        "actions": [
            {"action": "Look at the desktop", "result": "Many icons visible, but report.pdf not immediately visible"},
            {"action": "Search for 'report.pdf' using search bar", "result": "Found report.pdf in Documents folder"},
            {"action": "Open report.pdf", "result": "File opened successfully"}
        ],
        "success": True,
        "time_taken": 15.5
    }
    print(f"Evaluation Data: {eval_data}")
    
    result = tools_integration.evaluator(eval_data)
    print("Result:")
    print(result)

def demo_embedding(tools_integration):
    """
    Demonstrate the embedding tool.
    
    Args:
        tools_integration: ToolsIntegration instance
    """
    print("\n=== Embedding Demo ===")
    
    text = "This is a sample text for embedding generation"
    print(f"Text: {text}")
    
    embeddings = tools_integration.embedding(text)
    
    # Convert to numpy array for easier analysis
    embeddings_array = np.array(embeddings)
    
    print(f"Embedding shape: {embeddings_array.shape}")
    print(f"First 5 dimensions: {embeddings_array[:5]}")

def demo_query_formulator(tools_integration):
    """
    Demonstrate the query formulator tool.
    
    Args:
        tools_integration: ToolsIntegration instance
    """
    print("\n=== Query Formulator Demo ===")
    
    task = "查找并打开桌面上的report.pdf文件"
    print(f"Task: {task}")
    
    # Take a screenshot
    screenshot = take_screenshot()
    
    result = tools_integration.query_formulator(task, screenshot)
    print("Result:")
    print(result)

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Demonstrate the Tools integration")
    parser.add_argument(
        "--config", "-c",
        type=str,
        default="tools_config.json",
        help="Path to the configuration file"
    )
    parser.add_argument(
        "--demo", "-d",
        type=str,
        choices=["all", "websearch", "subtask_planner", "dag_translator", "grounding", "action_generator", 
                 "trajectory_reflection", "memory_retrieval", "context_fusion", "evaluator", "embedding", "query_formulator"],
        default="all",
        help="Which demo to run"
    )
    
    args = parser.parse_args()
    
    # Get the tools integration
    tools_integration = get_tools_integration(args.config)
    
    # Run the selected demo
    if args.demo == "all" or args.demo == "websearch":
        demo_websearch(tools_integration)
    
    if args.demo == "all" or args.demo == "subtask_planner":
        demo_subtask_planner(tools_integration)
    
    if args.demo == "all" or args.demo == "dag_translator":
        demo_dag_translator(tools_integration)
    
    if args.demo == "all" or args.demo == "grounding":
        demo_grounding(tools_integration)
    
    if args.demo == "all" or args.demo == "action_generator":
        demo_action_generator(tools_integration)
    
    if args.demo == "all" or args.demo == "trajectory_reflection":
        demo_trajectory_reflection(tools_integration)
    
    if args.demo == "all" or args.demo == "memory_retrieval":
        demo_memory_retrieval(tools_integration)
    
    if args.demo == "all" or args.demo == "context_fusion":
        demo_context_fusion(tools_integration)
    
    if args.demo == "all" or args.demo == "evaluator":
        demo_evaluator(tools_integration)
        
    if args.demo == "all" or args.demo == "embedding":
        demo_embedding(tools_integration)

    if args.demo == "all" or args.demo == "query_formulator":
        demo_query_formulator(tools_integration)

if __name__ == "__main__":
    """Main function.
    python gui_agents/s2/tools/tools_demo.py -d grounding --config /Users/haoguangfu/Downloads/深维智能/客户方案/gui-agent/lybicguiagents/gui_agents/s2/tools/tools_config.json
    python gui_agents/s2/tools/tools_demo.py -d all --config /Users/haoguangfu/Downloads/深维智能/客户方案/gui-agent/lybicguiagents/gui_agents/s2/tools/tools_config.json
    python gui_agents/s2/tools/tools_demo.py -d embedding --config /Users/haoguangfu/Downloads/深维智能/客户方案/gui-agent/lybicguiagents/gui_agents/s2/tools/tools_config.json
    """
    main() 