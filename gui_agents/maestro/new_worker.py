"""
New Worker Module for GUI-Agent Architecture (agents3)
- Provides an Operator role that integrates action planning (LLM) and visual grounding
- Produces Action dicts compatible with agents3 `Action.py` and `hardware_interface.py`
- Uses `NewGlobalState` for observations and event logging

This implementation merges the essential behaviors of the legacy `worker.py` and `grounding.py` into a
single, concise Operator that is easy to invoke from the Controller.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from desktop_env.desktop_env import DesktopEnv

from gui_agents.maestro.new_global_state import NewGlobalState
from gui_agents.maestro.data_models import create_command_data
from gui_agents.maestro.enums import WorkerDecision

from .sub_worker.technician import Technician
from .sub_worker.analyst import Analyst
from .sub_worker.operator import Operator

logger = logging.getLogger(__name__)


class NewWorker:
    """Worker facade exposing specialized roles.

    Provides access to:
    - Operator: GUI interface operations with visual grounding
    - Technician: System-level operations via terminal commands
    - Analyst: Data analysis and recommendations
    """

    def __init__(
        self,
        tools_dict: Dict[str, Any],
        global_state: NewGlobalState,
        platform: str = "Windows",
        enable_search: bool = False,
        client_password: str = "",
        screen_size: List[int] = [1920, 1080],
    ) -> None:
        self.operator = Operator(
            tools_dict=tools_dict,
            global_state=global_state,
            platform=platform,
            enable_search=enable_search,
            screen_size=screen_size,
        )
        
        self.technician = Technician(
            tools_dict=tools_dict,
            global_state=global_state,
            platform=platform,
            client_password=client_password,
        )
            
        self.analyst = Analyst(
            tools_dict=tools_dict,
            global_state=global_state,
            platform=platform,
            enable_search=enable_search,
        )
        self._global_state = global_state
        self._tools_dict = tools_dict
        self._platform = platform

    def process_subtask_and_create_command(self) -> Optional[str]:
        """Route to the right role, create command/decision if applicable, and return worker_decision string.
        Returns one of WorkerDecision values or None on no-op/error.
        """
        subtask_id = self._global_state.get_task().current_subtask_id
        subtask = self._global_state.get_subtask(subtask_id) #type: ignore
        if not subtask:
            logging.warning(f"Worker: subtask {subtask_id} not found")
            return None

        # 获取当前的 trigger_code 来调整处理逻辑
        current_trigger_code = self._get_current_trigger_code()
        logger.info(f"Worker processing subtask {subtask_id} with trigger_code: {current_trigger_code}")

        role = (subtask.assignee_role or "operator").lower()
        try:
            if role == "operator":
                res = self.operator.generate_next_action(
                    subtask=subtask.to_dict(),  # type: ignore
                    trigger_code=current_trigger_code
                )
                outcome = (res.get("outcome") or "").strip()
                action = res.get("action")
                action_plan = res.get("action_plan", "")
                screenshot_analysis = res.get("screenshot_analysis", "")
                message = res.get("message", "")
                
                # Create command with complete information
                cmd = create_command_data(
                    command_id="", 
                    task_id=self._global_state.task_id, 
                    action=action or {}, 
                    subtask_id=subtask_id,
                    assignee_role=subtask.assignee_role or "operator"
                )
                command_id = self._global_state.add_command(cmd)
                
                pre_screenshot_analysis = screenshot_analysis
                pre_screenshot_id = self._global_state.get_screenshot_id()

                # Update command with all fields including message
                self._global_state.update_command_fields(
                    command_id,
                    assignee_role=subtask.assignee_role or "operator",
                    action=action or {},
                    pre_screenshot_id=pre_screenshot_id,
                    pre_screenshot_analysis=pre_screenshot_analysis,
                    message=message
                )

                # Update worker decision based on outcome
                if outcome == WorkerDecision.GENERATE_ACTION.value and action:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.GENERATE_ACTION.value)
                elif outcome == WorkerDecision.WORKER_DONE.value:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.WORKER_DONE.value)
                elif outcome == WorkerDecision.SUPPLEMENT.value:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.SUPPLEMENT.value)
                elif outcome == WorkerDecision.CANNOT_EXECUTE.value:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.CANNOT_EXECUTE.value)
                elif outcome == WorkerDecision.STALE_PROGRESS.value:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.STALE_PROGRESS.value)

            if role == "technician":
                res = self.technician.execute_task(
                    subtask=subtask.to_dict(),  # type: ignore
                    trigger_code=current_trigger_code
                )
                outcome = (res.get("outcome") or "").strip()
                action = res.get("action")
                command_plan = res.get("command_plan", "")
                screenshot_analysis = res.get("screenshot_analysis", "")
                message = res.get("message", "")
                
                # Create command with complete information
                cmd = create_command_data(
                    command_id="", 
                    task_id=self._global_state.task_id, 
                    action=action or {}, 
                    subtask_id=subtask_id,
                    assignee_role=subtask.assignee_role or "technician"
                )
                command_id = self._global_state.add_command(cmd)
                
                pre_screenshot_analysis = screenshot_analysis
                # Add screenshot and get ID
                pre_screenshot_id = self._global_state.get_screenshot_id()

                # Update command with all fields including message
                self._global_state.update_command_fields(
                    command_id,
                    assignee_role=subtask.assignee_role or "technician",
                    action=action or {},
                    pre_screenshot_id=pre_screenshot_id,
                    pre_screenshot_analysis=pre_screenshot_analysis,
                    message=message
                )

                # Update worker decision based on outcome
                if outcome == WorkerDecision.GENERATE_ACTION.value and action:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.GENERATE_ACTION.value)
                elif outcome == WorkerDecision.WORKER_DONE.value:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.WORKER_DONE.value)
                elif outcome == WorkerDecision.STALE_PROGRESS.value:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.STALE_PROGRESS.value)
                elif outcome == WorkerDecision.SUPPLEMENT.value:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.SUPPLEMENT.value)
                elif outcome == WorkerDecision.CANNOT_EXECUTE.value:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.CANNOT_EXECUTE.value)

            if role == "analyst":
                # 获取artifacts内容，用于分析
                artifacts_content = self._global_state.get_artifacts()
                
                # 检查是否有memorize相关的artifacts需要分析
                if "memorize" in artifacts_content.lower() or "information" in artifacts_content.lower():
                    # 如果有memorize内容，使用专门的memorize分析类型
                    res = self.analyst.analyze_task(
                        subtask=subtask.to_dict(), 
                        analysis_type="memorize_analysis",
                        guidance=artifacts_content
                    )
                else:
                    # 普通分析
                    res = self.analyst.analyze_task(
                        subtask=subtask.to_dict(), 
                        analysis_type="general"
                    )
                
                outcome = (res.get("outcome") or "").strip()
                analysis = res.get("analysis", "")
                recommendations = res.get("recommendations", [])
                extracted_data = res.get("extracted_data", {})
                
                # Create command with complete information
                cmd = create_command_data(
                    command_id="", 
                    task_id=self._global_state.task_id, 
                    action={"analysis": analysis, "recommendations": recommendations, "extracted_data": extracted_data}, 
                    subtask_id=subtask_id,
                    assignee_role=subtask.assignee_role or "analyst"
                )
                command_id = self._global_state.add_command(cmd)
                
                pre_screenshot_analysis = ""
                # Add screenshot and get ID
                pre_screenshot_id = self._global_state.get_screenshot_id()
                # Use the analysis result as pre_screenshot_analysis
                # pre_screenshot_analysis = analysis

                # Update command with all fields
                self._global_state.update_command_fields(
                    command_id,
                    assignee_role=subtask.assignee_role or "analyst",
                    action={"analysis": analysis, "recommendations": recommendations, "extracted_data": extracted_data},
                    pre_screenshot_id=pre_screenshot_id,
                    pre_screenshot_analysis=pre_screenshot_analysis
                )
                
                if outcome == "analysis_complete":
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.STALE_PROGRESS.value)
                    return WorkerDecision.STALE_PROGRESS.value
                elif outcome == "STALE_PROGRESS":
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.STALE_PROGRESS.value)
                    return WorkerDecision.STALE_PROGRESS.value
                else:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.CANNOT_EXECUTE.value)
                    return WorkerDecision.CANNOT_EXECUTE.value

            # logging.info(f"Worker: unknown assignee_role '{role}' for subtask {subtask_id}")
            return WorkerDecision.CANNOT_EXECUTE.value
        except Exception as e:
            logging.error(f"Worker: error processing subtask {subtask_id}: {e}")
            return WorkerDecision.CANNOT_EXECUTE.value

    def _get_current_trigger_code(self) -> str:
        """获取当前的 trigger_code"""
        try:
            controller_state = self._global_state.get_controller_state()
            return controller_state.get("trigger_code", "")
        except Exception as e:
            logger.warning(f"Failed to get current trigger_code: {e}")
            return ""


# Export friendly alias
Worker = NewWorker 