"""
Operator Module for GUI-Agent Architecture (agents3)
- Merges action planning (LLM) and visual grounding
- Generates next UI action and grounds it to screen coordinates
- Produces Action dicts compatible with agents3 Action.py and hardware_interface.py
"""

from __future__ import annotations

import time
import logging
from typing import Any, Dict, List, Optional

from gui_agents.tools.new_tools import NewTools
from gui_agents.utils.common_utils import (
    parse_single_code_from_string,
    sanitize_code,
    extract_first_agent_function,
)
from gui_agents.agents3.grounding import Grounding
from gui_agents.agents3.new_global_state import NewGlobalState

logger = logging.getLogger(__name__)


class Operator:
    """Operator role: generate next UI action and ground it to screen coordinates.

    Responsibilities:
    - Query the LLM action generator to propose the next grounded action (code snippet)
    - Parse the proposed action and extract intent + arguments
    - If necessary, run visual grounding to obtain precise coordinates
    - Return a normalized action dict compatible with `Action.py` for hardware execution

    """

    def __init__(
        self,
        tools_dict: Dict[str, Any],
        global_state: NewGlobalState,
        platform: str = "unknown",
        enable_search: bool = False,
        screen_size: List[int] = [1920, 1080],
    ) -> None:
        self.tools_dict = tools_dict
        self.global_state = global_state
        self.platform = platform
        self.enable_search = enable_search
        self.screen_size = screen_size

        # Embedding engine for Memory
        self.embedding_engine = NewTools()
        self.embedding_engine.register_tool(
            "embedding",
            self.tools_dict["embedding"]["provider"],
            self.tools_dict["embedding"]["model"],
        )

        # LLM for action generation
        self.operator_agent_name = "operator_role"
        tool_params = {}
        action_gen_cfg = self.tools_dict.get("action_generator", {})
        if self.enable_search:
            tool_params["enable_search"] = action_gen_cfg.get("enable_search", True)
            tool_params["search_provider"] = action_gen_cfg.get("search_provider", "bocha")
            tool_params["search_model"] = action_gen_cfg.get("search_model", "")
        else:
            tool_params["enable_search"] = False
        self.operator_agent = NewTools()
        self.operator_agent.register_tool(
            self.operator_agent_name,
            self.tools_dict[self.operator_agent_name]["provider"],
            self.tools_dict[self.operator_agent_name]["model"],
             **tool_params
        )

        # Visual grounding
        self.grounding_agent = Grounding(
            Tools_dict=self.tools_dict,
            platform=self.platform,
            width=self.screen_size[0],
            height=self.screen_size[1]
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_next_action(
        self,
        subtask: Dict[str, Any],
        guidance: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate and ground the next action for the given subtask.

        Returns a dict containing:
        - plan: raw LLM output text
        - action: JSON action dict (if ok)
        - step_result: StepResult as dict
        - outcome: one of {"generate_action", "CANNOT_EXECUTE", "STALE_PROGRESS"}
        """
        task = self.global_state.get_task()
        screenshot_bytes = self.global_state.get_screenshot()
        if not screenshot_bytes:
            # Without screenshot, we cannot ground; signal stale
            msg = "No screenshot available for action generation"
            logger.warning(msg)
            self.global_state.add_event("worker", "no_screenshot", msg)
            result = {
                "step_id": f"{subtask.get('subtask_id','unknown')}.step-0",
                "ok": False,
                "error": msg,
                "latency_ms": 0,
                "outcome": "STALE_PROGRESS",
            }
            return {
                "plan": "",
                "action": None,
                "step_result": result,
                "outcome": "STALE_PROGRESS",
            }

        # Build concise generator prompt
        subtask_title = subtask.get("title", "")
        subtask_desc = subtask.get("description", "")
        message = []
        message.append(f"Remember only complete the subtask: {subtask_title}")
        message.append(f"You can use this extra information for completing the current subtask: {subtask_desc}")
        if guidance:
            message.append(f"GUIDANCE: {guidance}")
        message.append("Return exactly one action as an agent.* function in Python fenced code under (Grounded Action).")
        generator_prompt = "\n\n".join(message)

        # Call action generator
        t0 = time.time()
        action_plan, total_tokens, cost_string = self.operator_agent.execute_tool(
            self.operator_agent_name,
            {"str_input": generator_prompt, "img_input": screenshot_bytes},
        )
        latency_ms = int((time.time() - t0) * 1000)
        self.global_state.add_event(
            "worker",
            "action_plan_generated",
            f"tokens={total_tokens}, cost={cost_string}",
        )

        # Parse action code
        try:
            current_width, current_height = self.global_state.get_screen_size()
            self.grounding_agent.reset_screen_size(current_width, current_height)
            self.grounding_agent.assign_coordinates(action_plan, self.global_state.get_obs_for_grounding())

            action_code = parse_single_code_from_string(action_plan.split("Grounded Action")[-1])
            action_code = sanitize_code(action_code)
            self.global_state.add_event("worker", "generated_action_code", f"{action_code}")
        except Exception as e:
            err = f"PARSE_ACTION_FAILED: {e}"
            logger.warning(err)
            self.global_state.add_event("worker", "parse_action_failed", err)
            result = {
                "step_id": f"{subtask.get('subtask_id','unknown')}.step-1",
                "ok": False,
                "error": err,
                "latency_ms": latency_ms,
                "outcome": "CANNOT_EXECUTE",
            }
            return {
                "action_plan": action_plan,
                "action": None,
                "step_result": result,
                "outcome": "CANNOT_EXECUTE",
            }

        # Convert code into a normalized action dict
        agent: Grounding = self.grounding_agent
        try:
            plan_code = extract_first_agent_function(action_code)
            exec_code = eval(plan_code)  # type: ignore
            self.global_state.add_event("worker", "generated_exec_code", f"{exec_code}")
            ok = True
            # Determine outcome based on action type
            action_type = ""
            if isinstance(exec_code, dict):
                action_type = str(exec_code.get("type", ""))
            if action_type == "Done":
                outcome = "worker_done"
            elif action_type == "Failed":
                outcome = "worker_fail"
            elif action_type == "Supplement":
                outcome = "worker_supplement"
            elif action_type == "NeedQualityCheck":
                outcome = "worker_stale_progress"
            else:
                outcome = "worker_generate_action"

            err = None
        except Exception as e:
            ok = False
            outcome = "CANNOT_EXECUTE"
            exec_code = None
            err = f"BUILD_ACTION_FAILED: {e}"
            logger.warning(err)

        result = {
            "step_id": f"{subtask.get('subtask_id','unknown')}.step-1",
            "ok": ok,
            "error": err,
            "latency_ms": latency_ms,
            "outcome": outcome,
            "action": exec_code,
        }

        # Log
        self.global_state.add_event(
            "worker",
            "action_ready" if ok else "action_failed",
            f"outcome={outcome}",
        )
        return {
            "action_plan": action_plan,
            "action": exec_code,
            "step_result": result,
            "outcome": outcome,
        } 