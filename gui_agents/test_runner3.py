"""Automated test runner for agents3 using original osworld test configurations."""

import argparse
import datetime
import json
import logging
import os
import platform
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv
from tqdm import tqdm

from desktop_env.desktop_env import DesktopEnv

# Load environment variables
env_path = Path(os.path.dirname(os.path.abspath(__file__))) / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    parent_env_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / '.env'
    if parent_env_path.exists():
        load_dotenv(dotenv_path=parent_env_path)

from PIL import Image

# Import agents3 modules
from gui_agents.agents3.new_global_state import NewGlobalState
from gui_agents.agents3.new_controller import NewController

# Import analyze_display functionality
from gui_agents.utils.analyze_display import analyze_display_json, aggregate_results, format_output_line
from gui_agents.utils.common_utils import show_task_completion_notification

# Set platform from environment variable, similar to cli_app3.py
current_platform = os.getenv("USE_PRECREATE_VM", "Windows")

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

test_datetime_str: str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

log_dir = "runtime"
os.makedirs(os.path.join(log_dir, f"test_{test_datetime_str}"), exist_ok=True)

file_handler = logging.FileHandler(
    os.path.join(log_dir, f"test_{test_datetime_str}", "test_runner3.log"), encoding="utf-8"
)
debug_handler = logging.FileHandler(
    os.path.join(log_dir, f"test_{test_datetime_str}", "test_runner3_debug.log"), encoding="utf-8"
)
stdout_handler = logging.StreamHandler(sys.stdout)

file_handler.setLevel(logging.INFO)
debug_handler.setLevel(logging.DEBUG)
stdout_handler.setLevel(logging.INFO)

formatter = logging.Formatter(
    fmt="\x1b[1;33m[%(asctime)s \x1b[31m%(levelname)s \x1b[32m%(module)s/%(lineno)d-%(processName)s\x1b[1;33m] \x1b[0m%(message)s"
)
file_handler.setFormatter(formatter)
debug_handler.setFormatter(formatter)
stdout_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(debug_handler)
logger.addHandler(stdout_handler)


