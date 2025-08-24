"""
State Machine for Agent-S Controller
负责状态切换和流程控制
"""

import time
import logging
from typing import Dict, Any

from gui_agents.maestro.controller.rule_engine import RuleEngine
from gui_agents.maestro.controller.state_handlers import StateHandlers
from gui_agents.maestro.new_global_state import NewGlobalState
from ..enums import ControllerState

logger = logging.getLogger(__name__)


class StateMachine:
    """状态机，负责状态切换和流程控制"""
    
    def __init__(self, 
        global_state: NewGlobalState, 
        rule_engine: RuleEngine, 
        state_handlers: StateHandlers
    ):
        self.global_state = global_state
        self.rule_engine = rule_engine
        self.state_handlers = state_handlers
        self.state_switch_count = 0
        
    def get_current_state(self) -> ControllerState:
        """获取当前状态"""
        return self.global_state.get_controller_current_state()
    
    def switch_state(self, new_state: ControllerState, trigger: str = "controller", trigger_details: str = ""):
        """切换到新状态"""
        if new_state == self.get_current_state():
            logger.debug(f"Already in state {new_state}")
            return

        old_state = self.get_current_state()
        self.state_switch_count += 1

        # 根据触发情况确定trigger_code
        trigger_code = self.rule_engine.determine_trigger_code(new_state, trigger, trigger_details)

        # 记录状态切换事件
        self.global_state.add_event(
            "controller", "state_switch",
            f"State changed: {old_state} -> {new_state} (trigger: {trigger}, details: {trigger_details}, trigger_code: {trigger_code})"
        )

        # 更新controller状态，包含trigger_code
        try:
            self.global_state.update_controller_state(new_state, trigger, trigger_details, trigger_code)
        except Exception as e:
            logger.warning(f"Failed to update controller state: {e}")

        logger.info(
            f"State switched: {old_state} -> {new_state} "
            f"(trigger: {trigger}, details: {trigger_details}, trigger_code: {trigger_code})"
        )
    
    def process_rules_and_update_states(self) -> None:
        """处理规则并更新状态 - 每次循环结束后调用"""
        try:
            # 1. 检查任务状态规则
            new_state = self.rule_engine.check_task_state_rules(self.state_switch_count)
            if new_state:
                self.switch_state(new_state, "rule_task_state", f"Task state rule triggered: {new_state}")

            # 2. 检查当前状态规则
            new_state = self.rule_engine.check_current_state_rules()
            if new_state:
                self.switch_state(new_state, "rule_current_state", f"Current state rule triggered: {new_state}")

        except Exception as e:
            logger.error(f"Error in rule processing: {e}")
            self.global_state.log_operation(
                "controller", "error",
                {"error": f"Rule processing error: {str(e)}"})
    
    def should_exit_loop(self) -> bool:
        """判断是否应该跳出主循环"""
        try:
            task = self.global_state.get_task()

            if not task:
                return False
            task_status = task.status

            if task_status == "fulfilled":
                logger.info("Task fulfilled, should exit loop")
                return True
            elif task_status == "rejected":
                logger.info("Task rejected, should exit loop")
                return True
                
            return False

        except Exception as e:
            logger.error(f"Error checking exit condition: {e}")
            return False
    
    def get_state_switch_count(self) -> int:
        """获取状态切换次数"""
        return self.state_switch_count
    
    def reset_state_switch_count(self):
        """重置状态切换次数"""
        self.state_switch_count = 0
        logger.info("State switch count reset to 0") 