"""
Rule Engine for Agent-S Controller
负责处理各种业务规则和状态检查
"""

import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from gui_agents.maestro.new_global_state import NewGlobalState
from ..enums import ControllerState, TaskStatus, TriggerCode
from ..data_models import CommandData
from ..Action import Action

logger = logging.getLogger(__name__)


class RuleEngine:
    """规则引擎，负责处理各种业务规则和状态检查"""
    
    def __init__(
        self, 
        global_state: NewGlobalState, 
        max_steps: int = 50,
        max_state_switches: int = 100, 
        max_state_duration: int = 300,
        flow_config: Optional[Dict[str, Any]] = None,
    ):
        self.global_state = global_state
        self.max_steps = max_steps
        self.max_state_switches = max_state_switches
        self.max_state_duration = max_state_duration
        # 新增：流程配置阈值
        self.flow_config = flow_config or {}
        self.quality_check_interval_secs = self.flow_config.get("quality_check_interval_secs", 300)
        self.first_quality_check_min_commands = self.flow_config.get("first_quality_check_min_commands", 5)
        self.repeated_action_min_consecutive = self.flow_config.get("repeated_action_min_consecutive", 3)
        self.replan_long_execution_threshold = self.flow_config.get("replan_long_execution_threshold", 20)
        self.plan_number_limit = self.flow_config.get("plan_number_limit", 10)
    
    def _are_actions_similar(self, action1: Dict[str, Any], action2: Dict[str, Any]) -> bool:
        """检查两个 Action 是否相同（排除描述性字段）
        
        Args:
            action1: 第一个 Action 的字典表示
            action2: 第二个 Action 的字典表示
            
        Returns:
            bool: 如果两个 Action 相同则返回 True，否则返回 False
        """
        try:
            # 检查 Action 类型是否相同
            if action1.get("type") != action2.get("type"):
                return False
            
            # 获取 Action 类型
            action_type = action1.get("type")
            
            # 定义需要排除的描述性字段（这些字段不影响 Action 的实际执行）
            descriptive_fields = {
                "element_description",  # Click, DoubleClick, Move, Scroll
                "starting_description",  # Drag
                "ending_description",    # Drag
            }
            
            # 比较所有非描述性字段
            for key in action1:
                if key in descriptive_fields:
                    continue  # 跳过描述性字段
                
                if key not in action2:
                    return False
                
                if action1[key] != action2[key]:
                    return False
            
            # 检查 action2 中是否有 action1 中没有的字段（除了描述性字段）
            for key in action2:
                if key in descriptive_fields:
                    continue  # 跳过描述性字段
                
                if key not in action1:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error comparing actions: {e}")
            return False
    
    def _check_consecutive_similar_actions(self, commands: List[CommandData], min_consecutive: int = 3) -> bool:
        """检查是否有连续相同的 Action
        
        Args:
            commands: 命令列表
            min_consecutive: 最小连续次数
            
        Returns:
            bool: 如果发现连续相同的 Action 则返回 True，否则返回 False
        """
        try:
            if min_consecutive is None:
                min_consecutive = self.repeated_action_min_consecutive
            if len(commands) < min_consecutive:
                return False
            
            # 从最新的命令开始，检查连续的 Action
            consecutive_count = 1
            current_action = commands[-1].action
            
            # 从倒数第二个命令开始向前检查
            for i in range(len(commands) - 2, -1, -1):
                if self._are_actions_similar(current_action, commands[i].action):
                    consecutive_count += 1
                    if consecutive_count >= min_consecutive:
                        logger.info(f"Found {consecutive_count} consecutive similar actions")
                        return True
                else:
                    # 重置计数
                    consecutive_count = 1
                    current_action = commands[i].action
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking consecutive similar actions: {e}")
            return False
    
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

            # 检查规划次数上限 - 如果规划次数超过配置上限，标记任务为失败
            plan_num = self.global_state.get_plan_num()
            if plan_num > self.plan_number_limit:
                logger.warning(
                    f"Plan number ({plan_num}) exceeds limit ({self.plan_number_limit}), marking task as REJECTED")
                self.global_state.update_task_status(TaskStatus.REJECTED)
                return (ControllerState.DONE, TriggerCode.RULE_PLAN_NUMBER_EXCEEDED)

            # current_step大于max_steps步 - rejected/fulfilled
            if task.step_num >= self.max_steps:
                # 检查是否所有subtask都完成
                if not task.pending_subtask_ids or len(task.pending_subtask_ids) == 0:
                    logger.info(f"State switch count > {self.max_steps} and all subtasks completed, entering final check")
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

            # 距离上次质检过去了配置的时间 - QUALITY_CHECK
            gate_checks = self.global_state.get_gate_checks()
            if gate_checks:
                latest_quality_check = max(gate_checks, key=lambda x: x.created_at)
                latest_time = datetime.fromisoformat(
                    latest_quality_check.created_at)
                current_time = datetime.now()
                time_diff = current_time - latest_time

                if (time_diff.total_seconds() > self.quality_check_interval_secs and  # 配置时间间隔
                    self.global_state.get_controller_current_state() not in [ControllerState.QUALITY_CHECK, ControllerState.DONE]):
                    logger.info(f"{self.quality_check_interval_secs} seconds since last quality check, switching to QUALITY_CHECK")
                    return (ControllerState.QUALITY_CHECK, TriggerCode.RULE_QUALITY_CHECK_STEPS)
            else:
                # 如果没有质检记录且当前subtask的command数量达到阈值，进行首次质检
                if task.current_subtask_id:
                    subtask = self.global_state.get_subtask(task.current_subtask_id)
                    if (subtask and len(subtask.command_trace_ids) >= self.first_quality_check_min_commands and 
                        self.global_state.get_controller_current_state() not in [ControllerState.QUALITY_CHECK, ControllerState.DONE]):
                        logger.info(f"First quality check after {self.first_quality_check_min_commands} commands for subtask {task.current_subtask_id}, switching to QUALITY_CHECK")
                        return (ControllerState.QUALITY_CHECK, TriggerCode.RULE_QUALITY_CHECK_STEPS)

            # 相同连续动作高于配置次数 - QUALITY_CHECK
            if task.current_subtask_id:
                subtask = self.global_state.get_subtask(task.current_subtask_id)
                if subtask and len(subtask.command_trace_ids) >= self.repeated_action_min_consecutive:
                    # 获取当前 subtask 的所有命令
                    commands = self.global_state.get_commands_for_subtask(task.current_subtask_id)
                    if commands and self._check_consecutive_similar_actions(commands[-self.repeated_action_min_consecutive:], min_consecutive=self.repeated_action_min_consecutive):
                        logger.info(
                            f"Found {self.repeated_action_min_consecutive}+ consecutive similar actions in subtask {task.current_subtask_id}, switching to QUALITY_CHECK"
                        )
                        return (ControllerState.QUALITY_CHECK, TriggerCode.RULE_QUALITY_CHECK_REPEATED_ACTIONS)

            # 如果一个subtask的执行action过长，超过配置阈值 - REPLAN
            if task.current_subtask_id:
                subtask = self.global_state.get_subtask(task.current_subtask_id)
                if subtask and len(subtask.command_trace_ids) > self.replan_long_execution_threshold:
                    logger.info(
                        f"Subtask {task.current_subtask_id} has > {self.replan_long_execution_threshold} commands, switching to PLAN"
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
