import json
import logging
from math import log
import os
import platform
import textwrap
from typing import Dict, List, Optional, Tuple

from gui_agents.agents.grounding import ACI
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

logger = logging.getLogger("desktopenv.agent")

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
        """Reset agent state"""
        pass

    def predict(self, instruction: str, observation: Dict) -> Tuple[Dict, List[str]]|None:
        """Generate next action prediction

        Args:
            instruction: Natural language instruction
            observation: Current UI state observation

        Returns:
            Tuple containing agent info dictionary and list of actions
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

class AgentSNormal(UIAgent):
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
    ):
        """Initialize AgentSNormal

        Args:
            platform: Operating system platform (darwin, linux, windows)
            memory_root_path: Path to memory directory. Defaults to current working directory.
            memory_folder_name: Name of memory folder. Defaults to "kb_s2".
            kb_release_tag: Release tag for knowledge base. Defaults to "v0.2.2".
            enable_takeover: Whether to enable user takeover functionality. Defaults to False.
            enable_search: Whether to enable web search functionality. Defaults to True.
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

        # Load tools configuration from tools_config.json
        tools_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools", "tools_config.json")
        with open(tools_config_path, "r") as f:
            self.tools_config = json.load(f)
            print(f"Loaded tools configuration from: {tools_config_path}")
            self.Tools_dict = {}
            for tool in self.tools_config["tools"]:
                tool_name = tool["tool_name"]
                self.Tools_dict[tool_name] = {
                    "provider": tool["provider"],
                    "model": tool["model_name"]
                }
            print(f"Tools configuration: {self.Tools_dict}")

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

        self.reset()

    def reset(self) -> None:
        """Reset agent state and initialize components"""
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
        self.global_state: GlobalState = Registry.get("GlobalStateStore") # type: ignore
        self.last_exec_plan_code: Optional[str] = None
        self.last_exec_repeat: int = 0

    def reset_executor_state(self) -> None:
        """Reset executor and step counter"""
        self.worker.reset()
        self.step_count = 0

    def predict(self, instruction: str, observation: Dict) -> Tuple[Dict, List[str]]:
        # Initialize the three info dictionaries
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
                    
                    # 记录任务完成
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
                
                self.global_state.log_operation(
                    module="agent",
                    operation="current_subtask",
                    data={
                        "content": str(self.current_subtask),
                        "status": "start"
                    }
                )

            worker_start_time = time.time()
            
            # get the next action from the worker
            executor_info = self.worker.generate_next_action(
                Tu=instruction,
                search_query=self.search_query,
                subtask=self.current_subtask.name, # type: ignore
                subtask_info=self.current_subtask.info, # type: ignore
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
                    "subtask": self.current_subtask.name # type: ignore
                }
            )

            try:
                grounding_start_time = time.time()
                current_width, current_height = self.global_state.get_screen_size()
                self.grounding.reset_screen_size(current_width, current_height)
                self.grounding.assign_coordinates(executor_info["executor_plan"], observation)
                raw_grounded_action = executor_info["executor_plan"].split("Grounded Action")[-1]
                plan_code = parse_single_code_from_string(raw_grounded_action)
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
                logger.error("Error in parsing plan code: %s | raw_grounded_action: %s", e, 'raw_grounded_action' in locals() and raw_grounded_action or None)
                self.global_state.add_agent_log({
                    "type": "Error in parsing action code",
                    "content": f"error={str(e)}; raw_grounded_action={(raw_grounded_action if 'raw_grounded_action' in locals() else None)!r}"
                })
                plan_code = "agent.wait(1.0)"
                agent: Grounding = self.grounding # this agent will be used in next code
                exec_code = eval(plan_code) # type: ignore
                
                # 记录grounding错误
                self.global_state.log_operation(
                    module="agent",
                    operation="grounding_error",
                    data={
                        "content": str(e),
                        "fallback_action": plan_code,
                        "raw_grounded_action": (raw_grounded_action if 'raw_grounded_action' in locals() else None),
                        "plan": executor_info.get("executor_plan", "")
                    }
                )
            
            actions = [exec_code]
            
            if plan_code == (self.last_exec_plan_code or None):
                self.last_exec_repeat += 1
            else:
                self.last_exec_plan_code = plan_code
                self.last_exec_repeat = 1
            if self.last_exec_repeat >= 3:
                warning_msg = f"Action repeated {self.last_exec_repeat} times, possible stuck: {plan_code}"
                logger.warning(warning_msg)
                self.global_state.add_agent_log({
                    "type": "warning",
                    "content": warning_msg
                })
            
            self.step_count += 1

            # set the should_send_action flag to True if the executor returns an action
            self.should_send_action = True

            # replan on failure
            if "fail" in actions[0]["type"].lower():
                self.requires_replan = True
                self.needs_next_subtask = True

                # assign the failed subtask
                self.global_state.add_failed_subtask(self.current_subtask) # type: ignore
                self.failure_subtask = self.global_state.get_latest_failed_subtask()
                
                # 记录失败的子任务
                self.global_state.log_operation(
                    module="agent",
                    operation="subtask_failed",
                    data={
                        "content": str(self.current_subtask),
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
                self.global_state.add_completed_subtask(self.current_subtask) # type: ignore
                
                # 记录完成的子任务
                self.global_state.log_operation(
                    module="agent",
                    operation="subtask_completed",
                    data={
                        "content": str(self.current_subtask),
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
        info.update(
            {
                "subtask": self.current_subtask.name, # type: ignore
                "subtask_info": self.current_subtask.info, # type: ignore
                "subtask_status": self.subtask_status,
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
    """Fast version of AgentSNormal that generates a description-based plan with reflection, then grounds to precise coordinates before execution"""

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
        # enable_reflection: bool = False,
    ):
        """Initialize AgentSFast

        Args:
            platform: Operating system platform (darwin, linux, windows)
            memory_root_path: Path to memory directory. Defaults to current working directory.
            memory_folder_name: Name of memory folder. Defaults to "kb_s2".
            kb_release_tag: Release tag for knowledge base. Defaults to "v0.2.2".
            enable_takeover: Whether to enable user takeover functionality. Defaults to False.
            enable_search: Whether to enable web search functionality. Defaults to True.
            enable_reflection: Whether to enable reflection functionality. Defaults to True.
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

        # Load tools configuration from tools_config.json
        tools_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools", "tools_config.json")
        with open(tools_config_path, "r") as f:
            self.tools_config = json.load(f)
            print(f"Loaded tools configuration from: {tools_config_path}")
            self.Tools_dict = {}
            for tool in self.tools_config["tools"]:
                tool_name = tool["tool_name"]
                self.Tools_dict[tool_name] = {
                    "provider": tool["provider"],
                    "model": tool["model_name"]
                }
            print(f"Tools configuration: {self.Tools_dict}")

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

        self.reset()

    def reset(self) -> None:
        """Reset agent state and initialize components"""
        # Initialize the planner (description-based) action generator tool
        self.generator_agent = Tools()
        self.action_generator_tool = "fast_action_generator_with_takeover" if self.enable_takeover else "fast_action_generator"
        
        # Get tool configuration from tools_config
        tool_config = None
        for tool in self.tools_config["tools"]:
            if tool["tool_name"] == self.action_generator_tool:
                tool_config = tool
                break
        
        # Prepare tool parameters
        tool_params = {}
        
        # Apply global search switch and tool-specific overrides
        if not self.enable_search:
            tool_params["enable_search"] = False
            logger.info(f"Configuring {self.action_generator_tool} with search DISABLED (global switch off)")
        else:
            if tool_config and "enable_search" in tool_config:
                enable_search = tool_config.get("enable_search", False)
                tool_params["enable_search"] = enable_search
                tool_params["search_provider"] = tool_config.get("search_provider", "bocha")
                tool_params["search_model"] = tool_config.get("search_model", "")
                logger.info(f"Configuring {self.action_generator_tool} with search enabled: {enable_search} (from config)")
        
        # Register the planner tool
        self.generator_agent.register_tool(
            self.action_generator_tool, 
            self.Tools_dict[self.action_generator_tool]["provider"], 
            self.Tools_dict[self.action_generator_tool]["model"],
            **tool_params
        )

        # Use normal Grounding (description -> coordinates) instead of direct coordinate execution
        self.grounding = Grounding(
            Tools_dict=self.Tools_dict,
            platform=self.platform,
            width=self.screen_size[0],
            height=self.screen_size[1]
        )

        # Reset state variables
        self.step_count: int = 0
        self.turn_count: int = 0
        self.global_state: GlobalState = Registry.get("GlobalStateStore") # type: ignore
        self.latest_action = None
        self.last_exec_plan_code: Optional[str] = None
        self.last_exec_repeat: int = 0
        self.raw_grounded_action: Optional[str] = None

    def predict(self, instruction: str, observation: Dict) -> Tuple[Dict, List[str]]:
        """Generate next action prediction using two steps: (1) plan with integrated reflection, (2) ground to coordinates

        Args:
            instruction: Natural language instruction
            observation: Current UI state observation

        Returns:
            Tuple containing agent info dictionary and list of actions
        """
        import time
        predict_start_time = time.time()
        
        # Build planning message that includes history for implicit reflection within the same call
        agent_log = agent_log_to_string(self.global_state.get_agent_log())
        generator_message = textwrap.dedent(f"""
            Task Description: {instruction}
        """)
        generator_message += f"\n\nPlease reflect on prior actions (if any), verify the previous step outcome, analyze the current screenshot carefully, and then decide the next action.\n"
        generator_message += f"Please refer to the agent log to understand the progress and context so far.\n{agent_log}"

        # Step 1: planning (description-based action with built-in reflection via prompt)
        planning_start_time = time.time()
        plan, total_tokens, cost_string = self.generator_agent.execute_tool(
            self.action_generator_tool,
            {
                "str_input": generator_message,
                "img_input": observation["screenshot"]
            }
        )
        # Reset to avoid unintended message accumulation
        self.generator_agent.reset(self.action_generator_tool)
        planning_execution_time = time.time() - planning_start_time
        
        self.global_state.log_operation(
            module="agent",
            operation="fast_planning_execution",
            data={
                "duration": planning_execution_time,
                "tokens": total_tokens,
                "cost": cost_string
            }
        )
        
        logger.info("Fast Planning Output: %s", plan)
        # Record planning output into agent log for future context
        self.global_state.add_agent_log({
            "type": "passive",
            "content": plan
        })
 
        # Step 2: grounding to precise coordinates and building executable action
        current_width, current_height = self.global_state.get_screen_size()
        self.grounding.reset_screen_size(current_width, current_height)
        try:
            grounding_start_time = time.time()
            self.raw_grounded_action = plan.split("Grounded Action")[-1]
            plan_code = parse_single_code_from_string(self.raw_grounded_action)
            self.grounding.assign_coordinates(plan, observation)
            plan_code = sanitize_code(plan_code)
            plan_code = extract_first_agent_function(plan_code)
            agent: Grounding = self.grounding  # type: ignore
            exec_code = eval(plan_code)  # type: ignore
            grounding_execution_time = time.time() - grounding_start_time

            self.global_state.log_operation(
                module="agent",
                operation="fast_grounding_execution",
                data={
                    "duration": grounding_execution_time,
                    "content": plan_code
                }
            )

            actions = [exec_code]
            self.latest_action = plan_code
            
            if plan_code == (self.last_exec_plan_code or None):
                self.last_exec_repeat += 1
            else:
                self.last_exec_plan_code = plan_code
                self.last_exec_repeat = 1
            if self.last_exec_repeat >= 3:
                warning_msg = f"Action repeated {self.last_exec_repeat} times, possible stuck: {plan_code}"
                logger.warning(warning_msg)
                self.global_state.add_agent_log({
                    "type": "warning",
                    "content": warning_msg
                })
        except Exception as e:
            logger.error("Error in parsing/grounding action code: %s | raw_grounded_action: %s", e, self.raw_grounded_action)
            self.global_state.add_agent_log({
                "type": "Error in parsing action code",
                "content": f"error={str(e)}; latest_grounded_action={self.raw_grounded_action}"
            })
            agent: Grounding = self.grounding  # type: ignore
            exec_code = eval("agent.wait(1000)")  # type: ignore
            actions = [exec_code]
            self.latest_action = "agent.wait(1000)"
            
            if self.latest_action == (self.last_exec_plan_code or None):
                self.last_exec_repeat += 1
            else:
                self.last_exec_plan_code = self.latest_action
                self.last_exec_repeat = 1
            if self.last_exec_repeat >= 3:
                warning_msg = f"Action repeated {self.last_exec_repeat} times, possible stuck: {self.raw_grounded_action}"
                logger.warning(warning_msg)
                self.global_state.add_agent_log({
                    "type": "warning",
                    "content": warning_msg
                })
            
            self.global_state.log_operation(
                module="agent",
                operation="fast_action_error",
                data={
                    "content": str(e),
                    "fallback_action": "agent.wait(1000)",
                    "raw_grounded_action": self.raw_grounded_action,
                    "plan": plan
                }
            )

        self.step_count += 1
        self.turn_count += 1
        
        executor_info = {
            "executor_plan": plan,
            "reflection": "",
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
