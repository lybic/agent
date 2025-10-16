import asyncio
import json
import logging
import os
import platform
import textwrap
from typing import Dict, List, Optional, Tuple

from gui_agents.agents.worker import Worker
from gui_agents.agents.manager import Manager
from gui_agents.agents.grounding import Grounding, FastGrounding
from gui_agents.utils.common_utils import Node
from gui_agents.agents.global_state import GlobalState
from gui_agents.store.registry import Registry
from gui_agents.utils.common_utils import (
    # call_llm_safe,
    parse_single_code_from_string,
    sanitize_code,
    extract_first_agent_function,
    agent_log_to_string,
)
from gui_agents.tools.tools import Tools
from gui_agents.agents.stream_manager import stream_manager

logger = logging.getLogger("desktopenv.agent")

def load_config():
    """
    Load tool configurations from the repository's tools/tools_config.json and produce a mapping keyed by tool name.
    
    Returns:
        tuple: (tools_config, tools_dict) where `tools_config` is the parsed JSON object from tools_config.json, and `tools_dict` is a dict mapping each tool's `tool_name` to a dict with `provider` and `model`.
    """
    # Load tools configuration from tools_config.json
    tools_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools", "tools_config.json")
    with open(tools_config_path, "r") as f:
        tools_config = json.load(f)
        print(f"Loaded tools configuration from: {tools_config_path}")
        tools_dict = {}
        for tool in tools_config["tools"]:
            tool_name = tool["tool_name"]
            tools_dict[tool_name] = {
                "provider": tool["provider"],
                "model": tool["model_name"]
            }
        print(f"Tools configuration: {tools_dict}")
        return tools_config,tools_dict

class UIAgent:
    """Base class for UI automation agents"""

    def __init__(
        self,
        platform: str = platform.system().lower(),
    ):
        """Initialize UIAgent

        Args:
            platform: Operating system platform (macos, linux, windows)
        """
        self.platform = platform

    def reset(self) -> None:
        """
        Reset the agent to its initial internal state.
        
        Performs any subclass-specific reinitialization needed so the agent is ready to start a new task or episode.
        """
        pass

    def _send_stream_message(self, task_id: str, stage: str, message: str) -> None:
        """
        Safely send stream message to task stream.
        """
        if not task_id:
            return

        stream_manager.add_message_threadsafe(task_id, stage, message)

    def predict(self, instruction: str, observation: Dict) -> Tuple[Dict, List[str]]|None:
        """
        Produce the next agent information and action sequence for the given instruction and current observation.
        
        Returns:
            (info, actions) where `info` is a dictionary containing planner, executor and evaluator metadata (including subtask metadata and statuses) and `actions` is a list of action strings to execute; returns `None` if no prediction is available.
        """
        pass

    def update_narrative_memory(self, trajectory: str) -> None:
        """Update narrative memory with task trajectory

        Args:
            trajectory: String containing task execution trajectory
        """
        pass

    def update_episodic_memory(self, meta_data: Dict, subtask_trajectory: str) -> str|None:
        """Update episodic memory with subtask trajectory

        Args:
            meta_data: Metadata about current subtask execution
            subtask_trajectory: String containing subtask execution trajectory

        Returns:
            Updated subtask trajectory
        """
        pass

