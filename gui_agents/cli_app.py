import argparse
import datetime
import io
import logging
import os
import platform
import pyautogui
import sys
import time
import datetime
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(os.path.dirname(os.path.abspath(__file__))) / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    parent_env_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / '.env'
    if parent_env_path.exists():
        load_dotenv(dotenv_path=parent_env_path)

from PIL import Image

# from gui_agents.agents.grounding import OSWorldACI
from gui_agents.agents.Action import Screenshot
from gui_agents.agents.agent_s import AgentS2

from gui_agents.store.registry import Registry
from gui_agents.agents.global_state import GlobalState
from gui_agents.agents.hardware_interface import HardwareInterface

current_platform = platform.system().lower()

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

datetime_str: str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

log_dir = "runtime"
os.makedirs(os.path.join(log_dir, datetime_str), exist_ok=True)

file_handler = logging.FileHandler(
    os.path.join(log_dir, datetime_str, "normal.log"), encoding="utf-8"
)
debug_handler = logging.FileHandler(
    os.path.join(log_dir, datetime_str, "debug.log"), encoding="utf-8"
)
stdout_handler = logging.StreamHandler(sys.stdout)
sdebug_handler = logging.FileHandler(
    os.path.join(log_dir, datetime_str, "sdebug.log"), encoding="utf-8"
)

file_handler.setLevel(logging.INFO)
debug_handler.setLevel(logging.DEBUG)
stdout_handler.setLevel(logging.INFO)
sdebug_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    fmt="\x1b[1;33m[%(asctime)s \x1b[31m%(levelname)s \x1b[32m%(module)s/%(lineno)d-%(processName)s\x1b[1;33m] \x1b[0m%(message)s"
)
file_handler.setFormatter(formatter)
debug_handler.setFormatter(formatter)
stdout_handler.setFormatter(formatter)
sdebug_handler.setFormatter(formatter)

stdout_handler.addFilter(logging.Filter("desktopenv"))
sdebug_handler.addFilter(logging.Filter("desktopenv"))

logger.addHandler(file_handler)
logger.addHandler(debug_handler)
logger.addHandler(stdout_handler)
logger.addHandler(sdebug_handler)

platform_os = platform.system()


def show_permission_dialog(code: str, action_description: str):
    """Show a platform-specific permission dialog and return True if approved."""
    if platform.system() == "Darwin":
        result = os.system(
            f'osascript -e \'display dialog "Do you want to execute this action?\n\n{code} which will try to {action_description}" with title "Action Permission" buttons {{"Cancel", "OK"}} default button "OK" cancel button "Cancel"\''
        )
        return result == 0
    elif platform.system() == "Linux":
        result = os.system(
            f'zenity --question --title="Action Permission" --text="Do you want to execute this action?\n\n{code}" --width=400 --height=200'
        )
        return result == 0
    return False


def scale_screen_dimensions(width: int, height: int, max_dim_size: int):
    scale_factor = min(max_dim_size / width, max_dim_size / height, 1)
    safe_width = int(width * scale_factor)
    safe_height = int(height * scale_factor)
    return safe_width, safe_height


