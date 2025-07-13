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

from PIL import Image

# from gui_agents.s2.agents.grounding import OSWorldACI
from gui_agents.s2.agents.agent_s import AgentS2

from gui_agents.s2.store.registry import Registry
from gui_agents.s2.agents.global_state import GlobalState
from gui_agents.s2.agents.hardware_interface import HardwareInterface

current_platform = platform.system().lower()

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

datetime_str: str = datetime.datetime.now().strftime("%Y%m%d@%H%M%S")

log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

file_handler = logging.FileHandler(
    os.path.join("logs", "normal-{:}.log".format(datetime_str)), encoding="utf-8"
)
debug_handler = logging.FileHandler(
    os.path.join("logs", "debug-{:}.log".format(datetime_str)), encoding="utf-8"
)
stdout_handler = logging.StreamHandler(sys.stdout)
sdebug_handler = logging.FileHandler(
    os.path.join("logs", "sdebug-{:}.log".format(datetime_str)), encoding="utf-8"
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
    obs = {}
    traj = "Task:\n" + instruction
    subtask_traj = ""
    global_state: GlobalState = Registry.get("GlobalStateStore")
    global_state.set_Tu(instruction)
    hwi = HardwareInterface(backend="pyautogui", platform=platform_os)
    for _ in range(15):
        # Get screen shot using pyautogui
        screenshot = pyautogui.screenshot()
        screenshot = screenshot.resize((scaled_width, scaled_height), Image.LANCZOS)
        global_state.set_screenshot(screenshot)
        obs = global_state.get_obs_for_manager()

        # Get next action code from the agent
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

            # Ask for permission before executing
            # exec(code[0])
            hwi.dispatchDict(code[0])
            logger.info(f"HARDWARE INTERFACE: Executed")

            time.sleep(1.0)

            # Update task and subtask trajectories and optionally the episodic memory
            traj += (
                "\n\nReflection:\n"
                + str(info["reflection"])
                + "\n\n----------------------\n\nPlan:\n"
                + info["executor_plan"]
            )
            subtask_traj = agent.update_episodic_memory(info, subtask_traj)


def main():
    parser = argparse.ArgumentParser(description="Run AgentS2 with specified model.")
    parser.add_argument(
        "--provider",
        type=str,
        default="anthropic",
        help="Specify the provider to use (e.g., openai, anthropic, etc.)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="claude-3-7-sonnet-20250219",
        help="Specify the model to use (e.g., gpt-4o)",
    )
    parser.add_argument(
        "--model_url",
        type=str,
        default="",
        help="The URL of the main generation model API.",
    )
    parser.add_argument(
        "--model_api_key",
        type=str,
        default="",
        help="The API key of the main generation model.",
    )

    # Grounding model config option 1: API based
    parser.add_argument(
        "--grounding_model_provider",
        type=str,
        default="anthropic",
        help="Specify the provider to use for the grounding model (e.g., openai, anthropic, etc.)",
    )
    parser.add_argument(
        "--grounding_model",
        type=str,
        default="claude-3-7-sonnet-20250219",
        help="Specify the grounding model to use (e.g., claude-3-5-sonnet-20241022)",
    )
    parser.add_argument(
        "--grounding_model_resize_width",
        type=int,
        default=1366,
        help="Width of screenshot image after processor rescaling",
    )
    parser.add_argument(
        "--grounding_model_resize_height",
        type=int,
        default=None,
        help="Height of screenshot image after processor rescaling",
    )

    # Grounding model config option 2: Self-hosted endpoint based
    parser.add_argument(
        "--endpoint_provider",
        type=str,
        default="",
        help="Specify the endpoint provider for your grounding model, only HuggingFace TGI support for now",
    )
    parser.add_argument(
        "--endpoint_url",
        type=str,
        default="",
        help="Specify the endpoint URL for your grounding model",
    )
    parser.add_argument(
        "--endpoint_api_key",
        type=str,
        default="",
        help="The API key of the grounding model.",
    )

    parser.add_argument(
        "--embedding_engine_type",
        type=str,
        default="openai",
        help="Specify the embedding engine type (supports openai, gemini)",
    )

    args = parser.parse_args()
    assert (
        args.grounding_model_provider and args.grounding_model
    ) or args.endpoint_url, "Error: No grounding model was provided. Either provide an API based model, or a self-hosted HuggingFace endpoint"

    # Re-scales screenshot size to ensure it fits in UI-TARS context limit
    screen_width, screen_height = pyautogui.size()
    scaled_width, scaled_height = scale_screen_dimensions(
        screen_width, screen_height, max_dim_size=2400
    )
    # Load the general engine params
    engine_params = {
        "engine_type": args.provider,
        "model": args.model,
        "base_url": args.model_url,
        "api_key": args.model_api_key,
    }

    # # Load the grounding engine from a HuggingFace TGI endpoint
    # if args.endpoint_url:
    #     engine_params_for_grounding = {
    #         "engine_type": args.endpoint_provider,
    #         "base_url": args.endpoint_url,
    #         "api_key": args.endpoint_api_key,
    #     }
    # else:
    #     grounding_height = args.grounding_model_resize_height
    #     # If not provided, use the aspect ratio of the screen to compute the height
    #     if grounding_height is None:
    #         grounding_height = (
    #             screen_height * args.grounding_model_resize_width / screen_width
    #         )

    #     engine_params_for_grounding = {
    #         "engine_type": args.grounding_model_provider,
    #         "model": args.grounding_model,
    #         "grounding_width": args.grounding_model_resize_width,
    #         "grounding_height": grounding_height,
    #     }

    # grounding_agent = OSWorldACI(
    #     platform=current_platform,
    #     engine_params_for_generation=engine_params,
    #     engine_params_for_grounding=engine_params_for_grounding,
    #     width=screen_width,
    #     height=screen_height,
    # )

    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    runtime_dir = f"runtime/{now_str}"

    Registry.register(
        "GlobalStateStore",
        GlobalState(
            screenshot_dir=os.path.join(runtime_dir, "cache", "screens"),
            tu_path=os.path.join(runtime_dir, "state", "tu.json"),
            search_query_path=os.path.join(runtime_dir, "state", "search_query.json"),
            completed_subtask_path=os.path.join(runtime_dir, "state", "completed_subtask.json"),
            failed_subtask_path=os.path.join(runtime_dir, "state", "failed_subtask.json"),
            remaining_subtask_path=os.path.join(runtime_dir, "state", "remaining_subtask.json"),
            termination_flag_path=os.path.join(runtime_dir, "state", "termination_flag.json"),
            running_state_path=os.path.join(runtime_dir, "state", "running_state.json"),
        )
    )

    agent = AgentS2(
        engine_params,
        # grounding_agent,
        platform=current_platform,
        action_space="pyautogui",
        observation_type="mixed",
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
