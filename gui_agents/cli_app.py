import argparse
import datetime
import io
import logging
import os
import platform
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
from gui_agents.agents.agent_s import AgentS2, AgentSFast

from gui_agents.store.registry import Registry
from gui_agents.agents.global_state import GlobalState
from gui_agents.agents.hardware_interface import HardwareInterface

# Import analyze_display functionality
from gui_agents.utils.analyze_display import analyze_display_json, aggregate_results, format_output_line

current_platform = platform.system().lower()

# Display environment detection and backend compatibility validation
def check_display_environment():
    """
    Check if the current environment supports GUI operations.
    Returns (has_display, pyautogui_available, error_message)
    """
    has_display = False
    pyautogui_available = False
    error_message = None
    
    # Check DISPLAY environment variable (Linux/Unix)
    if current_platform == "linux":
        display_env = os.environ.get('DISPLAY')
        if display_env:
            has_display = True
        else:
            error_message = "No DISPLAY environment variable found. Running in headless/containerized environment."
    elif current_platform == "darwin":
        # macOS typically has display available unless running in special contexts
        has_display = True
    elif current_platform == "windows":
        # Windows typically has display available
        has_display = True
    
    # Try to import and initialize pyautogui if display is available
    if has_display:
        try:
            import pyautogui
            # Test if pyautogui can actually work
            pyautogui.size()  # This will fail if no display is available
            pyautogui_available = True
        except Exception as e:
            pyautogui_available = False
            error_message = f"PyAutoGUI not available: {str(e)}"
    
    return has_display, pyautogui_available, error_message

def get_compatible_backends(has_display, pyautogui_available):
    """
    Get list of backends compatible with current environment.
    """
    compatible_backends = []
    incompatible_backends = []
    
    # Lybic backend works in headless environments (cloud-based)
    compatible_backends.append("lybic")
    
    # ADB backend works without display (for Android devices)
    compatible_backends.append("adb")
    
    # PyAutoGUI-based backends require display
    if has_display and pyautogui_available:
        compatible_backends.extend(["pyautogui", "pyautogui_vmware"])
    else:
        incompatible_backends.extend(["pyautogui", "pyautogui_vmware"])
    
    return compatible_backends, incompatible_backends

def validate_backend_compatibility(backend, compatible_backends, incompatible_backends):
    """
    Validate if the requested backend is compatible with current environment.
    Returns (is_compatible, recommended_backend, warning_message)
    """
    if backend in compatible_backends:
        return True, backend, None
    elif backend in incompatible_backends:
        # Recommend lybic as the primary fallback for headless environments
        recommended = "lybic"
        warning = f"Backend '{backend}' is not compatible with current environment (no display/GUI). Recommending '{recommended}' backend instead."
        return False, recommended, warning
    else:
        # Unknown backend, let it fail naturally
        return True, backend, f"Unknown backend '{backend}', compatibility cannot be determined."

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


def auto_analyze_execution(timestamp_dir: str):
    """
    Automatically analyze execution statistics from display.json files after task completion
    
    Args:
        timestamp_dir: Directory containing the execution logs and display.json
    """
    import time
    
    try:
        # Analyze the display.json file for this execution
        display_json_path = os.path.join(timestamp_dir, "display.json")
        
        # Wait for file to be fully written
        max_wait_time = 10  # Maximum wait time in seconds
        wait_interval = 0.5  # Check every 0.5 seconds
        waited_time = 0
        
        while waited_time < max_wait_time:
            if os.path.exists(display_json_path):
                # Check if file is still being written by monitoring its size
                try:
                    size1 = os.path.getsize(display_json_path)
                    time.sleep(wait_interval)
                    size2 = os.path.getsize(display_json_path)
                    
                    # If file size hasn't changed in the last 0.5 seconds, it's likely complete
                    if size1 == size2:
                        logger.info(f"Display.json file appears to be complete (size: {size1} bytes)")
                        break
                    else:
                        logger.info(f"Display.json file still being written (size changed from {size1} to {size2} bytes)")
                        waited_time += wait_interval
                        continue
                except OSError:
                    # File might be temporarily inaccessible
                    time.sleep(wait_interval)
                    waited_time += wait_interval
                    continue
            else:
                logger.info(f"Waiting for display.json file to be created... ({waited_time:.1f}s)")
                time.sleep(wait_interval)
                waited_time += wait_interval
        
        if os.path.exists(display_json_path):
            logger.info(f"Auto-analyzing execution statistics from: {display_json_path}")
            
            # Analyze the single display.json file
            result = analyze_display_json(display_json_path)
            
            if result:
                # Format and log the statistics
                output_line = format_output_line(result)
                logger.info("=" * 80)
                logger.info("EXECUTION STATISTICS:")
                logger.info("Steps, Duration (seconds), (Input Tokens, Output Tokens, Total Tokens), Cost")
                logger.info("=" * 80)
                logger.info(output_line)
                logger.info("=" * 80)
                
                # Also print to console for immediate visibility
                print("\n" + "=" * 80)
                print("EXECUTION STATISTICS:")
                print("Steps, Duration (seconds), (Input Tokens, Output Tokens, Total Tokens), Cost")
                print("=" * 80)
                print(output_line)
                print("=" * 80)
            else:
                logger.warning("No valid data found in display.json for analysis")
        else:
            logger.warning(f"Display.json file not found at: {display_json_path} after waiting {max_wait_time} seconds")
            
    except Exception as e:
        logger.error(f"Error during auto-analysis: {e}")


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


