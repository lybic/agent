import json
import logging
import os
import platform
import textwrap
from typing import Dict, List, Optional, Tuple

from gui_agents.agents.grounding import Grounding
from gui_agents.utils.common_utils import (
    parse_single_code_from_string,
    sanitize_code,
    extract_first_agent_function,
    agent_log_to_string,
)
from gui_agents.tools.tools import Tools
from gui_agents.agents.global_state import GlobalState
from gui_agents.store.registry import Registry

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