def run_agent(agent, instruction: str, scaled_width: int, scaled_height: int):
    import time  # Ensure time is imported
    obs = {}
    traj = "Task:\n" + instruction
    subtask_traj = ""
    global_state: GlobalState = Registry.get("GlobalStateStore") # type: ignore
    global_state.set_Tu(instruction)
    hwi = HardwareInterface(backend="pyautogui", platform=platform_os)
    
    total_start_time = time.time()  # Record total start time
    for _ in range(15):
        # Get screen shot using pyautogui
        screenshot: Image.Image = hwi.dispatch(Screenshot()) # type: ignore
        # w, h = screenshot.size  
        # screenshot = pyautogui.screenshot()
        screenshot = screenshot.resize((scaled_width, scaled_height), Image.LANCZOS) # type: ignore
        global_state.set_screenshot(screenshot)
        obs = global_state.get_obs_for_manager()

        # Time predict step
        info, code = agent.predict(instruction=instruction, observation=obs)

        if "done" in code[0]["type"].lower() or "fail" in code[0]["type"].lower():
            if platform.system() == "Darwin":
                os.system(
                    f'osascript -e \'display dialog "Task Completed" with title "OpenACI Agent" buttons "OK" default button "OK"\''
                )
            elif platform.system() == "Linux":
                os.system(
                    f'zenity --info --title="OpenACI Agent" --text="Task Completed" --width=200 --height=100'
                )

            agent.update_narrative_memory(traj)
            break

        if "next" in code[0]["type"].lower():
            continue

        if "wait" in code[0]["type"].lower():
            time.sleep(5)
            continue

        else:
            time.sleep(1.0)
            logger.info(f"EXECUTING CODE: {code[0]}")

            # Time dispatchDict step
            step_dispatch_start = time.time()
            hwi.dispatchDict(code[0])
            step_dispatch_time = time.time() - step_dispatch_start
            logger.info(f"[Step Timing] hwi.dispatchDict execution time: {step_dispatch_time:.2f} seconds")
            logger.info(f"HARDWARE INTERFACE: Executed")
            
            # 记录执行的代码和时间
            global_state.log_operation(
                module="hardware",
                operation="executing_code", 
                data={"content": str(code[0])}
            )
            global_state.log_operation(
                module="hardware",
                operation="hwi.dispatchDict", 
                data={"duration": step_dispatch_time}
            )

            time.sleep(1.0)

            # Update task and subtask trajectories and optionally the episodic memory
            traj += (
                "\n\nReflection:\n"
                + str(info["reflection"])
                + "\n\n----------------------\n\nPlan:\n"
                + info["executor_plan"]
            )
            subtask_traj = agent.update_episodic_memory(info, subtask_traj)
    
    total_end_time = time.time()
    total_duration = total_end_time - total_start_time
    logger.info(f"[Total Timing] Total execution time for this task: {total_duration:.2f} seconds")
    global_state.log_operation(
        module="other",
        operation="total_execution_time", 
        data={"duration": total_duration}
    )
    
    # 确保所有日志记录都已合并
    global_state.consolidate_display_info()


def main():
    
    # Re-scales screenshot size to ensure it fits in UI-TARS context limit
    screen_width, screen_height = pyautogui.size()
    scaled_width, scaled_height = screen_width, screen_height

    # 确保必要的目录结构存在
    timestamp_dir = os.path.join(log_dir, datetime_str)
    cache_dir = os.path.join(timestamp_dir, "cache", "screens")
    state_dir = os.path.join(timestamp_dir, "state")
    
    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(state_dir, exist_ok=True)

    Registry.register(
        "GlobalStateStore",
        GlobalState(
            screenshot_dir=cache_dir,
            tu_path=os.path.join(state_dir, "tu.json"),
            search_query_path=os.path.join(state_dir, "search_query.json"),
            completed_subtasks_path=os.path.join(state_dir, "completed_subtasks.json"),
            failed_subtasks_path=os.path.join(state_dir, "failed_subtasks.json"),
            remaining_subtasks_path=os.path.join(state_dir, "remaining_subtasks.json"),
            termination_flag_path=os.path.join(state_dir, "termination_flag.json"),
            running_state_path=os.path.join(state_dir, "running_state.json"),
            display_info_path=os.path.join(timestamp_dir, "display.json"),
        )
    )
    global current_platform
    agent = AgentS2(
        platform=current_platform,
        screen_size = [scaled_width, scaled_height]
    )

    while True:
        query = input("Query: ")

        agent.reset()

        # Run the agent on your own device
        run_agent(agent, query, scaled_width, scaled_height)

        response = input("Would you like to provide another query? (y/n): ")
        if response.lower() != "y":
            break


if __name__ == "__main__":
    main()