def scale_screenshot_dimensions(screenshot: Image.Image, hwi_para: HardwareInterface):
    screenshot_high = screenshot.height
    screenshot_width = screenshot.width
    
    # Only try to scale if we have a PyAutoGUI backend and pyautogui is available
    try:
        from gui_agents.agents.Backend.PyAutoGUIBackend import PyAutoGUIBackend
        if isinstance(hwi_para.backend, PyAutoGUIBackend):
            import pyautogui
            screen_width, screen_height = pyautogui.size()
            if screen_width != screenshot_width or screen_height != screenshot_high:
                screenshot = screenshot.resize((screen_width, screen_height), Image.Resampling.LANCZOS)
    except Exception as e:
        # Any error (e.g., no display, import error), skip scaling
        logger.warning(f"Could not scale screenshot dimensions: {e}")

    return screenshot

def run_agent_normal(agent, instruction: str, hwi_para: HardwareInterface, max_steps: int = 50, enable_takeover: bool = False):
    import time
    obs = {}
    traj = "Task:\n" + instruction
    subtask_traj = ""
    global_state: GlobalState = Registry.get("GlobalStateStore") # type: ignore
    global_state.set_Tu(instruction)
    global_state.set_running_state("running")
    hwi = hwi_para

    total_start_time = time.time()
    for _ in range(max_steps):
        while global_state.get_running_state() == "stopped":
            user_input = input(
                "Agent execution is paused. Enter 'continue' to resume: ")
            if user_input == "continue":
                global_state.set_running_state("running")
                logger.info("Agent execution resumed by user")
                break
            time.sleep(0.5)

        screenshot: Image.Image = hwi.dispatch(Screenshot())  # type: ignore
        global_state.set_screenshot(
            scale_screenshot_dimensions(screenshot, hwi_para))  # type: ignore
        obs = global_state.get_obs_for_manager()

        predict_start = time.time()
        info, code = agent.predict(instruction=instruction, observation=obs)
        predict_time = time.time() - predict_start
        logger.info(
            f"[Step Timing] agent.predict execution time: {predict_time:.2f} seconds"
        )

        global_state.log_operation(module="agent",
                                   operation="agent.predict",
                                   data={"duration": predict_time})

        if "done" in code[0]["type"].lower() or "fail" in code[0]["type"].lower(
        ):
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

        if enable_takeover and "usertakeover" in code[0]["type"].lower():
            message = code[0].get("message", "need user takeover")
            logger.info(f"User takeover request: {message}")

            global_state.set_running_state("stopped")

            if platform.system() == "Darwin":
                os.system(
                    f'osascript -e \'display dialog "{message}" with title "User takeover request" buttons "Continue" default button "Continue"\''
                )
            elif platform.system() == "Linux":
                os.system(
                    f'zenity --info --title="User takeover request" --text="{message}" --width=300 --height=150'
                )

            logger.info("Agent execution paused waiting for user takeover")
            continue
        elif not enable_takeover and "usertakeover" in code[0]["type"].lower():
            logger.info(
                f"User takeover request received but takeover is disabled. Continuing execution."
            )
            continue

        else:
            time.sleep(1.0)
            logger.info(f"EXECUTING CODE: {code[0]}")

            step_dispatch_start = time.time()
            hwi.dispatchDict(code[0])
            step_dispatch_time = time.time() - step_dispatch_start
            logger.info(
                f"[Step Timing] hwi.dispatchDict execution time: {step_dispatch_time:.2f} seconds"
            )
            logger.info(f"HARDWARE INTERFACE: Executed")

            # Record executed code and time
            global_state.log_operation(module="hardware",
                                       operation="executing_code",
                                       data={"content": str(code[0])})
            global_state.log_operation(module="hardware",
                                       operation="hwi.dispatchDict",
                                       data={"duration": step_dispatch_time})

            time.sleep(1.0)

            # Update task and subtask trajectories and optionally the episodic memory
            traj += ("\n\nReflection:\n" + str(info.get("reflection", "")) +
                     "\n\n----------------------\n\nPlan:\n" +
                     info.get("executor_plan", ""))
            subtask_traj = agent.update_episodic_memory(info, subtask_traj)

    total_end_time = time.time()
    total_duration = total_end_time - total_start_time
    logger.info(
        f"[Total Timing] Total execution time for this task: {total_duration:.2f} seconds"
    )
    global_state.log_operation(module="other",
                               operation="total_execution_time",
                               data={"duration": total_duration})
    
    # Auto-analyze execution statistics after task completion
    timestamp_dir = os.path.join(log_dir, datetime_str)
    auto_analyze_execution(timestamp_dir)