class AgentS2(UIAgent):
    """Agent that uses hierarchical planning and directed acyclic graph modeling for UI automation"""

    def __init__(
        self,
        platform: str = platform.system().lower(),
        screen_size: List[int] = [1920, 1080],
        memory_root_path: str = os.getcwd(),
        memory_folder_name: str = "kb_s2",
        kb_release_tag: str = "v0.2.2",
        enable_takeover: bool = False,
        enable_search: bool = True,
        tools_config: dict | None = None,
    ):
        """
        Initialize an AgentS2 instance and prepare its tools and local knowledge base.
        
        If `tools_config` is provided, build `Tools_dict` mapping each `tool_name` to its config (renaming `model_name` to `model` and removing `tool_name`). If `tools_config` is not provided, load configuration via `load_config()`. Ensure a platform-specific knowledge base directory exists under `memory_root_path/memory_folder_name` (creating it if missing). Sets initial attributes (platform, screen_size, memory paths, flags) and initializes internal state via `reset()`.
        
        Parameters:
            tools_config (dict | None): Optional pre-loaded tools configuration; when present it is transformed into `Tools_dict`. Omit to load configuration from disk.
        """
        super().__init__(
            platform,
        )

        self.memory_root_path = memory_root_path
        self.memory_folder_name = memory_folder_name
        self.kb_release_tag = kb_release_tag
        self.screen_size = screen_size
        self.enable_takeover = enable_takeover
        self.enable_search = enable_search
        self.task_id = None  # Will be set when task starts

        if tools_config is not None:
            self.tools_config = tools_config
            # Create the dictionary mapping from the list-based config
            self.Tools_dict = {}
            for tool in self.tools_config["tools"]:
                tool_name = tool["tool_name"]
                # Create a copy of the tool's config to avoid modifying the original
                config_copy = tool.copy()
                # Rename 'model_name' to 'model' for consistency in downstream use
                if 'model_name' in config_copy:
                    config_copy['model'] = config_copy.pop('model_name')
                # Remove tool_name as it's now the key
                config_copy.pop('tool_name', None)
                self.Tools_dict[tool_name] = config_copy
        else:
            self.tools_config, self.Tools_dict = load_config()

        # Initialize agent's knowledge base path
        self.local_kb_path = os.path.join(
            self.memory_root_path, self.memory_folder_name
        )

        # Check if knowledge base exists
        kb_platform_path = os.path.join(self.local_kb_path, self.platform)
        if not os.path.exists(kb_platform_path):
            print(f"Warning: Knowledge base for {self.platform} platform not found in {self.local_kb_path}")
            os.makedirs(kb_platform_path, exist_ok=True)
            print(f"Created directory: {kb_platform_path}")
            # raise FileNotFoundError(f"Knowledge base path does not exist: {kb_platform_path}")
        else:
            print(f"Found local knowledge base path: {kb_platform_path}")

    def reset(self) -> None:
        """
        Reinitialize core components and reset the agent's runtime state.
        
        Recreates the Manager, Worker, and Grounding components using the agent's current configuration,
        resets planning/execution flags and counters, clears subtask-related state, reloads the shared
        global state from the registry, and propagates the agent's task_id to the components when present.
        """
        # Initialize core components

        self.manager = Manager(
            Tools_dict=self.Tools_dict,
            local_kb_path=self.local_kb_path,
            platform=self.platform,
            enable_search=self.enable_search,  # Pass global switch to Manager
        )

        self.worker = Worker(
            Tools_dict=self.Tools_dict,
            local_kb_path=self.local_kb_path,
            platform=self.platform,
            enable_takeover=self.enable_takeover,
            enable_search=self.enable_search,  # Pass global switch to Worker
            tools_config=self.tools_config,    # Pass complete tools configuration
        )

        self.grounding = Grounding(
            Tools_dict=self.Tools_dict,
            platform=self.platform,
            width=self.screen_size[0],
            height=self.screen_size[1]
        )

        # Reset state variables
        self.requires_replan: bool = True
        self.needs_next_subtask: bool = True
        self.step_count: int = 0
        self.turn_count: int = 0
        self.failure_subtask: Optional[Node] = None
        self.should_send_action: bool = False
        self.completed_tasks: List[Node] = []
        self.current_subtask: Optional[Node] = None
        self.subtasks: List[Node] = []
        self.search_query: str = ""
        self.subtask_status: str = "Start"
        # Use task-specific registry if task_id is available, otherwise fall back to global registry
        if self.task_id:
            self.global_state: GlobalState = Registry.get_from_context("GlobalStateStore", self.task_id) # type: ignore
        else:
            self.global_state: GlobalState = Registry.get("GlobalStateStore") # type: ignore

        # Pass task_id to components
        self.manager.set_task_id(self.task_id)
        self.worker.set_task_id(self.task_id)
        # Grounding doesn't have task_id in normal mode, but we set it if available
        if hasattr(self, 'grounding') and hasattr(self.grounding, 'set_task_id'):
            self.grounding.set_task_id(self.task_id)

    def set_task_id(self, task_id: str) -> None:
        """
        Set the task identifier and propagate it to internal components used for streaming.
        
        Parameters:
            task_id (str): Identifier for the current task; assigned to this agent and, if present, to its manager and worker so stream messages are tagged consistently.
        """
        self.task_id = task_id
        # Also set task_id for components if they exist
        if hasattr(self, 'manager') and self.manager:
            self.manager.set_task_id(task_id)
        if hasattr(self, 'worker') and self.worker:
            self.worker.set_task_id(task_id)

    def reset_executor_state(self) -> None:
        """Reset executor and step counter"""
        self.worker.reset()
        self.step_count = 0

    def predict(self, instruction: str, observation: Dict) -> Tuple[Dict, List[str]]:
        # Initialize the three info dictionaries
        """
        Produce the next executor actions and diagnostic information for the current task step.
        
        This method coordinates planning, subtask selection, action generation, grounding (code extraction and execution), and status updates. It may trigger replanning, advance to the next subtask, mark subtasks as completed or failed, and emit stream messages and logs. The returned info merges planner, executor, and evaluator metadata and includes current subtask details.
        
        Parameters:
            instruction (str): The user or system instruction describing the task to accomplish; forwarded to the manager/worker as the task utterance.
            observation (Dict): Current environment observation/state used for grounding and coordinate assignment.
        
        Returns:
            info (Dict): A merged dictionary containing planner_info, executor_info, evaluator_info and the keys `subtask`, `subtask_info`, and `subtask_status`.
            actions (List[Dict]): List of action dictionaries produced for execution (may include actions with type "DONE", failure indicators, or other executor-generated actions).
        """
        planner_info = {}
        executor_info = {}
        evaluator_info = {
            "obs_evaluator_response": "",
            "num_input_tokens_evaluator": 0,
            "num_output_tokens_evaluator": 0,
            "evaluator_cost": 0.0,
        }
        actions = []

        # 记录预测开始时间
        import time
        predict_start_time = time.time()

        # If the DONE response by the executor is for a subtask, then the agent should continue with the next subtask without sending the action to the environment
        while not self.should_send_action:
            time.sleep(5.0)
            self.subtask_status = "In"
            # Always time get_action_queue, even if not called
            import time
            manager_start = time.time()
            # If replan is true, generate a new plan. True at start, after a failed plan, or after subtask completion
            if self.requires_replan:
                logger.info("(RE)PLANNING...")

                # Stream planning start message
                self._send_stream_message(self.task_id, "planning", f"Start planning task steps (Step {self.step_count + 1})...")

                Manager_info, self.subtasks = self.manager.get_action_queue(
                    Tu=self.global_state.get_Tu(),
                    observation=self.global_state.get_obs_for_manager(),
                    running_state=self.global_state.get_running_state(),
                    failed_subtask=self.failure_subtask,
                    completed_subtasks_list=self.global_state.get_completed_subtasks(),
                    remaining_subtasks_list=self.global_state.get_remaining_subtasks(),
                )
                self.global_state.set_remaining_subtasks(self.subtasks) # type: ignore

                self.requires_replan = False
                if "search_query" in Manager_info:
                    self.search_query = Manager_info["search_query"]
                else:
                    self.search_query = ""

                # Stream planning completion message
                self._send_stream_message(self.task_id, "planning", f"Planning completed, {len(self.subtasks)} subtasks generated")
            get_action_queue_time = time.time() - manager_start
            logger.info(f"[Timing] manager.get_action_queue execution time: {get_action_queue_time:.2f} seconds")
            self.global_state.log_operation(
                module="manager",
                operation="manager.get_action_queue",
                data={"duration": get_action_queue_time}
            )

            # use the exectuor to complete the topmost subtask
            if self.needs_next_subtask:
                logger.info("GETTING NEXT SUBTASK...")

                # this can be empty if the DAG planner deems that all subtasks are completed
                if len(self.subtasks) <= 0:
                    self.requires_replan = True
                    self.needs_next_subtask = True
                    self.failure_subtask = None
                    if self.current_subtask is not None:
                        self.global_state.add_completed_subtask(self.current_subtask)
                    # reset executor state
                    self.reset_executor_state()
                    self.should_send_action = True
                    self.subtask_status = "Done"
                    executor_info = {
                        "executor_plan": "agent.done()",
                        "plan_code": "agent.done()",
                        "reflection": "agent.done()",
                    }
                    actions = [{"type": "DONE"}]

                    # Stream task completion message
                    self._send_stream_message(self.task_id, "completion", "🎉 Mission Completed! All subtasks have been successfully executed")

                    self.global_state.log_operation(
                        module="agent",
                        operation="task_complete",
                        data={
                            "content": "All subtasks completed, task finished",
                            "status": "done"
                        }
                    )
                    break

                self.current_subtask = self.subtasks.pop(0)
                self.global_state.set_remaining_subtasks(self.subtasks)
                logger.info(f"NEXT SUBTASK: {self.current_subtask}")
                logger.info(f"REMAINING SUBTASKS: {self.subtasks}")
                logger.info(f"REMAINING SUBTASKS FROM GLOBAL STATE: {self.global_state.get_remaining_subtasks()}")
                self.needs_next_subtask = False
                self.subtask_status = "Start"

                # Stream current subtask message
                if self.current_subtask is not None:
                    self._send_stream_message(self.task_id, "subtask", f"Start executing subtasks: {self.current_subtask.name}")
                else:
                    self._send_stream_message(self.task_id, "subtask", "Start executing a new subtask")

                self.global_state.log_operation(
                    module="agent",
                    operation="current_subtask",
                    data={
                        "content": str(self.current_subtask) if self.current_subtask is not None else "No active subtask",
                        "status": "start"
                    }
                )

            worker_start_time = time.time()

            # Stream action generation start message
            self._send_stream_message(self.task_id, "thinking", "Generating execution actions...")

            # get the next action from the worker
            # Handle case where current_subtask might be None
            subtask_name = self.current_subtask.name if self.current_subtask is not None else "No active subtask"
            subtask_info = self.current_subtask.info if self.current_subtask is not None else ""

            executor_info = self.worker.generate_next_action(
                Tu=instruction,
                search_query=self.search_query,
                subtask=subtask_name,
                subtask_info=subtask_info,
                future_tasks=self.global_state.get_remaining_subtasks(),
                done_task=self.global_state.get_completed_subtasks(),
                obs=self.global_state.get_obs_for_manager(),
            )

            worker_execution_time = time.time() - worker_start_time

            self.global_state.log_operation(
                module="agent",
                operation="worker_execution",
                data={
                    "duration": worker_execution_time,
                    "subtask": self.current_subtask.name if self.current_subtask is not None else "No active subtask" # type: ignore
                }
            )

            # Stream action plan message
            if self.task_id and "executor_plan" in executor_info:
                plan_preview = executor_info["executor_plan"][:100] + "..." if len(executor_info["executor_plan"]) > 100 else executor_info["executor_plan"]
                self._send_stream_message(self.task_id, "action_plan", f"Generate an execution plan: {plan_preview}")

            try:
                grounding_start_time = time.time()
                current_width, current_height = self.global_state.get_screen_size()
                self.grounding.reset_screen_size(current_width, current_height)
                self.grounding.assign_coordinates(executor_info["executor_plan"], observation)
                plan_code = parse_single_code_from_string(executor_info["executor_plan"].split("Grounded Action")[-1])
                plan_code = sanitize_code(plan_code)
                plan_code = extract_first_agent_function(plan_code)
                agent: Grounding = self.grounding # type: ignore
                exec_code = eval(plan_code) # type: ignore
                grounding_execution_time = time.time() - grounding_start_time
                
                # 记录grounding执行时间
                self.global_state.log_operation(
                    module="agent",
                    operation="grounding_execution",
                    data={
                        "duration": grounding_execution_time,
                        "content": plan_code
                    }
                )
            except Exception as e:
                logger.error("Error in parsing plan code: %s", e)
                plan_code = "agent.wait(1.0)"
                agent: Grounding = self.grounding # this agent will be used in next code
                exec_code = eval(plan_code) # type: ignore
                
                # 记录grounding错误
                self.global_state.log_operation(
                    module="agent",
                    operation="grounding_error",
                    data={
                        "content": str(e),
                        "fallback_action": plan_code
                    }
                )

            actions = [exec_code]

            # Stream action execution message
            if actions:
                action_type = actions[0].get("type", "unknown")
                self._send_stream_message(self.task_id, "action", f"Execute an action: {action_type}")

            self.step_count += 1

            # set the should_send_action flag to True if the executor returns an action
            self.should_send_action = True

            # replan on failure
            if "fail" in actions[0]["type"].lower():
                self.requires_replan = True
                self.needs_next_subtask = True

                # assign the failed subtask
                if self.current_subtask is not None:
                    self.global_state.add_failed_subtask(self.current_subtask) # type: ignore
                self.failure_subtask = self.global_state.get_latest_failed_subtask()

                # Stream failure message
                if self.current_subtask is not None:
                    self._send_stream_message(self.task_id, "error", f"Subtask execution failed: {self.current_subtask.name}, will re-plan")
                else:
                    self._send_stream_message(self.task_id, "error", "Subtask execution failed and will be re-planned")

                # 记录失败的子任务
                self.global_state.log_operation(
                    module="agent",
                    operation="subtask_failed",
                    data={
                        "content": str(self.current_subtask) if self.current_subtask is not None else "Unknown subtask",
                        "status": "failed"
                    }
                )

                # reset the step count, executor, and evaluator
                self.reset_executor_state()

                # if more subtasks are remaining, we don't want to send DONE to the environment but move on to the next subtask
                if self.subtasks:
                    self.should_send_action = False

            # replan on subtask completion
            elif "done" in actions[0]["type"].lower():
                self.requires_replan = True
                self.needs_next_subtask = True
                self.failure_subtask = None
                # add completed subtask only if it exists
                if self.current_subtask is not None:
                    self.global_state.add_completed_subtask(self.current_subtask) # type: ignore

                # Stream subtask completion message
                if self.current_subtask is not None:
                    self._send_stream_message(self.task_id, "subtask_complete", f"✅ Subtask completed: {self.current_subtask.name}")
                else:
                    self._send_stream_message(self.task_id, "subtask_complete", "✅ Subtask completed")

                # 记录完成的子任务
                self.global_state.log_operation(
                    module="agent",
                    operation="subtask_completed",
                    data={
                        "content": str(self.current_subtask) if self.current_subtask is not None else "Unknown subtask",
                        "status": "completed"
                    }
                )

                # reset the step count, executor, and evaluator
                self.reset_executor_state()

                # if more subtasks are remaining, we don't want to send DONE to the environment but move on to the next subtask
                if self.subtasks:
                    self.should_send_action = False
                self.subtask_status = "Done"

            self.turn_count += 1

        # reset the should_send_action flag for next iteration
        self.should_send_action = False

        # concatenate the three info dictionaries
        info = {
            **{
                k: v
                for d in [planner_info or {}, executor_info or {}, evaluator_info or {}]
                for k, v in d.items()
            }
        }
        # Handle case where current_subtask might be None
        if self.current_subtask is not None:
            info.update(
                {
                    "subtask": self.current_subtask.name, # type: ignore
                    "subtask_info": self.current_subtask.info, # type: ignore
                    "subtask_status": self.subtask_status,
                }
            )
        else:
            # Handle None case - provide default values
            info.update(
                {
                    "subtask": "No active subtask",
                    "subtask_info": "",
                    "subtask_status": "no_subtask",
                }
            )
        
        # 记录predict函数总执行时间
        predict_total_time = time.time() - predict_start_time
        self.global_state.log_operation(
            module="agent",
            operation="predict_execution",
            data={
                "duration": predict_total_time,
                "step_count": self.step_count,
                "turn_count": self.turn_count,
                "subtask_status": self.subtask_status
            }
        )

        return info, actions # type: ignore

    def update_narrative_memory(self, trajectory: str) -> None:
        """Update narrative memory from task trajectory

        Args:
            trajectory: String containing task execution trajectory
        """
        try:
            reflection_path = os.path.join(
                self.local_kb_path, self.platform, "narrative_memory.json"
            )
            try:
                reflections = json.load(open(reflection_path))
            except:
                reflections = {}

            if self.search_query not in reflections:
                reflection = self.manager.summarize_narrative(trajectory)
                reflections[self.search_query] = reflection

            with open(reflection_path, "w") as f:
                json.dump(reflections, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to update narrative memory: {e}")

    def update_episodic_memory(self, meta_data: Dict, subtask_trajectory: str) -> str:
        """Update episodic memory from subtask trajectory

        Args:
            meta_data: Metadata about current subtask execution
            subtask_trajectory: String containing subtask execution trajectory

        Returns:
            Updated subtask trajectory
        """
        subtask = meta_data["subtask"]
        subtask_info = meta_data["subtask_info"]
        subtask_status = meta_data["subtask_status"]
        # Handle subtask trajectory
        if subtask_status == "Start" or subtask_status == "Done":
            # If it's a new subtask start, finalize the previous subtask trajectory if it exists
            if subtask_trajectory:
                subtask_trajectory += "\nSubtask Completed.\n"
                subtask_key = subtask_trajectory.split(
                    "\n----------------------\n\nPlan:\n"
                )[0]
                try:
                    subtask_path = os.path.join(
                        self.local_kb_path, self.platform, "episodic_memory.json"
                    )
                    kb = json.load(open(subtask_path))
                except:
                    kb = {}
                if subtask_key not in kb.keys():
                    subtask_summarization = self.manager.summarize_episode(
                        subtask_trajectory
                    )
                    kb[subtask_key] = subtask_summarization
                else:
                    subtask_summarization = kb[subtask_key]
                logger.info("subtask_key: %s", subtask_key)
                logger.info("subtask_summarization: %s", subtask_summarization)
                with open(subtask_path, "w") as fout:
                    json.dump(kb, fout, indent=2)
                # Reset for the next subtask
                subtask_trajectory = ""
            # Start a new subtask trajectory
            subtask_trajectory = (
                "Task:\n"
                + self.search_query
                + "\n\nSubtask: "
                + subtask
                + "\nSubtask Instruction: "
                + subtask_info
                + "\n----------------------\n\nPlan:\n"
                + meta_data["executor_plan"]
                + "\n"
            )
        elif subtask_status == "In":
            # Continue appending to the current subtask trajectory if it's still ongoing
            subtask_trajectory += (
                "\n----------------------\n\nPlan:\n"
                + meta_data["executor_plan"]
                + "\n"
            )

        return subtask_trajectory

class AgentSFast(UIAgent):
    """Fast version of AgentS2 that directly generates actions using the fast_action_generator tool"""

    def __init__(
        self,
        platform: str = platform.system().lower(),
        screen_size: List[int] = [1920, 1080],
        memory_root_path: str = os.getcwd(),
        memory_folder_name: str = "kb_s2",
        kb_release_tag: str = "v0.2.2",
        enable_takeover: bool = False,
        enable_search: bool = True,
        enable_reflection: bool = True,
        tools_config: dict | None = None,
        # enable_reflection: bool = False,
    ):
        """
        Create and initialize an AgentSFast instance, configuring tools, memory paths, and optional features.
        
        Parameters:
            platform (str): Operating system platform identifier (e.g., "darwin", "linux", "windows"); used to scope platform-specific knowledge base.
            screen_size (List[int]): Screen width and height used for grounding calculations.
            memory_root_path (str): Root directory for agent memory storage.
            memory_folder_name (str): Subfolder name under memory_root_path for this agent's knowledge base.
            kb_release_tag (str): Knowledge base release tag used for bookkeeping or compatibility.
            enable_takeover (bool): If True, enable user takeover capabilities in the fast action generator.
            enable_search (bool): If True, enable web/search-related features when registering tools.
            enable_reflection (bool): If True, enable trajectory reflection and a reflection agent to summarize agent behavior.
            tools_config (dict | None): Optional pre-loaded tools configuration; if omitted, configuration is loaded from disk.
        
        """
        super().__init__(
            platform,
        )

        self.memory_root_path = memory_root_path
        self.memory_folder_name = memory_folder_name
        self.kb_release_tag = kb_release_tag
        self.screen_size = screen_size
        self.enable_takeover = enable_takeover
        self.enable_search = enable_search
        self.enable_reflection = enable_reflection
        self.task_id = None  # Will be set when task starts

        if tools_config is not None:
            self.tools_config = tools_config
            # Create the dictionary mapping from the list-based config
            self.Tools_dict = {}
            for tool in self.tools_config["tools"]:
                tool_name = tool["tool_name"]
                # Create a copy of the tool's config to avoid modifying the original
                config_copy = tool.copy()
                # Rename 'model_name' to 'model' for consistency in downstream use
                if 'model_name' in config_copy:
                    config_copy['model'] = config_copy.pop('model_name')
                # Remove tool_name as it's now the key
                config_copy.pop('tool_name', None)
                self.Tools_dict[tool_name] = config_copy
        else:
            self.tools_config, self.Tools_dict = load_config()

        # Initialize agent's knowledge base path
        self.local_kb_path = os.path.join(
            self.memory_root_path, self.memory_folder_name
        )

        # Check if knowledge base exists
        kb_platform_path = os.path.join(self.local_kb_path, self.platform)
        if not os.path.exists(kb_platform_path):
            print(f"Warning: Knowledge base for {self.platform} platform not found in {self.local_kb_path}")
            os.makedirs(kb_platform_path, exist_ok=True)
            print(f"Created directory: {kb_platform_path}")
        else:
            print(f"Found local knowledge base path: {kb_platform_path}")

    def reset(self) -> None:
        """
        Reinitialize the fast-agent components and reset internal runtime state.
        
        Initializes and registers the fast action generator tool (and traj_reflector if reflection is enabled), configures search/auth parameters from tool configuration, creates or updates the grounding subsystem with resolved grounding dimensions, resets counters and runtime references (step_count, turn_count, latest_action, global_state), and propagates the current task_id to any registered tools.
        """
        # Initialize the fast action generator tool
        self.fast_action_generator = Tools()
        self.fast_action_generator_tool = "fast_action_generator_with_takeover" if self.enable_takeover else "fast_action_generator"

        # Get tool configuration from tools_config
        tool_config = None
        for tool in self.tools_config["tools"]:
            if tool["tool_name"] == self.fast_action_generator_tool:
                tool_config = tool
                break

        # Prepare tool parameters
        tool_params = {}

        # First check global search switch
        if not self.enable_search:
            # If global search is disabled, force disable search for this tool
            tool_params["enable_search"] = False
            logger.info(f"Configuring {self.fast_action_generator_tool} with search DISABLED (global switch off)")
        else:
            # If global search is enabled, check tool-specific config
            if tool_config and "enable_search" in tool_config:
                # Use enable_search from config file
                enable_search = tool_config.get("enable_search", False)
                tool_params["enable_search"] = enable_search
                tool_params["search_provider"] = tool_config.get("search_provider", "bocha")
                tool_params["search_model"] = tool_config.get("search_model", "")

                logger.info(f"Configuring {self.fast_action_generator_tool} with search enabled: {enable_search} (from config)")

        # Get base config from Tools_dict
        tool_config = self.Tools_dict[self.fast_action_generator_tool].copy()
        provider = tool_config.get("provider")
        model = tool_config.get("model")

        # Merge with search-related parameters
        all_params = {**tool_config, **tool_params}

        auth_keys = ['api_key', 'base_url', 'endpoint_url', 'azure_endpoint', 'api_version']
        for key in auth_keys:
            if key in all_params:
                logger.info(f"AgentSFast.reset: Setting {key} for fast_action_generator_tool")

        # Register the tool with all parameters
        self.fast_action_generator.register_tool(
            self.fast_action_generator_tool,
            provider,
            model,
            **all_params
        )

        if self.enable_reflection:
            self.reflection_agent = Tools()
            self.reflection_agent.register_tool(
                "traj_reflector", self.Tools_dict["traj_reflector"]["provider"],
                self.Tools_dict["traj_reflector"]["model"])
            self.reflections = []
            self.planner_history = []

        self.grounding_width, self.grounding_height = self.fast_action_generator.tools[self.fast_action_generator_tool].get_grounding_wh()
        if self.grounding_width is None or self.grounding_height is None:
            self.grounding_width = self.screen_size[0]
            self.grounding_height = self.screen_size[1]
        self.grounding = FastGrounding(
            Tools_dict=self.Tools_dict,
            platform=self.platform,
            width=self.screen_size[0],
            height=self.screen_size[1],
            grounding_width=self.grounding_width,
            grounding_height=self.grounding_height
        )

        # Reset state variables
        self.step_count: int = 0
        self.turn_count: int = 0
        # Use task-specific registry if task_id is available, otherwise fall back to global registry
        if self.task_id:
            self.global_state: GlobalState = Registry.get_from_context("GlobalStateStore", self.task_id) # type: ignore
        else:
            self.global_state: GlobalState = Registry.get("GlobalStateStore") # type: ignore
        self.latest_action = None

        # Pass task_id to tools and components if available
        self.fast_action_generator.task_id = self.task_id
        if self.enable_reflection and hasattr(self, 'reflection_agent'):
            self.reflection_agent.task_id = self.task_id
        # Set task_id for grounding component
        if hasattr(self, 'grounding') and hasattr(self.grounding, 'set_task_id'):
            self.grounding.set_task_id(self.task_id)

    def set_task_id(self, task_id: str) -> None:
        """
        Store the task identifier on the agent and propagate it to subcomponents that use it.

        Parameters:
            task_id (str): Identifier for the active task; assigned to this agent and, if present, to
                `fast_action_generator` and `reflection_agent`.
        """
        self.task_id = task_id
        # Also set task_id for components if they exist
        if hasattr(self, 'fast_action_generator') and self.fast_action_generator:
            self.fast_action_generator.task_id = task_id
        if hasattr(self, 'reflection_agent') and self.reflection_agent:
            self.reflection_agent.task_id = task_id
        # Set task_id for grounding component
        if hasattr(self, 'grounding') and hasattr(self.grounding, 'set_task_id'):
            self.grounding.set_task_id(task_id)

    def predict(self, instruction: str, observation: Dict) -> Tuple[Dict, List[str]]:
        """
        Generate the next executor plan and corresponding actions using the configured fast action generator.
        
        Parameters:
        	instruction (str): Natural language task description.
        	observation (Dict): Current UI state; must include a "screenshot" entry with the screen image.
        
        Returns:
        	executor_info (dict): Contains at least the keys `executor_plan` (raw plan text), `reflection` (reflection text or empty string), and `plan_code` (the latest extracted/used action code).
        	actions (List[dict]): List of action dictionaries produced by grounding execution; typically a single action dict describing the operation to perform.
        """
        import time
        predict_start_time = time.time()
        
        fast_action_start_time = time.time()

        reflection = None
        if self.enable_reflection:
            if self.turn_count == 0:
                text_content = textwrap.dedent(f"""
                    Task Description: {instruction}
                    """)
                self.reflection_agent.tools["traj_reflector"].llm_agent.add_message(
                    text_content + "\n\nThe initial screen is provided. No action has been taken yet.",
                    image_content=observation["screenshot"],
                    role="user")
                self.global_state.add_agent_log({
                    "type": "passive",
                    "content": "Reflection: " + text_content + "\n\nThe initial screen is provided. No action has been taken yet."
                })
            else:
                agent_log = agent_log_to_string(self.global_state.get_agent_log())
                text_content = f"Please refer to the agent log to understand the progress and context of the task so far.\n{agent_log}"

                reflection_start = time.time()
                reflection, total_tokens, cost_string = self.reflection_agent.execute_tool(
                    "traj_reflector", {
                        "str_input": text_content,
                        "img_input": observation["screenshot"]
                    })
                reflection = str(reflection)
                self.reflection_agent.reset("traj_reflector")
                self.global_state.add_agent_log({
                    "type": "passive",
                    "content": "Reflection: " + reflection
                })
                logger.info(f"Trajectory reflector tokens: {total_tokens}, cost: {cost_string}")
                reflection_time = time.time() - reflection_start
                logger.info(f"[Timing] AgentSFast.traj_reflector execution time: {reflection_time:.2f} seconds")
                self.reflections.append(reflection)
                logger.info("REFLECTION: %s", reflection)
                self.global_state.log_operation(
                    module="agent",
                    operation="reflection",
                    data={
                        "tokens": total_tokens,
                        "cost": cost_string,
                        "content": reflection,
                        "duration": reflection_time
                    })

        agent_log = agent_log_to_string(self.global_state.get_agent_log())
        
        generator_message = textwrap.dedent(f"""
            Task Description: {instruction}
        """)

        generator_message += f"\n\nPlease refer to the agent log to understand the progress and context of the task so far.\n{agent_log}"

        fast_action_start_time = time.time()

        # Stream action generation start message
        self._send_stream_message(self.task_id, "thinking", "Generating execution actions quickly...")

        plan, total_tokens, cost_string = self.fast_action_generator.execute_tool(
            self.fast_action_generator_tool,
            {
                "str_input": generator_message,
                "img_input": observation["screenshot"]
            }
        )
        self.fast_action_generator.reset(self.fast_action_generator_tool)

        fast_action_execution_time = time.time() - fast_action_start_time

        self.global_state.log_operation(
            module="agent",
            operation="fast_action_execution",
            data={
                "duration": fast_action_execution_time,
                "tokens": total_tokens,
                "cost": cost_string
            }
        )

        # Stream action plan message
        if self.task_id:
            plan_preview = plan[:100] + "..." if len(plan) > 100 else plan
            self._send_stream_message(self.task_id, "action_plan", f"Quickly generate execution plans: {plan_preview}")

        logger.info("Fast Action Plan: %s", plan)

        current_width, current_height = self.global_state.get_screen_size()
        self.grounding.reset_screen_size(current_width, current_height)
        try:
            code_pattern = r"```python\s*(.*?)\s*```"
            import re
            match = re.search(code_pattern, plan, re.DOTALL)
            
            if match:
                action_code = match.group(1).strip()
                logger.info("Extracted action code: %s", action_code)
                
                agent: FastGrounding = self.grounding # type: ignore
                exec_code = eval(action_code) # type: ignore
                actions = [exec_code]
                self.latest_action = action_code
            else:
                logger.warning("No code block found, trying to parse the entire response")
                action_code = plan.strip()
                
                if action_code.startswith("agent."):
                    agent: FastGrounding = self.grounding # type: ignore
                    exec_code = eval(action_code) # type: ignore
                    actions = [exec_code]
                    self.latest_action = action_code
                else:
                    logger.error("Could not parse action, using wait action")
                    self.global_state.add_agent_log({
                        "type": "Wrong action code format",
                        "content": action_code
                    })
                    agent: FastGrounding = self.grounding # type: ignore
                    exec_code = eval("agent.wait(1000)") # type: ignore
                    actions = [exec_code]
                    self.latest_action = "agent.wait(1000)"
        except Exception as e:
            logger.error("Error in parsing action code: %s", e)
            self.global_state.add_agent_log({
                    "type": "Error in parsing action code",
                    "content": str(e)  # Convert Exception to string
                })
            agent: FastGrounding = self.grounding # type: ignore
            exec_code = eval("agent.wait(1000)") # type: ignore
            actions = [exec_code]
            self.latest_action = "agent.wait(1000)"
            
            self.global_state.log_operation(
                module="agent",
                operation="fast_action_error",
                data={
                    "content": str(e),
                    "fallback_action": "agent.wait(1000)"
                }
            )

        self.step_count += 1
        self.turn_count += 1

        # Stream action execution message
        if actions:
            action_type = actions[0].get("type", "unknown")
            self._send_stream_message(self.task_id, "action", f"Execute an action: {action_type}")

        executor_info = {
            "executor_plan": plan,
            "reflection": reflection or "",
            "plan_code": self.latest_action
        }

        predict_total_time = time.time() - predict_start_time
        self.global_state.log_operation(
            module="agent",
            operation="predict_execution_fast_direct",
            data={
                "duration": predict_total_time,
                "step_count": self.step_count,
                "turn_count": self.turn_count
            }
        )

        return executor_info, actions