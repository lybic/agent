"""
New Controller Implementation
基于new_global_state.py的状态驱动控制器
负责状态切换和流程控制，不处理具体业务逻辑
"""

import time
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
import platform

from .new_global_state import NewGlobalState
from .new_manager import NewManager
from .enums import (
    ControllerState, SubtaskStatus, 
    GateDecision, GateTrigger
)

# 设置日志
logger = logging.getLogger(__name__)


class NewController:
    """新控制器实现"""
    
    def __init__(
        self, 
        global_state: NewGlobalState, 
        platform: str = platform.system().lower(),
        screen_size: List[int] = [1920, 1080],
        memory_root_path: str = os.getcwd(),
        memory_folder_name: str = "kb_s2",
        kb_release_tag: str = "v0.2.2",
        enable_takeover: bool = False,
        enable_search: bool = True,
    ):

        self.global_state = global_state
        self.platform = platform
        self.screen_size = screen_size
        self.memory_root_path = memory_root_path
        self.memory_folder_name = memory_folder_name
        self.kb_release_tag = kb_release_tag
        self.enable_takeover = enable_takeover
        self.enable_search = enable_search

        self.current_state = ControllerState.INIT
        self.state_start_time = time.time()
        self.max_state_duration = 300  # 5分钟最大状态持续时间
        self.state_switch_count = 0
        self.max_state_switches = 100  # 最大状态切换次数
        self.user_query = ""
        self.Tools_dict = {}
        
        # Load tools configuration from tools_config.json
        tools_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools", "tools_config.json")
        with open(tools_config_path, "r") as f:
            self.tools_config = json.load(f)
            print(f"Loaded tools configuration from: {tools_config_path}")
            for tool in self.tools_config["tools"]:
                tool_name = tool["tool_name"]
                self.Tools_dict[tool_name] = {
                    "provider": tool["provider"],
                    "model": tool["model_name"]
                }
            print(f"Tools configuration: {self.Tools_dict}")

        # Initialize agent's knowledge base path
        self.local_kb_path = os.path.join( self.memory_root_path, self.memory_folder_name)

        # Check if knowledge base exists
        kb_platform_path = os.path.join(self.local_kb_path, self.platform)
        if not os.path.exists(kb_platform_path):
            print(f"Warning: Knowledge base for {self.platform} platform not found in {self.local_kb_path}")
            os.makedirs(kb_platform_path, exist_ok=True)
            print(f"Created directory: {kb_platform_path}")
            # raise FileNotFoundError(f"Knowledge base path does not exist: {kb_platform_path}")
        else:
            print(f"Found local knowledge base path: {kb_platform_path}")

        self.manager = NewManager(self.Tools_dict, self.global_state, self.local_kb_path, self.platform, self.enable_search)
        
        # 初始化控制器状态
        self.global_state.reset_controller_state()
        logger.info("NewController initialized")
    
    def execute_main_loop(self) -> None:
        """主循环执行 - 基于状态状态机"""
        logger.info("Starting main loop execution")
        
        while True:
            try:
                # 检查是否应该终止
                if self._should_terminate():
                    logger.info("Main loop termination conditions met")
                    break
                
                # 获取当前状态
                current_state = self.get_current_state()
                logger.info(f"Current state: {current_state}")
                
                # 根据状态执行相应处理
                if current_state == ControllerState.INIT:
                    self.handle_init_state()
                elif current_state == ControllerState.GET_ACTION:
                    self.handle_get_action_state()
                elif current_state == ControllerState.EXECUTE_ACTION:
                    self.handle_et_action_state()
                elif current_state == ControllerState.QUALITY_CHECK:
                    self.handle_quality_check_state()
                elif current_state == ControllerState.PLAN:
                    self.handle_plan_state()
                elif current_state == ControllerState.SUPPLEMENT:
                    self.handle_supplement_state()
                elif current_state == ControllerState.DONE:
                    logger.info("Task completed, exiting main loop")
                    break
                else:
                    logger.error(f"Unknown state: {current_state}")
                    self.switch_to_state(ControllerState.INIT)
                
                # 状态间短暂等待
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                self.global_state.add_event("controller", "error", f"Main loop error: {str(e)}")
                # 错误恢复：回到INIT状态
                self.switch_to_state(ControllerState.INIT)
                time.sleep(1)
    
    def get_current_state(self) -> ControllerState:
        """获取当前状态"""
        return self.current_state
    
    def assess_state_transition(self) -> ControllerState:
        """基于globalstate评估应该切换到哪个状态"""
        try:
            task_state = self.global_state.controller_get_task_state()
            current_subtask = task_state["current_subtask"]
            
            if not current_subtask:
                return ControllerState.INIT
            
            subtask_status = current_subtask.status
            
            if subtask_status == SubtaskStatus.FULFILLED.value:
                return self._handle_subtask_completion()
            elif subtask_status == SubtaskStatus.REJECTED.value:
                return ControllerState.PLAN
            elif subtask_status == SubtaskStatus.STALE.value:
                return ControllerState.QUALITY_CHECK
            elif subtask_status == SubtaskStatus.PENDING.value:
                return ControllerState.GET_ACTION
            elif subtask_status == SubtaskStatus.READY.value:
                return ControllerState.GET_ACTION
            else:
                return ControllerState.GET_ACTION
                
        except Exception as e:
            logger.error(f"Error assessing state transition: {e}")
            return ControllerState.INIT
    
    def _handle_subtask_completion(self) -> ControllerState:
        """处理subtask完成后的逻辑"""
        try:
            task = self.global_state.get_task()
            pending_subtasks = task.pending_subtask_ids or []
            
            if pending_subtasks:
                # 还有待处理的subtask，继续执行
                next_subtask_id = pending_subtasks[0]
                self.global_state.set_current_subtask_id(next_subtask_id)
                logger.info(f"Moving to next subtask: {next_subtask_id}")
                return ControllerState.GET_ACTION
            else:
                # 所有subtask完成，进入终结阶段
                logger.info("All subtasks completed")
                return ControllerState.DONE
                
        except Exception as e:
            logger.error(f"Error handling subtask completion: {e}")
            return ControllerState.INIT
    
    def handle_init_state(self):
        """立项状态处理"""
        logger.info("Handling INIT state")
        
        try:
            # 检查是否有待处理的subtask
            task = self.global_state.get_task()
            pending_subtasks = task.pending_subtask_ids or []
            
            if pending_subtasks:
                # 有subtask，设置第一个为当前subtask
                first_subtask_id = pending_subtasks[0]
                self.global_state.set_current_subtask_id(first_subtask_id)
                self.global_state.update_controller_state(ControllerState.GET_ACTION)
                logger.info(f"Set current subtask: {first_subtask_id}")
                self.switch_to_state(ControllerState.GET_ACTION)
            else:
                # 没有subtask，需要创建
                self.global_state.update_controller_state(ControllerState.PLAN)
                logger.info("No subtasks available, switching to PLAN state")
                self.switch_to_state(ControllerState.PLAN)
                self.global_state.set_task_objective(self.user_query)
                
        except Exception as e:
            logger.error(f"Error in INIT state: {e}")
            self.global_state.add_event("controller", "error", f"INIT state error: {str(e)}")
            self.switch_to_state(ControllerState.PLAN)
    
    def handle_get_action_state(self):
        """取下一步动作阶段"""
        logger.info("Handling GET_ACTION state")
        
        try:
            current_subtask_id = self.global_state.get_task().current_subtask_id
            if not current_subtask_id:
                logger.warning("No current subtask ID, switching to INIT")
                self.switch_to_state(ControllerState.INIT)
                return
            
            # 检查subtask状态
            subtask = self.global_state.get_subtask(current_subtask_id)
            if not subtask:
                logger.warning(f"Subtask {current_subtask_id} not found, switching to INIT")
                self.switch_to_state(ControllerState.INIT)
                return
            
            # 根据subtask状态决定下一步
            subtask_status = subtask.status
            logger.info(f"Subtask {current_subtask_id} status: {subtask_status}")
            
            if subtask_status == SubtaskStatus.READY.value:
                # 准备执行，切换到ET_ACTION
                self.global_state.update_controller_state(ControllerState.EXECUTE_ACTION)
                logger.info(f"Subtask {current_subtask_id} ready for execution")
                self.switch_to_state(ControllerState.EXECUTE_ACTION)
            elif subtask_status == SubtaskStatus.PENDING.value:
                # 等待中，可能需要补充资料
                self.global_state.update_controller_state(ControllerState.SUPPLEMENT)
                logger.info(f"Subtask {current_subtask_id} needs supplement")
                self.switch_to_state(ControllerState.SUPPLEMENT)
            else:
                # 其他状态，继续等待或重规划
                logger.info(f"Subtask {current_subtask_id} in unexpected status, switching to PLAN")
                self.switch_to_state(ControllerState.PLAN)
                
        except Exception as e:
            logger.error(f"Error in GET_ACTION state: {e}")
            self.global_state.add_event("controller", "error", f"GET_ACTION state error: {str(e)}")
            self.switch_to_state(ControllerState.PLAN)
    
    def handle_et_action_state(self):
        """执行动作阶段"""
        logger.info("Handling ET_ACTION state")
        
        try:
            current_subtask_id = self.global_state.get_task().current_subtask_id
            if not current_subtask_id:
                logger.warning("No current subtask ID in ET_ACTION state")
                self.switch_to_state(ControllerState.INIT)
                return
            
            # 等待Worker执行完成
            # 检查执行结果
            subtask = self.global_state.get_subtask(current_subtask_id)
            if not subtask:
                logger.warning(f"Subtask {current_subtask_id} not found in ET_ACTION state")
                self.switch_to_state(ControllerState.INIT)
                return
            
            subtask_status = subtask.status
            logger.info(f"Subtask {current_subtask_id} status in ET_ACTION: {subtask_status}")
            
            if subtask_status == SubtaskStatus.FULFILLED.value:
                # 执行成功，进入质检
                self.global_state.update_controller_state(ControllerState.QUALITY_CHECK)
                logger.info(f"Subtask {current_subtask_id} execution successful, switching to QUALITY_CHECK")
                self.switch_to_state(ControllerState.QUALITY_CHECK)
            elif subtask_status == SubtaskStatus.REJECTED.value:
                # 执行失败，需要重规划
                self.global_state.update_controller_state(ControllerState.PLAN)
                logger.info(f"Subtask {current_subtask_id} execution failed, switching to PLAN")
                self.switch_to_state(ControllerState.PLAN)
            elif subtask_status == SubtaskStatus.STALE.value:
                # 执行过时，进入质检
                self.global_state.update_controller_state(ControllerState.QUALITY_CHECK)
                logger.info(f"Subtask {current_subtask_id} execution stale, switching to QUALITY_CHECK")
                self.switch_to_state(ControllerState.QUALITY_CHECK)
            else:
                # 继续等待执行完成
                logger.debug(f"Waiting for subtask {current_subtask_id} execution to complete")
                # 检查是否超时
                if self._is_state_timeout():
                    logger.warning(f"ET_ACTION state timeout for subtask {current_subtask_id}")
                    self.global_state.update_controller_state(ControllerState.PLAN)
                    self.switch_to_state(ControllerState.PLAN)
                
        except Exception as e:
            logger.error(f"Error in ET_ACTION state: {e}")
            self.global_state.add_event("controller", "error", f"ET_ACTION state error: {str(e)}")
            self.switch_to_state(ControllerState.PLAN)
    
    def handle_quality_check_state(self):
        """质检门检查阶段"""
        logger.info("Handling QUALITY_CHECK state")
        
        try:
            current_subtask_id = self.global_state.get_task().current_subtask_id
            if not current_subtask_id:
                logger.warning("No current subtask ID in QUALITY_CHECK state")
                self.switch_to_state(ControllerState.INIT)
                return
            
            # 等待Evaluator完成质检
            # 检查质检结果
            gate_checks = self.global_state.get_gate_checks()
            latest_gate = None
            
            for gate in gate_checks:
                if gate.subtask_id == current_subtask_id:
                    if not latest_gate or gate.created_at > latest_gate.created_at:
                        latest_gate = gate
            
            if latest_gate:
                decision = latest_gate.decision
                logger.info(f"Latest gate check decision for subtask {current_subtask_id}: {decision}")
                
                if decision == GateDecision.GATE_DONE.value:
                    # 质检通过，subtask完成
                    self.global_state.update_subtask_status(
                        current_subtask_id, 
                        SubtaskStatus.FULFILLED,
                        "Quality check passed"
                    )
                    logger.info(f"Quality check passed for subtask {current_subtask_id}")
                    self.switch_to_state(ControllerState.GET_ACTION)
                elif decision == GateDecision.GATE_FAIL.value:
                    # 质检失败，需要重规划
                    self.global_state.update_controller_state(ControllerState.PLAN)
                    logger.info(f"Quality check failed for subtask {current_subtask_id}")
                    self.switch_to_state(ControllerState.PLAN)
                elif decision == GateDecision.GATE_SUPPLEMENT.value:
                    # 需要补充资料
                    self.global_state.update_controller_state(ControllerState.SUPPLEMENT)
                    logger.info(f"Quality check requires supplement for subtask {current_subtask_id}")
                    self.switch_to_state(ControllerState.SUPPLEMENT)
                else:
                    # 继续质检
                    logger.debug(f"Waiting for quality check completion for subtask {current_subtask_id}")
                    # 检查是否超时
                    if self._is_state_timeout():
                        logger.warning(f"QUALITY_CHECK state timeout for subtask {current_subtask_id}")
                        self.global_state.update_controller_state(ControllerState.PLAN)
                        self.switch_to_state(ControllerState.PLAN)
            else:
                # 没有质检记录，继续等待
                logger.debug(f"No gate checks found for subtask {current_subtask_id}")
                if self._is_state_timeout():
                    logger.warning(f"QUALITY_CHECK state timeout (no gate checks) for subtask {current_subtask_id}")
                    self.global_state.update_controller_state(ControllerState.PLAN)
                    self.switch_to_state(ControllerState.PLAN)
                
        except Exception as e:
            logger.error(f"Error in QUALITY_CHECK state: {e}")
            self.global_state.add_event("controller", "error", f"QUALITY_CHECK state error: {str(e)}")
            self.switch_to_state(ControllerState.PLAN)
    
    def handle_plan_state(self):
        """重规划阶段"""
        logger.info("Handling PLAN state")
        
        try:
            # 调用Manager进行重规划
            # 等待规划完成
            # 检查新的subtask列表
            self.manager.plan_task("replan")
            
            task = self.global_state.get_task()
            subtasks = self.global_state.get_subtasks()
            
            # 检查是否有新的subtask
            if subtasks:
                # 有subtask，重新开始
                self.global_state.update_controller_state(ControllerState.GET_ACTION)
                logger.info(f"Found {len(subtasks)} subtasks, restarting execution")
                self.switch_to_state(ControllerState.INIT)
            else:
                # 没有subtask，任务可能无法完成
                self.global_state.update_controller_state(ControllerState.PLAN)
                logger.warning("No subtasks available, continuing to wait for planning")
                # 继续等待或进入终结状态
                if self._is_state_timeout():
                    logger.error("PLAN state timeout, no subtasks created")
                    self.switch_to_state(ControllerState.DONE)
                
        except Exception as e:
            logger.error(f"Error in PLAN state: {e}")
            self.global_state.add_event("controller", "error", f"PLAN state error: {str(e)}")
            self.switch_to_state(ControllerState.INIT)
    
    def handle_supplement_state(self):
        """资料补全阶段"""
        logger.info("Handling SUPPLEMENT state")
        
        try:
            # 等待Manager补充资料
            # 检查补充状态

            self.manager.plan_task("supplement")
            
            # 检查supplement.md是否有更新
            supplement_content = self.global_state.get_supplement()
            
            # 如果资料补充完成，回到GET_ACTION
            self.global_state.update_controller_state(ControllerState.GET_ACTION)
            logger.info("Supplement state completed, returning to GET_ACTION")
            self.switch_to_state(ControllerState.GET_ACTION)
            
        except Exception as e:
            logger.error(f"Error in SUPPLEMENT state: {e}")
            self.global_state.add_event("controller", "error", f"SUPPLEMENT state error: {str(e)}")
            self.switch_to_state(ControllerState.GET_ACTION)
    
    def switch_to_state(self, new_state: ControllerState):
        """切换到新状态"""
        if new_state == self.current_state:
            logger.debug(f"Already in state {new_state}")
            return
        
        old_state = self.current_state
        self.current_state = new_state
        self.state_start_time = time.time()
        self.state_switch_count += 1
        
        # 记录状态切换事件
        self.global_state.add_event(
            "controller", 
            "state_switch", 
            f"State changed: {old_state} -> {new_state}"
        )
        
        # 更新controller状态
        try:
            self.global_state.update_controller_state(new_state)
        except Exception as e:
            logger.warning(f"Failed to update controller state: {e}")
        
        logger.info(f"State switched: {old_state} -> {new_state}")
    

    
    def _is_state_timeout(self) -> bool:
        """检查当前状态是否超时"""
        return (time.time() - self.state_start_time) > self.max_state_duration
    
    def _should_terminate(self) -> bool:
        """检查是否应该终止主循环"""
        # 检查状态切换次数
        if self.state_switch_count >= self.max_state_switches:
            logger.warning(f"Maximum state switches ({self.max_state_switches}) reached")
            return True
        
        # 检查任务状态
        try:
            task = self.global_state.get_task()
            if task.status == "completed":
                logger.info("Task marked as completed")
                return True
        except Exception as e:
            logger.warning(f"Failed to check task status: {e}")
        
        return False
    
    def get_controller_info(self) -> Dict[str, Any]:
        """获取控制器信息"""
        return {
            "current_state": self.current_state.value,
            "state_start_time": self.state_start_time,
            "state_switch_count": self.state_switch_count,
            "controller_state": self.global_state.get_controller_state(),
            "task_id": self.global_state.task_id
        }
    
    def reset_controller(self):
        """重置控制器状态"""
        logger.info("Resetting controller")
        self.current_state = ControllerState.INIT
        self.state_start_time = time.time()
        self.state_switch_count = 0
        self.global_state.reset_controller_state()
        logger.info("Controller reset completed") 