def run_agent_fast(agent,
                   instruction: str,
                   hwi_para: HardwareInterface,
                   max_steps: int = 50,
                   enable_takeover: bool = False):
    import time
    obs = {}
    global_state: GlobalState = Registry.get("GlobalStateStore")  # type: ignore
    global_state.set_Tu(instruction)
    global_state.set_running_state("running")
    hwi = hwi_para

    total_start_time = time.time()
    for step in range(max_steps):
        while global_state.get_running_state() == "stopped":
            user_input = input(
                "Agent execution is paused. Enter 'continue' to resume: ")
            if user_input == "continue":
                global_state.set_running_state("running")
                logger.info("[Fast Mode] Agent execution resumed by user")
                break
            time.sleep(0.5)

        screenshot: Image.Image = hwi.dispatch(Screenshot())  # type: ignore
        global_state.set_screenshot(
            scale_screenshot_dimensions(screenshot, hwi_para))  # type: ignore
        obs = global_state.get_obs_for_manager()

        predict_start = time.time()
        info, code = agent.predict(instruction=instruction,
                                   observation=obs)
        predict_time = time.time() - predict_start
        logger.info(
            f"[Fast Mode] [Step {step+1}] Prediction time: {predict_time:.2f} seconds"
        )

        global_state.log_operation(module="agent_fast",
                                   operation="agent.predict_fast",
                                   data={
                                       "duration": predict_time,
                                       "step": step + 1
                                   })

        if "done" in code[0]["type"].lower() or "fail" in code[0]["type"].lower(
        ):
            logger.info(
                f"[Fast Mode] Task {'completed' if 'done' in code[0]['type'].lower() else 'failed'}"
            )
            if platform.system() == "Darwin":
                os.system(
                    f'osascript -e \'display dialog "Task Completed" with title "OpenACI Agent (Fast)" buttons "OK" default button "OK"\''
                )
            elif platform.system() == "Linux":
                os.system(
                    f'zenity --info --title="OpenACI Agent (Fast)" --text="Task Completed" --width=200 --height=100'
                )
            break

        if "wait" in code[0]["type"].lower():
            wait_duration = code[0].get("duration", 5000) / 1000
            logger.info(f"[Fast Mode] Waiting for {wait_duration} seconds")
            time.sleep(wait_duration)
            continue

        if enable_takeover and "usertakeover" in code[0]["type"].lower():
            message = code[0].get("message", "need user takeover")
            logger.info(f"[Fast Mode] User takeover request: {message}")

            global_state.set_running_state("stopped")

            if platform.system() == "Darwin":
                os.system(
                    f'osascript -e \'display dialog "{message}" with title "User takeover request (Fast)" buttons "Continue" default button "Continue"\''
                )
            elif platform.system() == "Linux":
                os.system(
                    f'zenity --info --title="User takeover request (Fast)" --text="{message}" --width=300 --height=150'
                )

            logger.info(
                "[Fast Mode] Agent execution paused waiting for user takeover")
            continue
        elif not enable_takeover and "usertakeover" in code[0]["type"].lower():
            logger.info(
                f"[Fast Mode] User takeover request received but takeover is disabled. Continuing execution."
            )
            continue

        logger.info(f"[Fast Mode] Executing action: {code[0]}")
        step_dispatch_start = time.time()
        hwi.dispatchDict(code[0])
        step_dispatch_time = time.time() - step_dispatch_start
        logger.info(
            f"[Fast Mode] Action execution time: {step_dispatch_time:.2f} seconds"
        )

        global_state.log_operation(module="hardware_fast",
                                   operation="executing_code_fast",
                                   data={
                                       "content": str(code[0]),
                                       "duration": step_dispatch_time,
                                       "step": step + 1
                                   })

        time.sleep(0.5)

    total_end_time = time.time()
    total_duration = total_end_time - total_start_time
    logger.info(
        f"[Fast Mode] Total execution time: {total_duration:.2f} seconds")
    global_state.log_operation(module="other",
                               operation="total_execution_time_fast",
                               data={"duration": total_duration})
    
    # Auto-analyze execution statistics after task completion
    timestamp_dir = os.path.join(log_dir, datetime_str)
    auto_analyze_execution(timestamp_dir)


