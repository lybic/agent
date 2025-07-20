import datetime
import json
import logging
import os
import time
import io
from typing import Optional
from wrapt_timeout_decorator import *
from PIL import Image
from gui_agents.s2.store.registry import Registry
from gui_agents.s2.agents.global_state import GlobalState

logger = logging.getLogger("desktopenv.experiment")


def screenshot_bytes_to_pil_image(screenshot_bytes: bytes) -> Optional[Image.Image]:
    """
    将obs["screenshot"]的bytes数据转换为PIL Image对象，保持原始尺寸
    
    Args:
        screenshot_bytes: 截图的bytes数据
    
    Returns:
        PIL Image对象，如果转换失败则返回None
    """
    if screenshot_bytes is None:
        logger.warning("Screenshot bytes is None")
        return None
    
    try:
        # 直接从bytes创建PIL Image对象
        image = Image.open(io.BytesIO(screenshot_bytes))
        logger.debug(f"Successfully converted screenshot to PIL Image, size: {image.size}, mode: {image.mode}")
        return image
    except Exception as e:
        logger.error(f"Failed to convert screenshot bytes to PIL Image: {e}")
        return None


def run_single_example(
    agent, env, example, max_steps, instruction, args, example_result_dir, scores
):
    global_state: GlobalState = Registry.get("GlobalStateStore")
    runtime_logger = setup_logger(example, example_result_dir)
    agent.reset()
    env.reset(task_config=example)
    time.sleep(60)  # Wait for the environment to be ready
    obs = env._get_obs()  # Get the initial observation
    global_state.set_screenshot(screenshot_bytes_to_pil_image(obs["screenshot"]))
    global_state.set_instruction(obs["instruction"])
    
    done = False
    step_idx = 0
    env.controller.start_recording()
    while not done and step_idx < max_steps:
        response, actions = agent.predict(instruction, obs)
        for action in actions:
            # Capture the timestamp before executing the action
            action_timestamp = datetime.datetime.now().strftime("%Y%m%d@%H%M%S")
            logger.info("Step %d: %s", step_idx + 1, action)
            obs, reward, done, info = env.step(action, args.sleep_after_execution)

            logger.info("Reward: %.2f", reward)
            logger.info("Done: %s", done)
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
                break
        step_idx += 1
    result = env.evaluate()
    logger.info("Result: %.2f", result)
    scores.append(result)
    with open(
        os.path.join(example_result_dir, "result.txt"), "w", encoding="utf-8"
    ) as f:
        f.write(f"{result}\n")
    env.controller.end_recording(os.path.join(example_result_dir, "recording.mp4"))


def setup_logger(example, example_result_dir):
    runtime_logger = logging.getLogger(f"desktopenv.example.{example['id']}")
    runtime_logger.setLevel(logging.DEBUG)
    runtime_logger.addHandler(
        logging.FileHandler(os.path.join(example_result_dir, "runtime.log"))
    )
    return runtime_logger
