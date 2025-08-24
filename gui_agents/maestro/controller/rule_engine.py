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
        max_state_switches: int = 100, 
        max_state_duration: int = 300
    ):
        self.global_state = global_state
        self.max_state_switches = max_state_switches
        self.max_state_duration = max_state_duration
        
    def check_task_state_rules(self, state_switch_count: int) -> Optional[ControllerState]:
        """检查task_state相关规则，包括终止条件"""
        try:
            task = self.global_state.get_task()
            if not task:
                return None

            # 检查状态切换次数上限
            if state_switch_count >= self.max_state_switches:
                logger.warning(
                    f"Maximum state switches ({self.max_state_switches}) reached"
                )
                self.global_state.update_task_status(TaskStatus.REJECTED)

            # 检查任务状态
            if task.status == "completed":
                logger.info("Task marked as completed")

            # 检查规划次数上限 - 如果规划次数超过10次，标记任务为失败
            plan_num = self.global_state.get_plan_num()
            if plan_num > 10:
                logger.warning(
                    f"Plan number ({plan_num}) exceeds limit (10), marking task as REJECTED")
                self.global_state.update_task_status(TaskStatus.REJECTED)
                return ControllerState.DONE

            # current_step大于50步 - rejected/fulfilled
            if state_switch_count > 50:
                # 检查是否所有subtask都完成
                if not task.pending_subtask_ids or len(task.pending_subtask_ids) == 0:
                    logger.info(f"State switch count > 50 and all subtasks completed, entering final check")
                    return ControllerState.FINAL_CHECK
                else:
                    logger.warning(
                        f"State switch count > 50 but subtasks not completed, marking task as REJECTED"
                    )
                    self.global_state.update_task_status(TaskStatus.REJECTED)

            return None

        except Exception as e:
            logger.error(f"Error checking task state rules: {e}")
            return None
    
    def check_current_state_rules(self) -> Optional[ControllerState]:
        """检查current_state相关规则"""
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
                    return ControllerState.QUALITY_CHECK
            else:
                # 如果没有质检记录且当前subtask的command数量>=5，进行首次质检
                if task.current_subtask_id:
                    subtask = self.global_state.get_subtask(task.current_subtask_id)
                    if (subtask and len(subtask.command_trace_ids) >= 5 and 
                        self.global_state.get_controller_current_state() not in [ControllerState.QUALITY_CHECK, ControllerState.DONE]):
                        logger.info(f"First quality check after 5 commands for subtask {task.current_subtask_id}, switching to QUALITY_CHECK")
                        return ControllerState.QUALITY_CHECK

            # 相同连续动作高于3次 - QUALITY_CHECK
            # 检查当前subtask的command_trace数量
            # if task.current_subtask_id:
            #     subtask = self.global_state.get_subtask(task.current_subtask_id)
            #     if subtask and len(subtask.command_trace_ids) >= 3:
            #         logger.info(
            #             f"Subtask {task.current_subtask_id} has >= 3 commands, switching to QUALITY_CHECK"
            #         )
            #         return ControllerState.QUALITY_CHECK

            # 如果一个subtask的执行action过长，超过15次 - REPLAN
            if task.current_subtask_id:
                subtask = self.global_state.get_subtask(task.current_subtask_id)
                if subtask and len(subtask.command_trace_ids) > 10:
                    logger.info(
                        f"Subtask {task.current_subtask_id} has > 10 commands, switching to PLAN"
                    )
                    return ControllerState.PLAN

            return None

        except Exception as e:
            logger.error(f"Error checking current situation rules: {e}")
            return None
    
    def is_state_timeout(self) -> bool:
        """检查当前状态是否超时"""
        state_start_time = self.global_state.get_controller_state_start_time()
        return (time.time() - state_start_time) > self.max_state_duration
    
    def determine_trigger_code(self, new_state: ControllerState, trigger: str, trigger_details: str) -> str:
        """根据状态切换情况确定trigger_code"""
        try:
            # 根据trigger字符串匹配对应的TriggerCode
            if "worker_success" in trigger:
                return TriggerCode.WORKER_SUCCESS.value
            elif "worker_cannot_execute" in trigger:
                return TriggerCode.WORK_CANNOT_EXECUTE.value
            elif "worker_stale_progress" in trigger:
                return TriggerCode.WORKER_STALE_PROGRESS.value
            elif "worker_generate_action" in trigger:
                return TriggerCode.WORKER_GENERATE_ACTION.value
            elif "worker_supplement" in trigger:
                return TriggerCode.WORKER_SUPPLEMENT.value
            elif "quality_check_passed" in trigger:
                return TriggerCode.EVALUATOR_GATE_DONE_FINAL_CHECK.value
            elif "quality_check_failed" in trigger:
                return TriggerCode.EVALUATOR_GATE_FAIL_GET_ACTION.value
            elif "quality_check_supplement" in trigger:
                return TriggerCode.EVALUATOR_GATE_SUPPLEMENT.value
            elif "quality_check_execute_action" in trigger:
                return TriggerCode.EVALUATOR_GATE_CONTINUE.value
            elif "final_check_passed" in trigger:
                return TriggerCode.FINAL_CHECK_GATE_DONE.value
            elif "final_check_failed" in trigger:
                return TriggerCode.FINAL_CHECK_GATE_FAIL.value
            elif "all_subtasks_completed" in trigger:
                return TriggerCode.EVALUATOR_GATE_DONE_FINAL_CHECK.value
            elif "subtask_ready" in trigger:
                return TriggerCode.MANAGER_GET_ACTION.value
            elif "no_subtasks" in trigger or "planning_timeout" in trigger:
                return TriggerCode.MANAGER_REPLAN.value
            elif "supplement_completed" in trigger:
                return TriggerCode.MANAGER_GET_ACTION.value
            elif "command_completed" in trigger:
                return TriggerCode.HARDWARE_GET_ACTION.value
            elif "execution_error" in trigger:
                return TriggerCode.WORK_CANNOT_EXECUTE.value
            elif "timeout" in trigger:
                return TriggerCode.EVALUATOR_GATE_FAIL_GET_ACTION.value
            elif "error" in trigger:
                return TriggerCode.EVALUATOR_GATE_FAIL_GET_ACTION.value
            elif "unknown_state" in trigger:
                return TriggerCode.EVALUATOR_GATE_FAIL_GET_ACTION.value
            elif "subtask_not_found" in trigger:
                return TriggerCode.MANAGER_GET_ACTION.value
            elif "no_worker_decision" in trigger:
                return TriggerCode.MANAGER_REPLAN.value
            elif "get_action_error" in trigger:
                return TriggerCode.MANAGER_REPLAN.value
            elif "quality_check_error" in trigger:
                return TriggerCode.EVALUATOR_GATE_FAIL_GET_ACTION.value
            elif "plan_error" in trigger:
                return TriggerCode.MANAGER_REPLAN.value
            elif "supplement_error" in trigger:
                return TriggerCode.MANAGER_REPLAN.value
            elif "final_check_error" in trigger:
                return TriggerCode.EVALUATOR_GATE_FAIL_GET_ACTION.value
            elif "final_check_pending" in trigger:
                return TriggerCode.MANAGER_GET_ACTION.value
            elif "final_check_timeout" in trigger:
                return TriggerCode.MANAGER_REPLAN.value
            elif "init_error" in trigger:
                return TriggerCode.MANAGER_REPLAN.value
            elif "error_recovery" in trigger:
                return TriggerCode.EVALUATOR_GATE_FAIL_GET_ACTION.value
            elif "error_recovery_single_step" in trigger:
                return TriggerCode.EVALUATOR_GATE_FAIL_GET_ACTION.value
            elif "no_command" in trigger:
                return TriggerCode.WORKER_GENERATE_ACTION.value
            elif "no_current_subtask_id" in trigger:
                return TriggerCode.MANAGER_GET_ACTION.value
            elif "subtask_ready" in trigger:
                return TriggerCode.MANAGER_GET_ACTION.value
            elif "replan" in trigger:
                return TriggerCode.MANAGER_REPLAN.value
            elif "supplement" in trigger:
                return TriggerCode.MANAGER_REPLAN.value
            elif "rule_quality_check_steps" in trigger:
                return TriggerCode.RULE_QUALITY_CHECK_STEPS.value
            elif "rule_quality_check_repeated_actions" in trigger:
                return TriggerCode.RULE_QUALITY_CHECK_REPEATED_ACTIONS.value
            elif "rule_replan_long_execution" in trigger:
                return TriggerCode.RULE_REPLAN_LONG_EXECUTION.value
            else:
                # 默认返回controller
                return TriggerCode.HARDWARE_GET_ACTION.value
        except Exception as e:
            logger.warning(f"Error determining trigger_code: {e}")
            return TriggerCode.HARDWARE_GET_ACTION.value 