def main():
    parser = argparse.ArgumentParser(description='GUI Agent CLI Application')
    parser.add_argument(
        '--backend',
        type=str,
        default='lybic',
        help='Backend to use (e.g., lybic, pyautogui, pyautogui_vmware)')
    parser.add_argument('--query',
                        type=str,
                        default='',
                        help='Initial query to execute')
    parser.add_argument('--max-steps',
                        type=int,
                        default=50,
                        help='Maximum number of steps to execute (default: 50)')
    parser.add_argument('--mode',
                        type=str,
                        default='normal',
                        choices=['normal', 'fast'],
                        help='Agent mode: normal or fast (default: normal)')
    parser.add_argument('--enable-takeover',
                        action='store_true',
                        help='Enable user takeover functionality')
    parser.add_argument(
        '--disable-search',
        action='store_true',
        help='Disable web search functionality (default: enabled)')
    parser.add_argument(
        '--lybic-sid',
        type=str,
        default=None,
        help='Lybic precreated sandbox ID (if not provided, will use LYBIC_PRECREATE_SID environment variable)')
    parser.add_argument(
        '--force-backend',
        action='store_true',
        help='Force the use of specified backend even if incompatible with current environment')
    args = parser.parse_args()

    # Check environment compatibility
    has_display, pyautogui_available, env_error = check_display_environment()
    compatible_backends, incompatible_backends = get_compatible_backends(has_display, pyautogui_available)
    
    # Log environment status
    logger.info(f"Environment check: Display available={has_display}, PyAutoGUI available={pyautogui_available}")
    if env_error:
        logger.info(f"Environment note: {env_error}")
    logger.info(f"Compatible backends: {compatible_backends}")
    if incompatible_backends:
        logger.info(f"Incompatible backends: {incompatible_backends}")
    
    # Validate backend compatibility
    is_compatible, recommended_backend, warning = validate_backend_compatibility(
        args.backend, compatible_backends, incompatible_backends)
    
    if not is_compatible and not args.force_backend:
        logger.warning(warning)
        logger.info(f"Switching from '{args.backend}' to '{recommended_backend}' backend")
        args.backend = recommended_backend
    elif not is_compatible and args.force_backend:
        logger.warning(f"Forcing incompatible backend '{args.backend}' - this may cause errors")
    elif warning:
        logger.info(warning)

    # Ensure necessary directory structure exists
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
            completed_subtasks_path=os.path.join(state_dir,
                                                 "completed_subtasks.json"),
            failed_subtasks_path=os.path.join(state_dir,
                                              "failed_subtasks.json"),
            remaining_subtasks_path=os.path.join(state_dir,
                                                 "remaining_subtasks.json"),
            termination_flag_path=os.path.join(state_dir,
                                               "termination_flag.json"),
            running_state_path=os.path.join(state_dir, "running_state.json"),
            display_info_path=os.path.join(timestamp_dir, "display.json"),
            agent_log_path=os.path.join(timestamp_dir, "agent_log.json")))
    global current_platform
    # Set platform to Windows if backend is lybic
    if args.backend == 'lybic':
        current_platform = 'windows'

    # Initialize agent based on mode
    if args.mode == 'fast':
        agent = AgentSFast(
            platform=current_platform,
            enable_takeover=args.enable_takeover,
            enable_search=not args.disable_search,
        )
        logger.info("Running in FAST mode")
        run_agent_func = run_agent_fast
    else:
        agent = AgentS2(
            platform=current_platform,
            enable_takeover=args.enable_takeover,
            enable_search=not args.disable_search,
        )
        logger.info("Running in NORMAL mode with full agent")
        run_agent_func = run_agent_normal

    # Log whether user takeover is enabled
    if args.enable_takeover:
        logger.info("User takeover functionality is ENABLED")
    else:
        logger.info("User takeover functionality is DISABLED")

    # Log whether web search is enabled
    if args.disable_search:
        logger.info("Web search functionality is DISABLED")
    else:
        logger.info("Web search functionality is ENABLED")

    # Initialize hardware interface with error handling
    backend_kwargs = {"platform": platform_os}
    if args.lybic_sid is not None:
        backend_kwargs["precreate_sid"] = args.lybic_sid
        logger.info(f"Using Lybic SID from command line: {args.lybic_sid}")
    else:
        logger.info("Using Lybic SID from environment variable LYBIC_PRECREATE_SID")
    
    try:
        hwi = HardwareInterface(backend=args.backend, **backend_kwargs)
        logger.info(f"Successfully initialized hardware interface with backend: {args.backend}")
    except Exception as e:
        logger.error(f"Failed to initialize hardware interface with backend '{args.backend}': {e}")
        
        # If the backend failed and it's a GUI-dependent backend, suggest alternatives
        if args.backend in incompatible_backends and not args.force_backend:
            logger.info("Attempting to initialize with lybic backend as fallback...")
            try:
                hwi = HardwareInterface(backend="lybic", **backend_kwargs)
                logger.info("Successfully initialized with lybic backend")
                args.backend = "lybic"
            except Exception as fallback_error:
                logger.error(f"Fallback to lybic backend also failed: {fallback_error}")
                sys.exit(1)
        else:
            logger.error("Hardware interface initialization failed. Please check your environment and backend configuration.")
            sys.exit(1)

    # if query is provided, run the agent on the query
    if args.query:
        agent.reset()
        run_agent_func(agent, args.query, hwi, args.max_steps,
                       args.enable_takeover)

    else:
        while True:
            query = input("Query: ")

            agent.reset()

            # Run the agent on your own device
            run_agent_func(agent, query, hwi, args.max_steps, args.enable_takeover)

            response = input("Would you like to provide another query? (y/n): ")
            if response.lower() != "y":
                break


if __name__ == "__main__":
    """
    GUI Agent CLI Application with environment compatibility checking.
    
    The application automatically detects the current environment and recommends compatible backends:
    - In headless/containerized environments: uses 'lybic' or 'adb' backends
    - In GUI environments: supports all backends including 'pyautogui' and 'pyautogui_vmware'
    
    Examples:
    python gui_agents/cli_app.py --backend lybic
    python gui_agents/cli_app.py --backend pyautogui --mode fast
    python gui_agents/cli_app.py --backend pyautogui_vmware
    python gui_agents/cli_app.py --backend lybic --max-steps 15
    python gui_agents/cli_app.py --backend lybic --mode fast --enable-takeover
    python gui_agents/cli_app.py --backend lybic --disable-search
    python gui_agents/cli_app.py --backend pyautogui --mode fast --disable-search
    python gui_agents/cli_app.py --backend lybic --lybic-sid SBX-01K1X6ZKAERXAN73KTJ1XXJXAF
    python gui_agents/cli_app.py --backend lybic --mode fast --lybic-sid SBX-01K1X6ZKAERXAN73KTJ1XXJXAF
    python gui_agents/cli_app.py --backend pyautogui --force-backend  # Force incompatible backend
    """
    main()
