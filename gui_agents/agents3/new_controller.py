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

from gui_agents.agents3.data_models import SubtaskData, TaskData
from desktop_env.desktop_env import DesktopEnv
from gui_agents.agents3.hardware_interface import HardwareInterface
from PIL import Image

from gui_agents.agents3.utils.screenShot import scale_screenshot_dimensions

from .new_global_state import NewGlobalState
from .new_manager import NewManager
from .new_worker import NewWorker
from .evaluator import Evaluator
from .new_executor import NewExecutor
from .enums import (
    ControllerState, TaskStatus, SubtaskStatus, 
    GateDecision, GateTrigger, WorkerDecision
)
from gui_agents.agents3.Action import Screenshot

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
        backend: str = "pyautogui",
        user_query: str = "",
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
        self.user_query = user_query
        self.Tools_dict = {}

        # Load tools configuration from tools_config.json
        tools_config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "tools",
            "new_tools_config.json")
        with open(tools_config_path, "r") as f:
            self.tools_config = json.load(f)
            print(f"Loaded tools configuration from: {tools_config_path}")
            for tool in self.tools_config["tools"]:
                tool_name = tool["tool_name"]
                self.Tools_dict[tool_name] = {
                    "provider": tool["provider"],
                    "model": tool["model_name"]
                }
            # print(f"Tools configuration: {self.Tools_dict}")

        # Initialize agent's knowledge base path
        self.local_kb_path = os.path.join(self.memory_root_path,
                                          self.memory_folder_name)

        # Check if knowledge base exists
        kb_platform_path = os.path.join(self.local_kb_path, self.platform)
        if not os.path.exists(kb_platform_path):
            print(
                f"Warning: Knowledge base for {self.platform} platform not found in {self.local_kb_path}"
            )
            os.makedirs(kb_platform_path, exist_ok=True)
            print(f"Created directory: {kb_platform_path}")
            # raise FileNotFoundError(f"Knowledge base path does not exist: {kb_platform_path}")
        else:
            print(f"Found local knowledge base path: {kb_platform_path}")

        scaled_width, scaled_height = 1920, 1080
        self.env = DesktopEnv(
            provider_name="vmware",
            path_to_vm="path_to_vm",
            action_space="action_space",
            screen_size=(scaled_width, scaled_height),  # type: ignore
            headless=False,
            require_a11y_tree=False,
        )
        self.env_password = "password"

        self.manager = NewManager(self.Tools_dict, self.global_state,
                                  self.local_kb_path, self.platform,
                                  self.enable_search)
        self.worker = NewWorker(self.Tools_dict, self.global_state, self.env,
                                self.platform, self.enable_search,
                                self.env_password)
        self.evaluator = Evaluator(
            self.global_state,
            self.Tools_dict,
        )

        # 初始化硬件接口
        backend_kwargs = {"platform": platform}
        self.hwi = HardwareInterface(backend=backend, **backend_kwargs)
        logger.info(f"Hardware interface initialized with backend: {backend}")

        # 初始化执行器
        self.executor = NewExecutor(self.global_state, self.hwi, self.env)
        logger.info("Executor initialized")

        self._last_evaluated_subtask_id: Optional[str] = None

        # 初始化控制器状态
        self.global_state.reset_controller_state()
        logger.info("NewController initialized")

        screenshot: Image.Image = self.hwi.dispatch(
            Screenshot())  # type: ignore
        self.global_state.set_screenshot(
            scale_screenshot_dimensions(screenshot, self.hwi))

    def execute_single_step(self, steps: int = 1) -> None:
        """单步执行若干次状态机逻辑（执行 steps 步，不进入循环）"""
        if steps is None or steps <= 0:
            steps = 1
        try:
            for step_index in range(steps):
                # 1. 检查是否应该终止（单步序列）
                if self.should_exit_loop():
                    logger.info("Task fulfilled or rejected, terminating single step batch")
                    break

                # 2. 获取当前状态
                current_state = self.get_current_state()
                logger.info(
                    f"Current state (single step {step_index + 1}/{steps}): {current_state}"
                )

                # 3. 根据状态执行相应处理（一次一步）
                if current_state == ControllerState.INIT:
                    self.handle_init_state()
                elif current_state == ControllerState.GET_ACTION:
                    self.handle_get_action_state()
                elif current_state == ControllerState.EXECUTE_ACTION:
                    self.handle_execute_action_state()
                elif current_state == ControllerState.QUALITY_CHECK:
                    self.handle_quality_check_state()
                elif current_state == ControllerState.PLAN:
                    self.handle_plan_state()
                elif current_state == ControllerState.SUPPLEMENT:
                    self.handle_supplement_state()
                elif current_state == ControllerState.DONE:
                    logger.info("Task completed (single step sequence)")
                    break
                else:
                    logger.error(f"Unknown state: {current_state}")
                    self.switch_to_state(
                        ControllerState.INIT,
                        "unknown_state_single_step",
                        f"Unknown state encountered (single step): {current_state}",
                    )

                # 4. 每步结束后，处理规则并更新状态
                self.process_rules_and_update_states()

        except Exception as e:
            logger.error(f"Error in single step batch: {e}")
            self.global_state.add_event(
                "controller",
                "error",
                f"Single step batch error: {str(e)}",
            )
            # 错误恢复：回到INIT状态（单步序列）
            self.switch_to_state(
                ControllerState.INIT,
                "error_recovery_single_step",
                f"Error recovery from single step batch: {str(e)}",
            )

    def should_exit_loop(self) -> bool:
        """判断是否应该跳出主循环"""
        try:
            task = self.global_state.get_task()
            
            if not task:
                return False
            task_status = task.status
                            
            if task_status == TaskStatus.FULFILLED.value:
                logger.info("Task fulfilled, should exit loop")
                return True
            elif task_status == TaskStatus.REJECTED.value:
                logger.info("Task rejected, should exit loop")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error checking exit condition: {e}")
            return False

    def process_rules_and_update_states(self) -> None:
        """处理规则并更新状态 - 每次循环结束后调用"""
        try:
            # 1. 检查任务状态规则
            self._check_task_state_rules()

            # 2. 检查当前状态规则
            self._check_current_state_rules()
            
        except Exception as e:
            logger.error(f"Error in rule processing: {e}")
            self.global_state.add_event("controller", "error", f"Rule processing error: {str(e)}")

    def execute_main_loop(self) -> None:
        """主循环执行 - 基于状态状态机"""
        logger.info("Starting main loop execution")

        while True:
            try:
                # 1. 检查是否应该退出循环
                if self.should_exit_loop():
                    logger.info("Task fulfilled or rejected, breaking main loop")
                    break

                # 2. 获取当前状态
                current_state = self.get_current_state()
                logger.info(f"Current state: {current_state}")

                # 3. 根据状态执行相应处理
                if current_state == ControllerState.INIT:
                    self.handle_init_state()
                elif current_state == ControllerState.GET_ACTION:
                    self.handle_get_action_state()
                elif current_state == ControllerState.EXECUTE_ACTION:
                    self.handle_execute_action_state()
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
                    self.switch_to_state(
                        ControllerState.INIT, "unknown_state",
                        f"Unknown state encountered: {current_state}")

                # 4. 每次循环结束后，处理规则并更新状态
                self.process_rules_and_update_states()

                # 5. 状态间短暂等待
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                self.global_state.add_event("controller", "error",
                                            f"Main loop error: {str(e)}")
                # 错误恢复：回到INIT状态
                self.switch_to_state(
                    ControllerState.INIT, "error_recovery",
                    f"Error recovery from main loop: {str(e)}")
                time.sleep(1)

    def get_current_state(self) -> ControllerState:
        """获取当前状态"""
        return self.current_state


    # 不清楚作用，先保留
    def _handle_subtask_completion(self) -> ControllerState:
        """处理subtask完成后的逻辑"""
        try:
            task = self.global_state.get_task()
            pending_subtasks = task.pending_subtask_ids or []

            if pending_subtasks:
                # 还有待处理的subtask，继续执行
                next_subtask_id = pending_subtasks[0]
                self.global_state.advance_to_next_subtask()
                logger.info(f"Moving to next subtask: {next_subtask_id}")
                return ControllerState.GET_ACTION
            else:
                # 所有subtask完成，进入终结阶段
                logger.info("All subtasks completed")
                # 更新任务状态为完成
                self.global_state.update_task_status(TaskStatus.FULFILLED)
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
            pending_subtask_ids = task.pending_subtask_ids or []

            if pending_subtask_ids:
                # 有subtask，设置第一个为当前subtask
                first_subtask_id = pending_subtask_ids[0]
                self.global_state.advance_to_next_subtask()
                # 更新任务状态为进行中
                self.global_state.update_task_status(TaskStatus.PENDING)
                self.global_state.update_controller_state(
                    ControllerState.GET_ACTION)
                logger.info(f"Set current subtask: {first_subtask_id}")
                self.switch_to_state(ControllerState.GET_ACTION,
                                     "subtask_ready",
                                     f"First subtask {first_subtask_id} ready")
            else:
                # 没有subtask，需要创建
                self.global_state.update_controller_state(ControllerState.PLAN)
                logger.info("No subtasks available, switching to PLAN state")
                self.switch_to_state(ControllerState.PLAN, "no_subtasks",
                                     "No subtasks available, need planning")
                self.global_state.set_task_objective(self.user_query)

        except Exception as e:
            logger.error(f"Error in INIT state: {e}")
            self.global_state.add_event("controller", "error",
                                        f"INIT state error: {str(e)}")
            self.switch_to_state(ControllerState.PLAN, "init_error",
                                 f"INIT state error: {str(e)}")

    def handle_get_action_state(self):
        """取下一步动作阶段"""
        logger.info("Handling GET_ACTION state")

        try:
            current_subtask_id = self.global_state.get_task().current_subtask_id
            if not current_subtask_id:
                logger.warning("No current subtask ID, switching to INIT")
                self.switch_to_state(ControllerState.INIT, "subtask_not_found", f"No current subtask ID in GET_ACTION state")
                return

            # 检查subtask状态
            subtask = self.global_state.get_subtask(current_subtask_id)
            if not subtask:
                logger.warning(f"Subtask {current_subtask_id} not found, switching to INIT")
                self.switch_to_state(ControllerState.INIT, "subtask_not_found", f"Subtask {current_subtask_id} not found in GET_ACTION state")
                return
            
            #worker生成command
            #这块也可以拿到worker的outcome给command的worker_decision
            # 方案一拿到outcome作为worker_decision
            # 方案二设置outcome作为command的worker_decision
            # 方案三worker内部处理worker_decision
            
            # 由Worker统一处理：根据角色生成action/记录decision/创建command
            self.worker.process_subtask_and_create_command()

            worker_decision = self.global_state.get_subtask_worker_decision(current_subtask_id)

            if worker_decision:
                logger.info(f"Subtask {current_subtask_id} has worker_decision: {worker_decision}")
                
                # 根据worker_decision切换状态
                if worker_decision == WorkerDecision.WORKER_DONE.value:
                    # 操作成功，进入质检阶段
                    logger.info(f"Worker decision is WORKER_DONE, switching to QUALITY_CHECK")
                    # 更新subtask状态为进行中
                    self.global_state.update_subtask_status(
                        current_subtask_id, SubtaskStatus.PENDING,
                        "Worker completed action, waiting for quality check")
                    self.switch_to_state(ControllerState.QUALITY_CHECK, "worker_success", f"Worker decision success for subtask {current_subtask_id}")
                    return
                elif worker_decision == WorkerDecision.CANNOT_EXECUTE.value:
                    # 无法执行，需要重规划
                    logger.info(f"Worker decision is CANNOT_EXECUTE, switching to PLAN")
                    # 更新subtask状态为失败
                    self.global_state.update_subtask_status(
                        current_subtask_id, SubtaskStatus.REJECTED,
                        "Worker cannot execute this subtask")
                    self.switch_to_state(ControllerState.PLAN, "worker_cannot_execute", f"Worker cannot execute subtask {current_subtask_id}")
                    return
                elif worker_decision == WorkerDecision.STALE_PROGRESS.value:
                    # 进展停滞，进入质检阶段
                    logger.info(f"Worker decision is STALE_PROGRESS, switching to QUALITY_CHECK")
                    self.switch_to_state(ControllerState.QUALITY_CHECK, "worker_stale_progress", f"Worker progress stale for subtask {current_subtask_id}")
                    return
                elif worker_decision == WorkerDecision.SUPPLEMENT.value:
                    # 需要补充资料
                    logger.info(f"Worker decision is SUPPLEMENT, switching to SUPPLEMENT")
                    self.switch_to_state(ControllerState.SUPPLEMENT, "worker_supplement", f"Worker needs supplement for subtask {current_subtask_id}")
                    return
                elif worker_decision == WorkerDecision.GENERATE_ACTION.value:
                    # 生成了新动作，执行动作
                    logger.info(f"Worker decision is GENERATE_ACTION, switching to EXECUTE_ACTION")
                    self.switch_to_state(ControllerState.EXECUTE_ACTION, "worker_generate_action", f"Worker generated action for subtask {current_subtask_id}")
                    return
            else:
                # 错误处理
                logger.info(f"Subtask {current_subtask_id} has no worker_decision, switching to PLAN")
                self.switch_to_state(ControllerState.PLAN, "no_worker_decision", f"Subtask {current_subtask_id} has no worker_decision in GET_ACTION state")
                return
            
            # 如果没有worker_decision或worker_decision不匹配已知类型，根据subtask状态决定下一步，暂时不开发
                
        except Exception as e:
            logger.error(f"Error in GET_ACTION state: {e}")
            self.global_state.add_event("controller", "error",
                                        f"GET_ACTION state error: {str(e)}")
            self.switch_to_state(ControllerState.PLAN)

    def handle_execute_action_state(self):
        """执行动作阶段"""
        logger.info("Handling EXECUTE_ACTION state")

        try:
            current_subtask_id = self.global_state.get_task().current_subtask_id
            if not current_subtask_id:
                logger.warning("No current subtask ID in EXECUTE_ACTION state")
                self.switch_to_state(ControllerState.INIT)
                return

            # 获取当前subtask
            subtask = self.global_state.get_subtask(current_subtask_id)
            if not subtask:
                logger.warning(
                    f"Subtask {current_subtask_id} not found in EXECUTE_ACTION state"
                )
                self.switch_to_state(ControllerState.INIT)
                return

            # 使用新的执行器执行动作
            execution_result = self.executor.execute_current_action(
                current_subtask_id)
            if execution_result["success"]:
                logger.info(
                    f"Action executed successfully for subtask {current_subtask_id} in {execution_result['execution_time']:.2f}s"
                )
                # 执行成功，等待状态更新或继续处理
            else:
                # 执行失败，标记subtask为失败并切换到重规划状态
                error_msg = execution_result.get("error_message",
                                                 "Unknown execution error")
                logger.warning(
                    f"Action execution failed for subtask {current_subtask_id}: {error_msg}"
                )

                self.global_state.update_subtask_status(
                    current_subtask_id, SubtaskStatus.REJECTED,
                    f"Action execution failed: {error_msg}")
                self.switch_to_state(ControllerState.PLAN, "execution_error",
                                     f"Action execution failed: {error_msg}")
                return

            # 等待1000秒
            time.sleep(1000)
            command = self.global_state.get_current_command_for_subtask(
                current_subtask_id)
            if command:
                screenshot: Image.Image = self.hwi.dispatch(
                    Screenshot())  # type: ignore
                self.global_state.set_screenshot(
                    scale_screenshot_dimensions(screenshot, self.hwi))
                self.switch_to_state(
                    ControllerState.GET_ACTION, "command_completed",
                    f" {command.command_id} command completed")

        except Exception as e:
            logger.error(f"Error in EXECUTE_ACTION state: {e}")
            self.global_state.add_event(
                "controller", "error", f"EXECUTE_ACTION state error: {str(e)}")
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
            self.evaluator.quality_check()

            # 检查质检结果
            gate_checks = self.global_state.get_gate_checks()
            latest_gate = None

            for gate in gate_checks:
                if gate.subtask_id == current_subtask_id:
                    if not latest_gate or gate.created_at > latest_gate.created_at:
                        latest_gate = gate

            if latest_gate:
                decision = latest_gate.decision
                logger.info(
                    f"Latest gate check decision for subtask {current_subtask_id}: {decision}"
                )

                if decision == GateDecision.GATE_DONE.value:
                    # 质检通过，subtask完成
                    self.global_state.update_subtask_status(
                        current_subtask_id, SubtaskStatus.FULFILLED,
                        "Quality check passed")
                    logger.info(
                        f"Quality check passed for subtask {current_subtask_id}"
                    )
                    
                    # 检查任务是否完成
                    task = self.global_state.get_task()
                    if not task.pending_subtask_ids:
                        # 所有subtask完成，更新任务状态为完成
                        # final_check先不开发
                        self.global_state.update_task_status(TaskStatus.FULFILLED)
                        logger.info("All subtasks completed, task finished")
                        self.switch_to_state(ControllerState.DONE, "task_completed", "All subtasks completed")
                        return
                    
                    # 还有待处理的subtask，推进到下一个
                    self.global_state.advance_to_next_subtask()
                    self.switch_to_state(
                        ControllerState.GET_ACTION, "quality_check_passed",
                        f"Quality check passed for subtask {current_subtask_id}"
                    )
                elif decision == GateDecision.GATE_FAIL.value:
                    # 质检失败，需要重规划
                    self.global_state.update_controller_state(
                        ControllerState.PLAN)
                    logger.info(
                        f"Quality check failed for subtask {current_subtask_id}"
                    )
                    self.switch_to_state(
                        ControllerState.PLAN, "quality_check_failed",
                        f"Quality check failed for subtask {current_subtask_id}"
                    )
                elif decision == GateDecision.GATE_SUPPLEMENT.value:
                    # 需要补充资料
                    self.global_state.update_controller_state(
                        ControllerState.SUPPLEMENT)
                    logger.info(
                        f"Quality check requires supplement for subtask {current_subtask_id}"
                    )
                    self.switch_to_state(
                        ControllerState.SUPPLEMENT, "quality_check_supplement",
                        f"Quality check requires supplement for subtask {current_subtask_id}"
                    )
                else:
                    # 继续质检
                    logger.debug(
                        f"Waiting for quality check completion for subtask {current_subtask_id}"
                    )
                    # 检查是否超时
                    if self._is_state_timeout():
                        logger.warning(
                            f"QUALITY_CHECK state timeout for subtask {current_subtask_id}"
                        )
                        self.global_state.update_controller_state(
                            ControllerState.PLAN)
                        self.switch_to_state(
                            ControllerState.PLAN, "timeout",
                            f"QUALITY_CHECK state timeout for subtask {current_subtask_id}"
                        )
            else:
                # 没有质检记录，继续等待
                logger.debug(
                    f"No gate checks found for subtask {current_subtask_id}")
                if self._is_state_timeout():
                    logger.warning(
                        f"QUALITY_CHECK state timeout (no gate checks) for subtask {current_subtask_id}"
                    )
                    self.global_state.update_controller_state(
                        ControllerState.PLAN)
                    self.switch_to_state(
                        ControllerState.PLAN, "timeout",
                        f"QUALITY_CHECK state timeout (no gate checks) for subtask {current_subtask_id}"
                    )

        except Exception as e:
            logger.error(f"Error in QUALITY_CHECK state: {e}")
            self.global_state.add_event("controller", "error",
                                        f"QUALITY_CHECK state error: {str(e)}")
            self.switch_to_state(ControllerState.PLAN)

    def handle_plan_state(self):
        """重规划阶段"""
        logger.info("Handling PLAN state")

        try:
            # 调用Manager进行重规划
            # 等待规划完成
            self.manager.plan_task("replan")
            # 检查新的subtask列表
            task = self.global_state.get_task()
            pending_subtask_ids = task.pending_subtask_ids or []

            if pending_subtask_ids:
                # 有subtask，设置第一个为当前subtask
                first_subtask_id = pending_subtask_ids[0]
                self.global_state.advance_to_next_subtask()
                self.global_state.update_task_status(TaskStatus.PENDING)
                self.global_state.update_controller_state(
                    ControllerState.GET_ACTION)
                logger.info(f"Set current subtask: {first_subtask_id}")
                self.switch_to_state(ControllerState.GET_ACTION,
                                     "subtask_ready",
                                     f"First subtask {first_subtask_id} ready")
            else:
                # 没有subtask，任务可能无法完成
                self.global_state.update_controller_state(ControllerState.PLAN)
                logger.warning(
                    "No subtasks available, continuing to wait for planning")
                # 继续等待或进入终结状态
                if self._is_state_timeout():
                    logger.error("PLAN state timeout, no subtasks created")
                    # 规划超时，更新任务状态为失败
                    self.global_state.update_task_status(TaskStatus.REJECTED)
                    self.switch_to_state(
                        ControllerState.DONE, "planning_timeout",
                        "PLAN state timeout, no subtasks created")

        except Exception as e:
            logger.error(f"Error in PLAN state: {e}")
            self.global_state.add_event("controller", "error",
                                        f"PLAN state error: {str(e)}")
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
            self.global_state.update_controller_state(
                ControllerState.GET_ACTION)
            logger.info("Supplement state completed, returning to GET_ACTION")
            self.switch_to_state(ControllerState.GET_ACTION,
                                 "supplement_completed",
                                 "Supplement collection completed")

        except Exception as e:
            logger.error(f"Error in SUPPLEMENT state: {e}")
            self.global_state.add_event("controller", "error",
                                        f"SUPPLEMENT state error: {str(e)}")
            self.switch_to_state(ControllerState.GET_ACTION)

    def switch_to_state(self,
                        new_state: ControllerState,
                        trigger: str = "controller",
                        trigger_details: str = ""):
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
            "controller", "state_switch",
            f"State changed: {old_state} -> {new_state} (trigger: {trigger}, details: {trigger_details})"
        )

        # 更新controller状态
        try:
            self.global_state.update_controller_state(new_state, trigger,
                                                      trigger_details)
        except Exception as e:
            logger.warning(f"Failed to update controller state: {e}")

        logger.info(
            f"State switched: {old_state} -> {new_state} (trigger: {trigger}, details: {trigger_details})"
        )

    def _is_state_timeout(self) -> bool:
        """检查当前状态是否超时"""
        return (time.time() - self.state_start_time) > self.max_state_duration

    def _check_current_state_rules(self) -> Optional[ControllerState]:
        """检查current_state相关规则"""
        try:
            task = self.global_state.get_task()
            if not task:
                return None
                
            # 距离上次质检过去了5步 - QUALITY_CHECK
            # 使用state_switch_count作为步数指标，但只在非质检状态下触发
            if (self.state_switch_count >= 5 and 
                self.current_state not in [ControllerState.QUALITY_CHECK, ControllerState.DONE]):
                logger.info(f"5 state switches since start, switching to QUALITY_CHECK")
                return ControllerState.QUALITY_CHECK
            
            # 相同连续动作高于3次 - QUALITY_CHECK
            # 检查当前subtask的command_trace数量
            if task.current_subtask_id:
                subtask = self.global_state.get_subtask(task.current_subtask_id)
                if subtask and len(subtask.command_trace_ids) >= 3:
                    logger.info(f"Subtask {task.current_subtask_id} has >= 3 commands, switching to QUALITY_CHECK")
                    return ControllerState.QUALITY_CHECK
            
            # 如果一个subtask的执行action过长，超过15次 - REPLAN
            if task.current_subtask_id:
                subtask = self.global_state.get_subtask(task.current_subtask_id)
                if subtask and len(subtask.command_trace_ids) > 15:
                    logger.info(f"Subtask {task.current_subtask_id} has > 15 commands, switching to PLAN")
                    return ControllerState.PLAN
                    
            return None
            
        except Exception as e:
            logger.error(f"Error checking current situation rules: {e}")
            return None

    def _check_task_state_rules(self) -> Optional[ControllerState]:
        """检查task_state相关规则，包括终止条件"""
        try:
            task = self.global_state.get_task()
            if not task:
                return
                
            # 检查状态切换次数上限
            if self.state_switch_count >= self.max_state_switches:
                logger.warning(f"Maximum state switches ({self.max_state_switches}) reached")
                self.global_state.update_task_status(TaskStatus.REJECTED)
            
            # 检查任务状态
            if task.status == "completed":
                logger.info("Task marked as completed")
                
            # manager规划次数大于10次 - rejected
            if self.state_switch_count > 10:
                logger.warning(f"State switch count > 10, marking task as REJECTED")
                self.global_state.update_task_status(TaskStatus.REJECTED)
            
            # manager重规划连续失败3次 - rejected
            # 检查是否有连续的状态切换到PLAN，但只在PLAN状态下检查
            if (self.current_state == ControllerState.PLAN and 
                self.state_switch_count >= 3):
                logger.warning(f"Multiple switches to PLAN state, marking task as REJECTED")
                self.global_state.update_task_status(TaskStatus.REJECTED)
            
            # current_step大于50步 - rejected/fulfilled
            if self.state_switch_count > 50:
                # 检查是否所有subtask都完成
                if not task.pending_subtask_ids or len(task.pending_subtask_ids) == 0:
                    logger.info(f"State switch count > 50 and all subtasks completed, marking task as FULFILLED")
                    self.global_state.update_task_status(TaskStatus.FULFILLED)
                else:
                    logger.warning(f"State switch count > 50 but subtasks not completed, marking task as REJECTED")
                    self.global_state.update_task_status(TaskStatus.REJECTED)
                    
            return
            
        except Exception as e:
            logger.error(f"Error checking task state rules: {e}")
            return

    def get_controller_info(self) -> Dict[str, Any]:
        """获取控制器信息"""
        return {
            "current_state": self.current_state.value,
            "state_start_time": self.state_start_time,
            "state_switch_count": self.state_switch_count,
            "controller_state": self.global_state.get_controller_state(),
            "task_id": self.global_state.task_id,
            "executor_status": self.executor.get_execution_status()
        }

    def reset_controller(self):
        """重置控制器状态"""
        logger.info("Resetting controller")
        self.current_state = ControllerState.INIT
        self.state_start_time = time.time()
        self.state_switch_count = 0
        self.global_state.reset_controller_state()
        logger.info("Controller reset completed")
