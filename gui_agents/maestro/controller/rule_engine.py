"""
Rule Engine for Agent-S Controller
负责处理各种业务规则和状态检查
"""

import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from gui_agents.maestro.new_global_state import NewGlobalState
from ..enums import ControllerState, TaskStatus, TriggerCode

logger = logging.getLogger(__name__)


class RuleEngine:
    """规则引擎，负责处理各种业务规则和状态检查"""
    
    def __init__(
        self, 
        global_state: NewGlobalState, 
        max_steps: int = 50,
        max_state_switches: int = 100, 
        max_state_duration: int = 300
    ):
        self.global_state = global_state
        self.max_steps = max_steps
        self.max_state_switches = max_state_switches
        self.max_state_duration = max_state_duration
        
    def check_task_state_rules(self, state_switch_count: int) -> Optional[tuple[ControllerState, TriggerCode]]:
        """检查task_state相关规则，包括终止条件
        
        Returns:
            Optional[tuple[ControllerState, TriggerCode]]: 返回新状态和对应的TriggerCode，如果没有规则触发则返回None
        """
        try:
            task = self.global_state.get_task()
            if not task:
                return None

            # # 检查状态切换次数上限
            # if state_switch_count >= self.max_state_switches:
            #     logger.warning(
            #         f"Maximum state switches ({self.max_state_switches}) reached"
            #     )
            #     self.global_state.update_task_status(TaskStatus.REJECTED)
            #     return (ControllerState.DONE, TriggerCode.RULE_MAX_STATE_SWITCHES_REACHED)

            # 检查任务状态
            if task.status == "completed":
                logger.info("Task marked as completed")
                return (ControllerState.DONE, TriggerCode.RULE_TASK_COMPLETED)

            # 检查规划次数上限 - 如果规划次数超过10次，标记任务为失败
            plan_num = self.global_state.get_plan_num()
            if plan_num > 10:
                logger.warning(
                    f"Plan number ({plan_num}) exceeds limit (10), marking task as REJECTED")
                self.global_state.update_task_status(TaskStatus.REJECTED)
                return (ControllerState.DONE, TriggerCode.RULE_PLAN_NUMBER_EXCEEDED)

            # current_step大于max_steps步 - rejected/fulfilled
            if task.step_num >= self.max_steps:
                # 检查是否所有subtask都完成
                if not task.pending_subtask_ids or len(task.pending_subtask_ids) == 0:
                    logger.info(f"State switch count > 50 and all subtasks completed, entering final check")
                    return (ControllerState.FINAL_CHECK, TriggerCode.RULE_STATE_SWITCH_COUNT_EXCEEDED)
                else:
                    logger.warning(
                        f"Step number ({task.step_num}) >= max_steps ({self.max_steps}) but subtasks not completed, marking task as REJECTED"
                    )
                    self.global_state.update_task_status(TaskStatus.REJECTED)
                    return (ControllerState.DONE, TriggerCode.RULE_STATE_SWITCH_COUNT_EXCEEDED)

            return None

        except Exception as e:
            logger.error(f"Error checking task state rules: {e}")
            return None
    
    def check_current_state_rules(self) -> Optional[tuple[ControllerState, TriggerCode]]:
        """检查current_state相关规则
        
        Returns:
            Optional[tuple[ControllerState, TriggerCode]]: 返回新状态和对应的TriggerCode，如果没有规则触发则返回None
        """
        try:
            task = self.global_state.get_task()
            if not task:
                return None

            # 距离上次质检过去了5步 - QUALITY_CHECK
            gate_checks = self.global_state.get_gate_checks()
            if gate_checks:
                latest_quality_check = max(gate_checks,
                                           key=lambda x: x.created_at)
                latest_time = datetime.fromisoformat(
                    latest_quality_check.created_at)
                current_time = datetime.now()
                time_diff = current_time - latest_time

                if (time_diff.total_seconds() > 300 and  # 5分钟 = 300秒
                    self.global_state.get_controller_current_state() not in [ControllerState.QUALITY_CHECK, ControllerState.DONE]):
                    logger.info(f"5 minutes since last quality check, switching to QUALITY_CHECK")
                    return (ControllerState.QUALITY_CHECK, TriggerCode.RULE_QUALITY_CHECK_STEPS)
            else:
                # 如果没有质检记录且当前subtask的command数量>=5，进行首次质检
                if task.current_subtask_id:
                    subtask = self.global_state.get_subtask(task.current_subtask_id)
                    if (subtask and len(subtask.command_trace_ids) >= 5 and 
                        self.global_state.get_controller_current_state() not in [ControllerState.QUALITY_CHECK, ControllerState.DONE]):
                        logger.info(f"First quality check after 5 commands for subtask {task.current_subtask_id}, switching to QUALITY_CHECK")
                        return (ControllerState.QUALITY_CHECK, TriggerCode.RULE_QUALITY_CHECK_STEPS)

            # 相同连续动作高于3次 - QUALITY_CHECK
            # 检查当前subtask的command_trace数量
            # if task.current_subtask_id:
            #     subtask = self.global_state.get_subtask(task.current_subtask_id)
            #     if subtask and len(subtask.command_trace_ids) >= 3:
            #         logger.info(
            #             f"Subtask {task.current_subtask_id} has >= 3 commands, switching to QUALITY_CHECK"
            #         )
            #         return (ControllerState.QUALITY_CHECK, TriggerCode.RULE_QUALITY_CHECK_REPEATED_ACTIONS)

            # 如果一个subtask的执行action过长，超过10次 - REPLAN
            if task.current_subtask_id:
                subtask = self.global_state.get_subtask(task.current_subtask_id)
                if subtask and len(subtask.command_trace_ids) > 10:
                    logger.info(
                        f"Subtask {task.current_subtask_id} has > 10 commands, switching to PLAN"
                    )
                    return (ControllerState.PLAN, TriggerCode.RULE_REPLAN_LONG_EXECUTION)

            return None

        except Exception as e:
            logger.error(f"Error checking current situation rules: {e}")
            return None
    
    def is_state_timeout(self) -> bool:
        """检查当前状态是否超时"""
        state_start_time = self.global_state.get_controller_state_start_time()
        return (time.time() - state_start_time) > self.max_state_duration
