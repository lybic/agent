#!/usr/bin/env python3
"""
Test script for NewManager module
Tests all functionality step by step without traditional unit test framework
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import platform
from dotenv import load_dotenv

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

env_path = Path(os.path.dirname(os.path.abspath(__file__))) / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    parent_env_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / '.env'
    if parent_env_path.exists():
        load_dotenv(dotenv_path=parent_env_path)

from gui_agents.maestro.new_manager import NewManager, PlanningScenario, PlanningResult
from gui_agents.maestro.new_global_state import NewGlobalState
from gui_agents.maestro.enums import TaskStatus, SubtaskStatus, ManagerStatus
from gui_agents.maestro.new_controller import NewController
from gui_agents.store.registry import Registry


def main():
    # Prepare temporary runtime directories
    temp_root = Path(__file__).parent / "new_controller_test_temp"
    temp_root.mkdir(exist_ok=True)
    cache_dir = temp_root / "cache" / "screens"
    state_dir = temp_root / "state"
    cache_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)

    user_query_input = "帮我打开bilibili"

    try:
        # Initialize NewGlobalState
        global_state = NewGlobalState(
            screenshot_dir=str(cache_dir),
            state_dir=str(state_dir),
            agent_log_path=str(temp_root / "agent_log.json"),
            display_info_path=str(temp_root / "display.json"),
        )
        Registry.register(
        "GlobalStateStore", global_state)

        # Initialize NewController
        controller = NewController(
            platform=platform.system().lower(),
            memory_root_path=os.getcwd(),
            backend="pyautogui",
            enable_search=False,
            enable_takeover=False,
            user_query=user_query_input,
        )

        # Print controller info to verify initialization
        info = controller.get_controller_info()
        print(info)
        controller.execute_single_step(steps=2)
    finally:
        # Clean up temp directories
        pass
        # shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    """
    python gui_agents/unit_test/test_new_manager.py
    """
    main()