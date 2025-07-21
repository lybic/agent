import datetime
import json
import logging
import os
import time
import io
from typing import Optional
# from wrapt_timeout_decorator import *
from PIL import Image
from gui_agents.store.registry import Registry
from gui_agents.agents.global_state import GlobalState
from gui_agents.agents.hardware_interface import HardwareInterface

logger = logging.getLogger("desktopenv.experiment")


def screenshot_bytes_to_pil_image(screenshot_bytes: bytes) -> Optional[Image.Image]:
    """
    Convert the bytes data of obs["screenshot"] to a PIL Image object, preserving the original size
    
    Args:
        screenshot_bytes: The bytes data of the screenshot
    
    Returns:
        PIL Image object, or None if conversion fails
    """
    if screenshot_bytes is None:
        logger.warning("Screenshot bytes is None")
        return None
    
    try:
        # Create PIL Image object directly from bytes
        image = Image.open(io.BytesIO(screenshot_bytes))
        logger.debug(f"Successfully converted screenshot to PIL Image, size: {image.size}, mode: {image.mode}")
        return image
    except Exception as e:
        logger.error(f"Failed to convert screenshot bytes to PIL Image: {e}")
        return None


def run_single_example(
    agent, env, example, max_steps, instruction, args, example_result_dir, scores, example_timestamp_dir
):
    global_state: GlobalState = Registry.get("GlobalStateStore") # type: ignore
    hwi = HardwareInterface(backend="pyautogui_vmware", platform='linux')

    # Set up a separate logger for each example
    example_logger = setup_example_logger(example, example_timestamp_dir)
    example_logger.info(f"Starting example {example.get('id', 'unknown')}")
    example_logger.info(f"Instruction: {instruction}")
    
    agent.reset()
    env.reset(task_config=example)
    time.sleep(60)  # Wait for the environment to be ready
    obs = env._get_obs()  # Get the initial observation
    global_state.set_screenshot(screenshot_bytes_to_pil_image(obs["screenshot"])) # type: ignore
    global_state.set_Tu(obs["instruction"])
    
    done = False
    step_idx = 0
    env.controller.start_recording()
    while not done and step_idx < max_steps:
        response, actions = agent.predict(instruction, global_state.get_obs_for_manager())
        for exec_code in actions:
            # Capture the timestamp before executing the action
            action_timestamp = datetime.datetime.now().strftime("%Y%m%d@%H%M%S")
            logger.info("Step %d: %s", step_idx + 1, exec_code)
            example_logger.info("Step %d: %s", step_idx + 1, exec_code)
            
            action = hwi.dispatchDict(exec_code)
            logger.info("Action: %s", action)
            example_logger.info("Action: %s", action)

            obs, reward, done, info = env.step(action, args.sleep_after_execution)
            global_state.set_screenshot(screenshot_bytes_to_pil_image(obs["screenshot"])) # type: ignore

            logger.info("Reward: %.2f", reward)
            logger.info("Done: %s", done)
            example_logger.info("Reward: %.2f", reward)
            example_logger.info("Done: %s", done)
            # Save screenshot and trajectory information
            with open(
                os.path.join(
                    example_result_dir, f"step_{step_idx + 1}_{action_timestamp}.png"
                ),
                "wb",
            ) as _f:
                _f.write(obs["screenshot"])
            with open(os.path.join(example_result_dir, "traj.jsonl"), "a") as f:
                f.write(
                    json.dumps(
                        {
                            "step_num": step_idx + 1,
                            "action_timestamp": action_timestamp,
                            "action": action,
                            "reward": reward,
                            "done": done,
                            "info": info,
                            "screenshot_file": f"step_{step_idx + 1}_{action_timestamp}.png",
                        }
                    )
                )
                f.write("\n")
            if done:
                logger.info("The episode is done.")
                example_logger.info("The episode is done.")
                break
        step_idx += 1
    result = env.evaluate()
    logger.info("Result: %.2f", result)
    example_logger.info("Result: %.2f", result)
    example_logger.info(f"Example {example.get('id', 'unknown')} completed with result: {result}")
    scores.append(result)
    with open(
        os.path.join(example_result_dir, "result.txt"), "w", encoding="utf-8"
    ) as f:
        f.write(f"{result}\n")
    env.controller.end_recording(os.path.join(example_result_dir, "recording.mp4"))

def setup_example_logger(example, example_timestamp_dir):
    example_id = example.get('id', 'unknown')
    example_logger = logging.getLogger(f"example.{example_id}.{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
    example_logger.setLevel(logging.DEBUG)
    
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