def setup_example_logger(example_id: str, example_timestamp_dir: str):
    """Set up a separate logger for each test example"""
    example_logger = logging.getLogger(
        f"example.{example_id}.{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    example_logger.setLevel(logging.DEBUG)
    
    # Clear existing handlers
    example_logger.handlers.clear()
    
    log_file = os.path.join(example_timestamp_dir, "example.log")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    
    debug_log_file = os.path.join(example_timestamp_dir, "example_debug.log")
    debug_handler = logging.FileHandler(debug_log_file, encoding="utf-8")
    debug_handler.setLevel(logging.DEBUG)
    
    formatter = logging.Formatter(
        fmt="\x1b[1;33m[%(asctime)s \x1b[31m%(levelname)s \x1b[32m%(module)s/%(lineno)d-%(processName)s\x1b[1;33m] \x1b[0m%(message)s"
    )
    file_handler.setFormatter(formatter)
    debug_handler.setFormatter(formatter)
    
    example_logger.addHandler(file_handler)
    example_logger.addHandler(debug_handler)
    
    return example_logger


def auto_analyze_execution(timestamp_dir: str):
    """
    Automatically analyze execution statistics from display.json files after task completion
    
    Args:
        timestamp_dir: Directory containing the execution logs and display.json
    """
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
                
                return result
            else:
                logger.warning("No valid data found in display.json for analysis")
        else:
            logger.warning(f"Display.json file not found at: {display_json_path} after waiting {max_wait_time} seconds")
            
    except Exception as e:
        logger.error(f"Error during auto-analysis: {e}")
    
    return None





def run_single_test_with_agents3(
    controller,
    env,
    example: dict,
    max_steps: int,
    instruction: str,
    args,
    example_result_dir: str,
    scores: list,
    example_timestamp_dir: str,
) -> float:
    """Run a single test using agents3 architecture with osworld compatibility"""
    from osworld_setup.lib_run_single import run_single_example
    
    try:
        # Use the original osworld run_single_example function but with agents3 controller
        result = run_single_example(
            env=env,
            controller=controller,  # Pass our agents3 controller
            example=example,
            max_steps=max_steps,
            instruction=instruction,
            args=args,
            example_result_dir=example_result_dir,
        )
        
        # Extract score from result
        if isinstance(result, dict) and "score" in result:
            score = result["score"]
        elif isinstance(result, (int, float)):
            score = float(result)
        else:
            score = 1.0 if result else 0.0
            
        scores.append(score)
        
        # Analyze execution statistics using agents3 analysis
        display_json_path = os.path.join(example_timestamp_dir, "display.json")
        analysis_result = auto_analyze_execution(display_json_path)
        
        # Save additional metadata with agents3 analysis
        metadata = {
            "instruction": instruction,
            "max_steps": max_steps,
            "score": score,
            "timestamp": datetime.datetime.now().isoformat(),
            "agents3_analysis": analysis_result
        }
        
        metadata_file = os.path.join(example_result_dir, "agents3_metadata.json")
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Test completed with score: {score}")
        return score
        
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        scores.append(0.0)
        
        # Save error information
        with open(os.path.join(example_result_dir, "error.txt"), "w", encoding="utf-8") as f:
            f.write(f"Error: {str(e)}\n")
        
        return 0.0





def get_unfinished(
    action_space, observation_type, result_dir, total_file_json
):
    target_dir = os.path.join(result_dir, action_space, observation_type)

    if not os.path.exists(target_dir):
        return total_file_json

    finished = {}
    for domain in os.listdir(target_dir):
        finished[domain] = []
        domain_path = os.path.join(target_dir, domain)
        if os.path.isdir(domain_path):
            for example_id in os.listdir(domain_path):
                if example_id == "onboard":
                    continue
                example_path = os.path.join(domain_path, example_id)
                if os.path.isdir(example_path):
                    if "result.txt" not in os.listdir(example_path):
                        # empty all files under example_id
                        for file in os.listdir(example_path):
                            os.remove(os.path.join(example_path, file))
                    else:
                        finished[domain].append(example_id)

    if not finished:
        return total_file_json

    for domain, examples in finished.items():
        if domain in total_file_json:
            total_file_json[domain] = [
                x for x in total_file_json[domain] if x not in examples
            ]

    return total_file_json


def get_result(action_space, observation_type, result_dir, total_file_json):
    target_dir = os.path.join(result_dir, action_space, observation_type)
    if not os.path.exists(target_dir):
        print("New experiment, no result yet.")
        return None

    all_result = []

    for domain in os.listdir(target_dir):
        domain_path = os.path.join(target_dir, domain)
        if os.path.isdir(domain_path):
            for example_id in os.listdir(domain_path):
                example_path = os.path.join(domain_path, example_id)
                if os.path.isdir(example_path):
                    if "result.txt" in os.listdir(example_path):
                        # empty all files under example_id
                        try:
                            all_result.append(
                                float(
                                    open(
                                        os.path.join(example_path, "result.txt"), "r"
                                    ).read()
                                )
                            )
                        except:
                            all_result.append(0.0)

    if not all_result:
        print("New experiment, no result yet.")
        return None
    else:
        print("Current Success Rate:", sum(all_result) / len(all_result) * 100, "%")
        return all_result


def test(args: argparse.Namespace, test_all_meta: dict) -> None:
    scores = []
    max_steps = args.max_steps
    scaled_width, scaled_height = args.screen_width, args.screen_height

    # log args
    logger.info("Args: %s", args)
    cfg_args = {
        "path_to_vm": args.path_to_vm,
        "headless": args.headless,
        "action_space": args.action_space,
        "observation_type": args.observation_type,
        "screen_width": args.screen_width,
        "screen_height": args.screen_height,
        "sleep_after_execution": args.sleep_after_execution,
        "max_steps": args.max_steps,
        "result_dir": args.result_dir,
    }

    env = DesktopEnv(
        provider_name="vmware",
        path_to_vm=args.path_to_vm,
        os_type=current_platform,
        action_space=args.action_space,
        headless=args.headless,
        require_a11y_tree=False,
    )

    for domain in tqdm(test_all_meta, desc="Domain"):
        for example_id in tqdm(test_all_meta[domain], desc="Example", leave=False):
            # Choose config directory based on platform, similar to cli_app3.py logic
            if current_platform == "Ubuntu":
                config_subdir = "examples"
            else:  # Windows
                config_subdir = "examples_windows"
            
            config_file = os.path.join(
                args.test_config_base_dir, f"{config_subdir}/{domain}/{example_id}.json"
            )
            with open(config_file, "r", encoding="utf-8") as f:
                example = json.load(f)

            logger.info(f"[Domain]: {domain}")
            logger.info(f"[Example ID]: {example_id}")

            instruction = example["instruction"]

            logger.info(f"[Instruction]: {instruction}")
            # wandb each example config settings
            cfg_args["instruction"] = instruction
            cfg_args["start_time"] = datetime.datetime.now().strftime(
                "%Y:%m:%d-%H:%M:%S"
            )

            # Create a separate timestamp folder for each example
            example_datetime_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            example_timestamp_dir = os.path.join(log_dir, f"test_{test_datetime_str}", example_datetime_str)
            example_cache_dir = os.path.join(example_timestamp_dir, "cache", "screens")
            example_state_dir = os.path.join(example_timestamp_dir, "state")
            
            os.makedirs(example_cache_dir, exist_ok=True)
            os.makedirs(example_state_dir, exist_ok=True)

            # Initialize agents3 components for each example
            global_state = NewGlobalState(
                screenshot_dir=example_cache_dir,
                state_dir=example_state_dir,
                agent_log_path=os.path.join(example_timestamp_dir, "agent_log.json"),
                display_info_path=os.path.join(example_timestamp_dir, "display.json")
            )
            
            # Initialize NewController with agents3 architecture
            controller = NewController(
                platform=current_platform,
                backend="pyautogui_vmware",  # Use vmware backend for osworld compatibility
                user_query=instruction,
                max_steps=max_steps,
                env=env,
                env_password="password",
                log_dir=log_dir,
                datetime_str=test_datetime_str
            )
            
            example_result_dir = os.path.join(
                args.result_dir,
                args.action_space,
                args.observation_type,
                domain,
                example_id,
            )
            os.makedirs(example_result_dir, exist_ok=True)
            
            # example start running
            try:
                result_score = run_single_test_with_agents3(
                    controller,
                    env,
                    example,
                    max_steps,
                    instruction,
                    args,
                    example_result_dir,
                    scores,
                    example_timestamp_dir,
                )
            except Exception as e:
                logger.error(f"Exception in {domain}/{example_id}: {e}")
                # env.controller.end_recording(
                #     os.path.join(example_result_dir, "recording.mp4")
                # )
                with open(os.path.join(example_result_dir, "traj.jsonl"), "a") as f:
                    f.write(
                        json.dumps(
                            {"Error": f"Time limit exceeded in {domain}/{example_id}"}
                        )
                    )
                    f.write("\n")

    env.close()
    logger.info(f"Average score: {sum(scores) / len(scores)}")


def config() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run end-to-end evaluation on the benchmark using agents3"
    )

    # Platform is now determined from environment variable USE_PRECREATE_VM
    # No need for platform argument, following cli_app3.py pattern

    # environment config
    # vm_path will be set based on platform
    parser.add_argument("--path_to_vm", type=str, default=None)
    parser.add_argument(
        "--headless", action="store_true", help="Run in headless machine"
    )
    parser.add_argument(
        "--action_space", type=str, default="pyautogui", help="Action type"
    )
    parser.add_argument(
        "--observation_type",
        choices=["screenshot", "a11y_tree", "screenshot_a11y_tree", "som"],
        default="screenshot",
        help="Observation type",
    )
    parser.add_argument("--screen_width", type=int, default=1920)
    parser.add_argument("--screen_height", type=int, default=1080)
    parser.add_argument("--sleep_after_execution", type=float, default=1.0)
    parser.add_argument("--max_steps", type=int, default=50)

    # agent config
    parser.add_argument(
        "--test_config_base_dir", type=str, default="evaluation_examples"
    )

    # example config
    parser.add_argument("--domain", type=str, default="all")
    parser.add_argument(
        "--test_all_meta_path", type=str, default=None
    )

    # logging related
    parser.add_argument("--result_dir", type=str, default="./results")

    parser.add_argument("--kb_name", default="kb_s2", type=str)

    args = parser.parse_args()

    # Set platform-specific defaults if not provided, using global current_platform
    if args.path_to_vm is None:
        if current_platform == "Ubuntu":
            # Use the same logic as cli_app3.py for Ubuntu platform
            cpu_arch = platform.machine().lower()
            if cpu_arch in ['x86_64', 'amd64', 'i386', 'i686']:
                args.path_to_vm = os.path.join("vmware_vm_data", "Ubuntu-x86", "Ubuntu.vmx")
            elif cpu_arch in ['arm64', 'aarch64']:
                args.path_to_vm = os.path.join("vmware_vm_data", "Ubuntu-arm", "Ubuntu.vmx")
            else:
                raise ValueError(f"Unsupported CPU architecture: {cpu_arch}")
        else:  # Windows
            args.path_to_vm = os.path.join("vmware_vm_data", "Windows-x86", "Windows 10 x64.vmx")
    
    if args.test_all_meta_path is None:
        if current_platform == "Ubuntu":
            args.test_all_meta_path = "osworld_setup/test_tiny.json"
        else:  # Windows
            args.test_all_meta_path = "osworld_setup/test_tiny_windows.json"

    return args


def main():
    """Main entry point"""
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    args = config()

    with open(args.test_all_meta_path, "r", encoding="utf-8") as f:
        test_all_meta = json.load(f)

    if args.domain != "all":
        test_all_meta = {args.domain: test_all_meta[args.domain]}

    test_file_list = get_unfinished(
        args.action_space,
        args.observation_type,
        args.result_dir,
        test_all_meta,
    )
    
    if not test_file_list or all(len(examples) == 0 for examples in test_file_list.values()):
        logger.info("All tests are completed")
        get_result(
            args.action_space,
            args.observation_type,
            args.result_dir,
            test_all_meta,
        )
        return
    
    left_info = ""
    for domain in test_file_list:
        left_info += f"{domain}: {len(test_file_list[domain])} "
    logger.info(f"Left: {left_info}")

    # Run tests using agents3 architecture
    test(args, test_file_list)
    
    # Get final results after test completion
    get_result(
        args.action_space,
        args.observation_type,
        args.result_dir,
        test_all_meta,
    )


if __name__ == "__main__":
    """
    Usage examples:
    python gui_agents/test_runner3.py --max_steps 30 --test_all_meta_path evaluation_examples/test_tiny.json
    """
    main()