"""OSWorld's run.py with AgentS2."""

"""Script to run end-to-end evaluation on the benchmark.
Utils and basic architecture credit to https://github.com/web-arena-x/webarena/blob/main/run.py.
"""

import argparse
import datetime
import json
import logging
import os
import sys

from gui_agents.s2.agents.agent_s import AgentS2
from gui_agents.s2.agents.grounding import Grounding
from tqdm import tqdm

import lib_run_single
from desktop_env.desktop_env import DesktopEnv
from gui_agents.s2.store.registry import Registry
from gui_agents.s2.agents.global_state import GlobalState

current_platform = "linux"

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

vm_datetime_str: str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

log_dir = "runtime"
os.makedirs(os.path.join(log_dir, f"vmrun_{vm_datetime_str}"), exist_ok=True)

file_handler = logging.FileHandler(
    os.path.join(log_dir, f"vmrun_{vm_datetime_str}", "vmrun_normal.log"), encoding="utf-8"
)
debug_handler = logging.FileHandler(
    os.path.join(log_dir, f"vmrun_{vm_datetime_str}", "vmrun_debug.log"), encoding="utf-8"
)
stdout_handler = logging.StreamHandler(sys.stdout)
sdebug_handler = logging.FileHandler(
    os.path.join(log_dir, f"vmrun_{vm_datetime_str}", "vmrun_sdebug.log"), encoding="utf-8"
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

logger = logging.getLogger("desktopenv.experiment")

def config() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run end-to-end evaluation on the benchmark"
    )

    # environment config
    parser.add_argument("--path_to_vm", type=str, default="/Users/lxguo/Documents/Code/lybicguiagents/vmware_vm_data/Ubuntu0/Ubuntu0.vmx")
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
    parser.add_argument("--max_steps", type=int, default=15)

    # agent config
    parser.add_argument(
        "--test_config_base_dir", type=str, default="evaluation_examples"
    )

    # example config
    parser.add_argument("--domain", type=str, default="all")
    parser.add_argument(
        "--test_all_meta_path", type=str, default="evaluation_examples/test_tiny.json"
    )

    # logging related
    parser.add_argument("--result_dir", type=str, default="./results")

    parser.add_argument("--kb_name", default="kb_s2", type=str)

    args = parser.parse_args()

    return args


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

    agent = AgentS2(
        platform=current_platform,
        screen_size = [scaled_width, scaled_height]
    )

    env = DesktopEnv(
        path_to_vm=args.path_to_vm,
        action_space=agent.action_space,
        screen_size=(scaled_width, scaled_height),
        headless=args.headless,
        require_a11y_tree=False,
    )

    for domain in tqdm(test_all_meta, desc="Domain"):
        for example_id in tqdm(test_all_meta[domain], desc="Example", leave=False):
            config_file = os.path.join(
                args.test_config_base_dir, f"examples/{domain}/{example_id}.json"
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

            # 为每个example创建独立的时间戳文件夹
            example_datetime_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            example_timestamp_dir = os.path.join(log_dir, f"vmrun_{vm_datetime_str}", example_datetime_str)
            example_cache_dir = os.path.join(example_timestamp_dir, "cache", "screens")
            example_state_dir = os.path.join(example_timestamp_dir, "state")
            
            os.makedirs(example_cache_dir, exist_ok=True)
            os.makedirs(example_state_dir, exist_ok=True)

            # 为每个example注册独立的GlobalState
            Registry.clear()
            Registry.register(
                "GlobalStateStore",
                GlobalState(
                    screenshot_dir=example_cache_dir,
                    tu_path=os.path.join(example_state_dir, "tu.json"),
                    search_query_path=os.path.join(example_state_dir, "search_query.json"),
                    completed_subtasks_path=os.path.join(example_state_dir, "completed_subtasks.json"),
                    failed_subtasks_path=os.path.join(example_state_dir, "failed_subtasks.json"),
                    remaining_subtasks_path=os.path.join(example_state_dir, "remaining_subtasks.json"),
                    termination_flag_path=os.path.join(example_state_dir, "termination_flag.json"),
                    running_state_path=os.path.join(example_state_dir, "running_state.json"),
                    display_info_path=os.path.join(example_timestamp_dir, "display.json"),
                )
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
                lib_run_single.run_single_example(
                    agent,
                    env,
                    example,
                    max_steps,
                    instruction,
                    args,
                    example_result_dir,
                    scores,
                    example_timestamp_dir,  # 传递时间戳目录给run_single_example
                )
            except Exception as e:
                logger.error(f"Exception in {domain}/{example_id}: {e}")
                env.controller.end_recording(
                    os.path.join(example_result_dir, "recording.mp4")
                )
                with open(os.path.join(example_result_dir, "traj.jsonl"), "a") as f:
                    f.write(
                        json.dumps(
                            {"Error": f"Time limit exceeded in {domain}/{example_id}"}
                        )
                    )
                    f.write("\n")

    env.close()
    logger.info(f"Average score: {sum(scores) / len(scores)}")


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


if __name__ == "__main__":
    ####### The complete version of the list of examples #######
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
    left_info = ""
    for domain in test_file_list:
        left_info += f"{domain}: {len(test_file_list[domain])}\n"
    logger.info(f"Left tasks:\n{left_info}")

    get_result(
        args.action_space,
        args.observation_type,
        args.result_dir,
        test_all_meta,
    )
    test(args, test_file_list)
