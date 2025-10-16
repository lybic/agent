import logging
import re
import textwrap
from typing import Dict, List
import platform
import os
import json

from gui_agents.core.knowledge import KnowledgeBase
from gui_agents.utils.common_utils import (
    Node,
    extract_first_agent_function,
    parse_single_code_from_string,
    sanitize_code,
    agent_log_to_string,
)
from gui_agents.tools.tools import Tools
from gui_agents.store.registry import Registry
from gui_agents.agents.global_state import GlobalState

logger = logging.getLogger("desktopenv.agent")


class Worker:

    def __init__(
        self,
        Tools_dict: Dict,
        local_kb_path: str,
        platform: str = platform.system().lower(),
        enable_reflection: bool = True,
        use_subtask_experience: bool = True,
        enable_takeover: bool = False,
        enable_search: bool = True,
        tools_config: Dict = {},
    ):
        """
        Initialize a Worker that generates executor actions using the provided tools, local knowledge base, and optional reflection, episodic experience, takeover, and search features.
        
        Parameters:
            Tools_dict (Dict): Mapping of tool names to tool instances/configurations used by the Worker.
            local_kb_path (str): Filesystem path to the local knowledge base to use for retrieval.
            platform (str): Operating system identifier the agent runs on (e.g., 'darwin', 'linux', 'windows').
            enable_reflection (bool): If True, enable trajectory reflection generation and use its output when producing actions.
            use_subtask_experience (bool): If True, attempt to retrieve and incorporate episodic/subtask experience on the first turn.
            enable_takeover (bool): If True, use the takeover-capable action generator tool when producing actions.
            enable_search (bool): Global switch that forces search-enabled tools to run with search disabled when False.
            tools_config (Dict): Tools configuration mapping; if None, the Worker loads tools_config.json from the package tools directory.
        """
        # super().__init__(engine_params, platform)
        self.platform = platform

        self.local_kb_path = local_kb_path
        self.Tools_dict = Tools_dict
        self.enable_takeover = enable_takeover
        self.enable_search = enable_search  # Store global search switch

        # If tools_config is not provided, load it from file
        if tools_config is None:
            tools_config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "tools",
                "tools_config.json")
            with open(tools_config_path, "r") as f:
                self.tools_config = json.load(f)
        else:
            self.tools_config = tools_config

        self.enable_reflection = enable_reflection
        self.use_subtask_experience = use_subtask_experience
        # GlobalState will be initialized in reset() method when task_id is available
        self.global_state: GlobalState = None  # type: ignore
        self.reset()

    def reset(self):

        """
        Initialize the worker's tool agents, knowledge base, and internal state for a new task session.
        
        This method registers the action generator (with optional takeover variant), trajectory reflector, and embedding engine using a local helper that merges tool configuration with any overrides and propagates authentication parameters; it initializes the KnowledgeBase with the embedding engine and toolkit, configures search-related parameters for the action generator according to global and per-tool settings, and resets runtime state fields (turn count, histories, reflections, cost tracking, screenshot inputs, planner history, latest action, trajectory length limit, and task_id).
        """
        def _register(tools_instance, tool_name, **override_kwargs):
            config = self.Tools_dict.get(tool_name, {}).copy()
            provider = config.pop("provider", None)
            model = config.pop("model", None)

            # Merge with any explicit overrides
            config.update(override_kwargs)

            auth_params = {}
            auth_keys = ['api_key', 'base_url', 'endpoint_url', 'azure_endpoint', 'api_version']
            for key in auth_keys:
                if key in config:
                    auth_params[key] = config[key]
                    logger.info(f"Worker._register: Setting {key} for tool '{tool_name}'")

            all_params = {**config, **auth_params}

            logger.info(f"Worker._register: Registering tool '{tool_name}' with provider '{provider}', model '{model}'")
            tools_instance.register_tool(tool_name, provider, model, **all_params)

        self.generator_agent = Tools()
        self.action_generator_tool = "action_generator_with_takeover" if self.enable_takeover else "action_generator"

        # Get tool configuration from tools_config
        tool_config = None
        for tool in self.tools_config["tools"]:
            if tool["tool_name"] == self.action_generator_tool:
                tool_config = tool
                break

        # Prepare tool parameters
        tool_params = {}

        # First check global search switch
        if not self.enable_search:
            # If global search is disabled, force disable search for this tool
            tool_params["enable_search"] = False
            logger.info(
                f"Configuring {self.action_generator_tool} with search DISABLED (global switch off)"
            )
        else:
            # If global search is enabled, check tool-specific config
            if tool_config and "enable_search" in tool_config:
                # Use enable_search from config file
                enable_search = tool_config.get("enable_search", False)
                tool_params["enable_search"] = enable_search
                tool_params["search_provider"] = tool_config.get(
                    "search_provider", "bocha")
                tool_params["search_model"] = tool_config.get(
                    "search_model", "")

                logger.info(
                    f"Configuring {self.action_generator_tool} with search enabled: {enable_search} (from config)"
                )

        # Register the tool with parameters
        _register(self.generator_agent, self.action_generator_tool, **tool_params)

        self.reflection_agent = Tools()
        _register(self.reflection_agent, "traj_reflector")

        self.embedding_engine = Tools()
        _register(self.embedding_engine, "embedding")

        self.knowledge_base = KnowledgeBase(
            embedding_engine=self.embedding_engine,
            Tools_dict=self.Tools_dict,
            local_kb_path=self.local_kb_path,
            platform=self.platform,
        )

        self.turn_count = 0
        self.worker_history = []
        self.reflections = []
        self.cost_this_turn = 0
        self.screenshot_inputs = []
        self.planner_history = []
        self.latest_action = None
        self.max_trajector_length = 8
        self.task_id = None  # Will be set by agent

    def set_task_id(self, task_id: str) -> None:
        """Set the task identifier and update global state reference"""
        self.task_id = task_id
        # Update global state reference with task-specific registry
        self.global_state = Registry.get_from_context("GlobalStateStore", task_id)  # type: ignore

    def generate_next_action(
        self,
        Tu: str,
        search_query: str,
        subtask: str,
        subtask_info: str,
        future_tasks: List[Node],
        done_task: List[Node],
        obs: Dict,
        running_state: str = "running",
    ) -> Dict:
        """
        Generate the next executor action plan and related metadata for the current subtask given the observation and context.
        
        Parameters:
            Tu (str): Full task description or task context.
            search_query (str): Search string used for retrieving episodic/subtask experience.
            subtask (str): Current subtask instruction/description to complete.
            subtask_info (str): Additional information or constraints for the current subtask.
            future_tasks (List[Node]): List of upcoming task nodes (used for context in planning).
            done_task (List[Node]): List of completed task nodes.
            obs (Dict): Current observation dictionary; must include a "screenshot" key with the current screen image.
            running_state (str): Current executor running state (default "running").
        
        Returns:
            Dict: Executor information containing:
                - "current_subtask" (str): The provided subtask.
                - "current_subtask_info" (str): The provided subtask_info.
                - "executor_plan" (str): The raw plan produced by the action generator.
                - "reflection" (str|None): Reflection text produced by the trajectory reflector, or None if reflection is disabled.
        """
        import time
        action_start = time.time()

        # Log the result of the previous hardware action, which is the current observation.
        if self.turn_count > 0 and self.latest_action:
            self.global_state.add_agent_log({
                "type":
                    "passive",
                "content":
                    f"Hardware action `{self.latest_action}` has been executed. The result is reflected in the current screenshot."
            })

        # Get RAG knowledge, only update system message at t=0
        if self.turn_count == 0:
            if self.use_subtask_experience:
                subtask_query_key = ("Task:\n" + search_query +
                                     "\n\nSubtask: " + subtask +
                                     "\nSubtask Instruction: " + subtask_info)
                retrieve_start = time.time()
                retrieved_similar_subtask, retrieved_subtask_experience, total_tokens, cost_string = (
                    self.knowledge_base.retrieve_episodic_experience(
                        subtask_query_key))
                logger.info(
                    f"Retrieve episodic experience tokens: {total_tokens}, cost: {cost_string}"
                )
                retrieve_time = time.time() - retrieve_start
                logger.info(
                    f"[Timing] Worker.retrieve_episodic_experience execution time: {retrieve_time:.2f} seconds"
                )

                # Dirty fix to replace id with element description during subtask retrieval
                pattern = r"\(\d+"
                retrieved_subtask_experience = re.sub(
                    pattern, "(element_description",
                    retrieved_subtask_experience)
                retrieved_subtask_experience = retrieved_subtask_experience.replace(
                    "_id", "_description")

                logger.info(
                    "SIMILAR SUBTASK EXPERIENCE: %s",
                    retrieved_similar_subtask + "\n" +
                    retrieved_subtask_experience.strip(),
                )
                self.global_state.log_operation(
                    module="worker",
                    operation="Worker.retrieve_episodic_experience",
                    data={
                        "tokens":
                            total_tokens,
                        "cost":
                            cost_string,
                        "content":
                            "Retrieved similar subtask: " +
                            retrieved_similar_subtask + "\n" +
                            "Retrieved subtask experience: " +
                            retrieved_subtask_experience.strip(),
                        "duration":
                            retrieve_time
                    })
                Tu += "\nYou may refer to some similar subtask experience if you think they are useful. {}".format(
                    retrieved_similar_subtask + "\n" +
                    retrieved_subtask_experience)

            prefix_message = f"SUBTASK_DESCRIPTION is {subtask}\n\nTASK_DESCRIPTION is {Tu}\n\nFUTURE_TASKS is {', '.join([f.name for f in future_tasks])}\n\nDONE_TASKS is {', '.join(d.name for d in done_task)}"

        # Reflection generation does not add its own response, it only gets the trajectory
        reflection = None
        if self.enable_reflection:
            # Load the initial subtask info
            if self.turn_count == 0:
                text_content = textwrap.dedent(f"""
                    Subtask Description: {subtask}
                    Subtask Information: {subtask_info}
                    Current Trajectory below:
                    """)
                self.reflection_agent.tools["traj_reflector"].llm_agent.add_message(
                    text_content +
                    "\n\nThe initial screen is provided. No action has been taken yet.",
                    image_content=obs["screenshot"],
                    role="user")

            else:
                if self.planner_history and self.planner_history[-1] is not None:
                    text_content = self.clean_worker_generation_for_reflection(
                        self.planner_history[-1])
                else:
                    text_content = "No previous action available for reflection"

                reflection_start = time.time()
                reflection, total_tokens, cost_string = self.reflection_agent.execute_tool(
                    "traj_reflector", {
                        "str_input": text_content,
                        "img_input": obs["screenshot"]
                    })
                logger.info(
                    f"Trajectory reflector tokens: {total_tokens}, cost: {cost_string}"
                )
                reflection_time = time.time() - reflection_start
                logger.info(
                    f"[Timing] Worker.traj_reflector execution time: {reflection_time:.2f} seconds"
                )
                self.reflections.append(reflection)
                logger.info("REFLECTION: %s", reflection)
                self.global_state.log_operation(module="manager",
                                                operation="reflection",
                                                data={
                                                    "tokens": total_tokens,
                                                    "cost": cost_string,
                                                    "content": reflection,
                                                    "duration": reflection_time
                                                })

        generator_message = ""

        # Only provide subinfo in the very first message to avoid over influence and redundancy
        if self.turn_count == 0:
            generator_message += prefix_message
            generator_message += f"Remember only complete the subtask: {subtask}\n"
            generator_message += f"You can use this extra information for completing the current subtask: {subtask_info}.\n"
        else:
            agent_log = agent_log_to_string(self.global_state.get_agent_log())
            generator_message += f"\nYour previous action was: {self.latest_action}\n"
            generator_message += (
                f"\nYou may use this reflection on the previous action and overall trajectory: {reflection}\n"
                if reflection and self.turn_count > 0 else "")
            generator_message += f"Please refer to the agent log to understand the progress and context of the task so far.\n{agent_log}"

        action_generator_start = time.time()
        plan, total_tokens, cost_string = self.generator_agent.execute_tool(
            "action_generator_with_takeover"
            if self.enable_takeover else "action_generator", {
                "str_input": generator_message,
                "img_input": obs["screenshot"]
            })
        logger.info(
            f"Action generator tokens: {total_tokens}, cost: {cost_string}")
        action_generator_time = time.time() - action_generator_start
        logger.info(
            f"[Timing] Worker.action_generator execution time: {action_generator_time:.2f} seconds"
        )

        self.planner_history.append(plan)
        logger.info("Action Plan: %s", plan)
        self.global_state.log_operation(module="worker",
                                        operation="action_plan",
                                        data={
                                            "tokens": total_tokens,
                                            "cost": cost_string,
                                            "content": plan,
                                            "duration": action_generator_time
                                        })

        # Add the generated plan to the agent log as passive memory
        self.global_state.add_agent_log({"type": "passive", "content": plan})

        try:
            action_code = parse_single_code_from_string(
                plan.split("Grounded Action")[-1])
            action_code = sanitize_code(action_code)
            self.latest_action = extract_first_agent_function(action_code)
        except Exception as e:
            logger.warning(f"Failed to parse action from plan: {e}")
            self.latest_action = None

        executor_info = {
            "current_subtask": subtask,
            "current_subtask_info": subtask_info,
            "executor_plan": plan,
            "reflection": reflection,
        }
        self.turn_count += 1

        self.screenshot_inputs.append(obs["screenshot"])

        return executor_info

    # Removes the previous action verification, and removes any extraneous grounded actions
    def clean_worker_generation_for_reflection(self,
                                               worker_generation: str) -> str:
        # Remove the previous action verification
        res = worker_generation[worker_generation.find("(Screenshot Analysis)"
                                                      ):]
        action = extract_first_agent_function(worker_generation)
        # Cut off extra grounded actions
        res = res[:res.find("(Grounded Action)")]
        res += f"(Grounded Action)\n```python\n{action}\n```\n"
        return res