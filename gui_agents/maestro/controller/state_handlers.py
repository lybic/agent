"""
State Handlers for Agent-S Controller
负责处理各种状态的具体逻辑
"""

import logging
from typing import Optional

from gui_agents.maestro.new_global_state import NewGlobalState
from ..enums import ControllerState, TaskStatus, SubtaskStatus, WorkerDecision, GateDecision, TriggerRole, TriggerCode
from ..new_manager import NewManager
from ..new_worker import NewWorker
from ..evaluator import Evaluator
from ..new_executor import NewExecutor

logger = logging.getLogger(__name__)


class StateHandlers:
    """状态处理器，负责处理各种状态的具体逻辑"""
    
    def __init__(self, 
            global_state: NewGlobalState, 
            manager: NewManager, 
            executor: NewExecutor, 
            tools_dict: dict, 
            platform: str, 
            enable_search: bool, 
            env_password: str
        ):
        self.global_state: NewGlobalState = global_state
        self.manager = manager
        self.executor = executor
        self.tools_dict = tools_dict
        self.platform = platform
        self.enable_search = enable_search
        self.env_password = env_password
    
    def handle_init_state(self) -> tuple[ControllerState, TriggerRole, str, TriggerCode]:
        """立项状态处理"""
        logger.info("Handling INIT state")
        self.global_state.set_task_objective(self.global_state.get_task().objective)

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
                logger.info(f"Set current subtask: {first_subtask_id}")
                return (ControllerState.GET_ACTION, TriggerRole.CONTROLLER, f"First subtask {first_subtask_id} ready", TriggerCode.SUBTASK_READY)
            else:
                # 没有subtask，需要创建
                logger.info("No subtasks available, switching to PLAN state")
                return (ControllerState.PLAN, TriggerRole.CONTROLLER, "No subtasks available, need planning", TriggerCode.NO_SUBTASKS)

        except Exception as e:
            logger.error(f"Error in INIT state: {e}")
            self.global_state.add_event("controller", "error", f"INIT state error: {str(e)}")
            return (ControllerState.PLAN, TriggerRole.CONTROLLER, f"INIT state error: {str(e)}", TriggerCode.INIT_ERROR)
    
    def handle_get_action_state(self) -> tuple[ControllerState, TriggerRole, str, TriggerCode]:
        """取下一步动作阶段"""
        logger.info("Handling GET_ACTION state")
        current_subtask_id = self.global_state.get_task().current_subtask_id
        
        try:
            if not current_subtask_id:
                logger.warning("No current subtask ID, switching to INIT")
                return (ControllerState.INIT, TriggerRole.WORKER_GET_ACTION, "No current subtask ID in GET_ACTION state", TriggerCode.NO_CURRENT_SUBTASK_ID)

            # 检查subtask状态
            subtask = self.global_state.get_subtask(current_subtask_id)
            if not subtask:
                logger.warning(f"Subtask {current_subtask_id} not found, switching to INIT")
                return (ControllerState.INIT, TriggerRole.WORKER_GET_ACTION, f"Subtask {current_subtask_id} not found in GET_ACTION state", TriggerCode.SUBTASK_NOT_FOUND)

            # 由Worker统一处理：根据角色生成action/记录decision/创建command
            worker_params = {
                "tools_dict": self.tools_dict,
                "global_state": self.global_state,
                "platform": self.platform,
                "enable_search": self.enable_search,
                "client_password": self.env_password
            }
            worker = NewWorker(**worker_params)
            worker.process_subtask_and_create_command()

            worker_decision = self.global_state.get_subtask_worker_decision(current_subtask_id)

            if worker_decision:
                logger.info(f"Subtask {current_subtask_id} has worker_decision: {worker_decision}")

                # 根据worker_decision切换状态
                if worker_decision == WorkerDecision.WORKER_DONE.value:
                    # 操作成功，进入质检阶段
                    logger.info(f"Worker decision is WORKER_DONE, switching to QUALITY_CHECK")
                    self.global_state.update_subtask_status(
                        current_subtask_id, SubtaskStatus.PENDING,
                        "Worker completed action, waiting for quality check")
                    return (ControllerState.QUALITY_CHECK, TriggerRole.WORKER_GET_ACTION, f"Worker decision success for subtask {current_subtask_id}", TriggerCode.WORKER_SUCCESS)
                    
                elif worker_decision == WorkerDecision.CANNOT_EXECUTE.value:
                    # 无法执行，需要重规划
                    logger.info(f"Worker decision is CANNOT_EXECUTE, switching to PLAN")
                    self.global_state.update_subtask_status(
                        current_subtask_id, SubtaskStatus.REJECTED,
                        "Worker cannot execute this subtask")
                    return (ControllerState.PLAN, TriggerRole.WORKER_GET_ACTION, f"Worker cannot execute subtask {current_subtask_id}", TriggerCode.WORK_CANNOT_EXECUTE)
                    
                elif worker_decision == WorkerDecision.STALE_PROGRESS.value:
                    # 进展停滞，进入质检阶段
                    logger.info(f"Worker decision is STALE_PROGRESS, switching to QUALITY_CHECK")
                    self.global_state.update_subtask_status(
                        current_subtask_id, SubtaskStatus.STALE,
                        "Worker progress stale, waiting for quality check")
                    return (ControllerState.QUALITY_CHECK, TriggerRole.WORKER_GET_ACTION, f"Worker progress stale for subtask {current_subtask_id}", TriggerCode.WORKER_STALE_PROGRESS)
                    
                elif worker_decision == WorkerDecision.SUPPLEMENT.value:
                    # 需要补充资料
                    logger.info(f"Worker decision is SUPPLEMENT, switching to SUPPLEMENT")
                    self.global_state.update_subtask_status(
                        current_subtask_id, SubtaskStatus.REJECTED,
                        "Worker needs supplement, waiting for supplement")
                    return (ControllerState.SUPPLEMENT, TriggerRole.WORKER_GET_ACTION, f"Worker needs supplement for subtask {current_subtask_id}", TriggerCode.WORKER_SUPPLEMENT)
                    
                elif worker_decision == WorkerDecision.GENERATE_ACTION.value:
                    # 生成了新动作，执行动作
                    logger.info(f"Worker decision is GENERATE_ACTION, switching to EXECUTE_ACTION")
                    self.global_state.update_subtask_status(
                        current_subtask_id, SubtaskStatus.PENDING,
                        "Worker generated action, waiting for execute")
                    return (ControllerState.EXECUTE_ACTION, TriggerRole.WORKER_GET_ACTION, f"Worker generated action for subtask {current_subtask_id}", TriggerCode.WORKER_GENERATE_ACTION)
                else:
                    # 未知的worker_decision，默认切换到PLAN
                    logger.warning(f"Unknown worker_decision: {worker_decision}, switching to PLAN")
                    self.global_state.update_subtask_status(
                        current_subtask_id, SubtaskStatus.REJECTED,
                        f"Unknown worker_decision: {worker_decision}")
                    return (ControllerState.PLAN, TriggerRole.WORKER_GET_ACTION, f"Unknown worker_decision: {worker_decision}", TriggerCode.NO_WORKER_DECISION)
            else:
                # 错误处理
                logger.info(f"Subtask {current_subtask_id} has no worker_decision, switching to PLAN")
                self.global_state.update_subtask_status(
                    current_subtask_id, SubtaskStatus.REJECTED,
                    "Worker has no worker_decision, switching to PLAN")
                return (ControllerState.PLAN, TriggerRole.WORKER_GET_ACTION, f"Subtask {current_subtask_id} has no worker_decision in GET_ACTION state", TriggerCode.NO_WORKER_DECISION)

        except Exception as e:
            logger.error(f"Error in GET_ACTION state: {e}")
            self.global_state.log_operation(
                "controller", "error", {"error": f"GET_ACTION state error: {str(e)}"})

            # 更新subtask状态为失败
            if current_subtask_id is not None:
                self.global_state.update_subtask_status(
                    current_subtask_id, SubtaskStatus.REJECTED,
                    "Worker has no worker_decision, switching to PLAN")
            return (ControllerState.PLAN, TriggerRole.WORKER_GET_ACTION, f"GET_ACTION state error: {str(e)}", TriggerCode.GET_ACTION_ERROR)
    
    def handle_execute_action_state(self) -> tuple[ControllerState, TriggerRole, str, TriggerCode]:
        """执行动作阶段"""
        logger.info("Handling EXECUTE_ACTION state")

        try:
            current_subtask_id = self.global_state.get_task().current_subtask_id
            if not current_subtask_id:
                logger.warning("No current subtask ID in EXECUTE_ACTION state")
                return (ControllerState.INIT, TriggerRole.EXECUTOR_EXECUTE_ACTION, "No current subtask ID in EXECUTE_ACTION state", TriggerCode.NO_CURRENT_SUBTASK_ID)

            # 获取当前subtask
            subtask = self.global_state.get_subtask(current_subtask_id)
            if not subtask:
                logger.warning(f"Subtask {current_subtask_id} not found in EXECUTE_ACTION state")
                return (ControllerState.INIT, TriggerRole.EXECUTOR_EXECUTE_ACTION, f"Subtask {current_subtask_id} not found in EXECUTE_ACTION state", TriggerCode.SUBTASK_NOT_FOUND)

            # 使用新的执行器执行动作
            execution_result = self.executor.execute_current_action(current_subtask_id)
            if execution_result["success"]:
                logger.info(f"Action executed successfully for subtask {current_subtask_id} in {execution_result['execution_time']:.2f}s")
            else:
                # 执行失败，标记subtask为失败并切换到重规划状态
                error_msg = execution_result.get("error_message", "Unknown execution error")
                logger.warning(f"Action execution failed for subtask {current_subtask_id}: {error_msg}")

                self.global_state.update_subtask_status(
                    current_subtask_id, SubtaskStatus.PENDING,
                    f"Action execution failed: {error_msg}")
                return (ControllerState.GET_ACTION, TriggerRole.EXECUTOR_EXECUTE_ACTION, f"Action execution failed: {error_msg}", TriggerCode.EXECUTION_ERROR)

            # 获取截图Executor处理
            command = self.global_state.get_current_command_for_subtask(current_subtask_id)
            if command:
                return (ControllerState.GET_ACTION, TriggerRole.EXECUTOR_EXECUTE_ACTION, f"{command.command_id} command completed", TriggerCode.COMMAND_COMPLETED)
            else:
                return (ControllerState.GET_ACTION, TriggerRole.EXECUTOR_EXECUTE_ACTION, "No command found in EXECUTE_ACTION state", TriggerCode.NO_COMMAND)

        except Exception as e:
            logger.error(f"Error in EXECUTE_ACTION state: {e}")
            self.global_state.add_event("controller", "error", f"EXECUTE_ACTION state error: {str(e)}")
            return (ControllerState.GET_ACTION, TriggerRole.EXECUTOR_EXECUTE_ACTION, f"EXECUTE_ACTION state error: {str(e)}", TriggerCode.EXECUTION_ERROR)
    
    def handle_quality_check_state(self) -> tuple[ControllerState, TriggerRole, str, TriggerCode]:
        """质检门检查阶段"""
        logger.info("Handling QUALITY_CHECK state")
        current_subtask_id = self.global_state.get_task().current_subtask_id
        
        try:
            if not current_subtask_id:
                logger.warning("No current subtask ID in QUALITY_CHECK state")
                return (ControllerState.INIT, TriggerRole.EVALUATOR_QUALITY_CHECK, "No current subtask ID in QUALITY_CHECK state", TriggerCode.NO_CURRENT_SUBTASK_ID)

            evaluator_params = {
                "global_state": self.global_state,
                "tools_dict": self.tools_dict
            }
            evaluator = Evaluator(**evaluator_params)

            # 等待Evaluator完成质检
            evaluator.quality_check()

            # 检查质检结果
            latest_gate = self.global_state.get_latest_gate_check_for_subtask(current_subtask_id)

            if latest_gate:
                decision = latest_gate.decision
                logger.info(f"Latest gate check decision for subtask {current_subtask_id}: {decision}")

                if decision == GateDecision.GATE_DONE.value:
                    # 质检通过，subtask完成
                    self.global_state.update_subtask_status(
                        current_subtask_id, SubtaskStatus.FULFILLED,
                        "Quality check passed")
                    logger.info(f"Quality check passed for subtask {current_subtask_id}")

                    # 检查任务是否完成
                    task = self.global_state.get_task()
                    if not task.pending_subtask_ids:
                        # 所有subtask完成，进入最终质检阶段
                        logger.info("All subtasks completed, entering final check")
                        return (ControllerState.FINAL_CHECK, TriggerRole.EVALUATOR_QUALITY_CHECK, "All subtasks completed, entering final check", TriggerCode.ALL_SUBTASKS_COMPLETED)

                    # 还有待处理的subtask，推进到下一个
                    self.global_state.advance_to_next_subtask()
                    return (ControllerState.GET_ACTION, TriggerRole.EVALUATOR_QUALITY_CHECK, f"Quality check passed for subtask {current_subtask_id}", TriggerCode.QUALITY_CHECK_PASSED)
                    
                elif decision == GateDecision.GATE_FAIL.value:
                    logger.info(f"Quality check failed for subtask {current_subtask_id}")
                    # 更新子任务状态为失败
                    self.global_state.update_subtask_status(
                        current_subtask_id, SubtaskStatus.REJECTED,
                        "Quality check failed")
                    return (ControllerState.PLAN, TriggerRole.EVALUATOR_QUALITY_CHECK, f"Quality check failed for subtask {current_subtask_id}", TriggerCode.QUALITY_CHECK_FAILED)
                    
                elif decision == GateDecision.GATE_SUPPLEMENT.value:
                    # 需要补充资料
                    logger.info(f"Quality check requires supplement for subtask {current_subtask_id}")
                    self.global_state.update_subtask_status(
                        current_subtask_id, SubtaskStatus.REJECTED,
                        "Quality check requires supplement")
                    return (ControllerState.SUPPLEMENT, TriggerRole.EVALUATOR_QUALITY_CHECK, f"Quality check requires supplement for subtask {current_subtask_id}", TriggerCode.QUALITY_CHECK_SUPPLEMENT)
                    
                elif decision == GateDecision.GATE_CONTINUE.value:
                    # execute_action
                    logger.info(f"Quality check requires execute action for subtask {current_subtask_id}")
                    self.global_state.update_subtask_status(
                        current_subtask_id, SubtaskStatus.PENDING,
                        "Quality check requires execute action")
                    return (ControllerState.EXECUTE_ACTION, TriggerRole.EVALUATOR_QUALITY_CHECK, f"Quality check requires execute action for subtask {current_subtask_id}", TriggerCode.QUALITY_CHECK_EXECUTE_ACTION)
                else:
                    # 未知的gate decision，默认切换到PLAN
                    logger.warning(f"Unknown gate decision: {decision}, switching to PLAN")
                    self.global_state.update_subtask_status(
                        current_subtask_id, SubtaskStatus.REJECTED,
                        f"Unknown gate decision: {decision}")
                    return (ControllerState.PLAN, TriggerRole.EVALUATOR_QUALITY_CHECK, f"Unknown gate decision: {decision}", TriggerCode.QUALITY_CHECK_ERROR)
            else:
                # 没有质检记录，错误
                logger.debug(f"No gate checks found for subtask {current_subtask_id}")
                return (ControllerState.PLAN, TriggerRole.EVALUATOR_QUALITY_CHECK, "Quality check error", TriggerCode.QUALITY_CHECK_ERROR)

        except Exception as e:
            logger.error(f"Error in QUALITY_CHECK state: {e}")
            self.global_state.add_event("controller", "error", f"QUALITY_CHECK state error: {str(e)}")
            if current_subtask_id is not None:
                self.global_state.update_subtask_status(
                    current_subtask_id, SubtaskStatus.REJECTED,
                    "Quality check error")
            return (ControllerState.PLAN, TriggerRole.EVALUATOR_QUALITY_CHECK, f"QUALITY_CHECK state error: {str(e)}", TriggerCode.QUALITY_CHECK_ERROR)
    
    def handle_plan_state(self) -> tuple[ControllerState, TriggerRole, str, TriggerCode]:
        """重规划阶段"""
        logger.info("Handling PLAN state")

        try:
            # 增加规划次数计数
            self.global_state.increment_plan_num()
            logger.info(f"Plan number incremented to: {self.global_state.get_plan_num()}")
            
            # 调用Manager进行重规划
            self.manager.plan_task("replan")
            
            # 检查新的subtask列表
            task = self.global_state.get_task()
            pending_subtask_ids = task.pending_subtask_ids or []

            if pending_subtask_ids:
                # 有subtask，设置第一个为当前subtask
                first_subtask_id = pending_subtask_ids[0]
                self.global_state.advance_to_next_subtask()
                self.global_state.update_task_status(TaskStatus.PENDING)
                logger.info(f"Set current subtask: {first_subtask_id}")
                return (ControllerState.GET_ACTION, TriggerRole.MANAGER_REPLAN, f"First subtask {first_subtask_id} ready", TriggerCode.SUBTASK_READY_AFTER_PLAN)
            else:
                # 没有subtask，任务可能无法完成
                logger.warning("No subtasks available, continuing to wait for planning")
                return (ControllerState.INIT, TriggerRole.MANAGER_REPLAN, "Plan error, no subtasks available", TriggerCode.PLAN_ERROR)

        except Exception as e:
            logger.error(f"Error in PLAN state: {e}")
            self.global_state.add_event("controller", "error", f"PLAN state error: {str(e)}")
            return (ControllerState.INIT, TriggerRole.MANAGER_REPLAN, f"PLAN state error: {str(e)}", TriggerCode.PLAN_ERROR)
    
    def handle_supplement_state(self) -> tuple[ControllerState, TriggerRole, str, TriggerCode]:
        """资料补全阶段"""
        logger.info("Handling SUPPLEMENT state")

        try:
            # 增加规划次数计数（补充资料也是一种规划行为）
            self.global_state.increment_plan_num()
            logger.info(f"Plan number incremented to: {self.global_state.get_plan_num()} (supplement)")
            
            # 等待Manager补充资料
            self.manager.plan_task("supplement")

            # 如果资料补充完成，回到PLAN
            logger.info("Supplement state completed, returning to PLAN")
            return (ControllerState.PLAN, TriggerRole.MANAGER_SUPPLEMENT, "Supplement collection completed", TriggerCode.SUPPLEMENT_COMPLETED)

        except Exception as e:
            logger.error(f"Error in SUPPLEMENT state: {e}")
            self.global_state.add_event("controller", "error", f"SUPPLEMENT state error: {str(e)}")
            # 此处没有定义current_subtask_id，修正为获取当前subtask_id
            current_subtask_id = self.global_state.get_task().current_subtask_id
            if current_subtask_id is not None:
                self.global_state.update_subtask_status(
                    current_subtask_id, SubtaskStatus.REJECTED,
                    "Supplement collection failed")
            return (ControllerState.PLAN, TriggerRole.MANAGER_SUPPLEMENT, f"SUPPLEMENT state error: {str(e)}", TriggerCode.SUPPLEMENT_ERROR)
    
    def handle_final_check_state(self) -> tuple[ControllerState, TriggerRole, str, TriggerCode]:
        """最终质检阶段"""
        logger.info("Handling FINAL_CHECK state")

        try:
            # 进行最终质检
            task = self.global_state.get_task()
            if not task:
                logger.error("No task found for final check")
                return (ControllerState.DONE, TriggerRole.EVALUATOR_FINAL_CHECK, "No task found", TriggerCode.FINAL_CHECK_ERROR)

            # 检查是否还有待处理的subtask
            if task.pending_subtask_ids and len(task.pending_subtask_ids) > 0:
                logger.info("Still have pending subtasks, switching to GET_ACTION")
                return (ControllerState.GET_ACTION, TriggerRole.EVALUATOR_FINAL_CHECK, "Still have pending subtasks", TriggerCode.FINAL_CHECK_PENDING)

            # 所有subtask都完成了，进行最终质检
            logger.info("All subtasks completed, performing final quality check")
            
            # 这里可以调用evaluator进行最终质检
            evaluator_params = {
                "global_state": self.global_state,
                "tools_dict": self.tools_dict
            }
            evaluator = Evaluator(**evaluator_params)

            # 等待Evaluator完成质检
            evaluator.quality_check()

            # 检查质检结果
            gate_checks = self.global_state.get_gate_checks()
            latest_gate = None

            for gate in gate_checks:
                if not latest_gate or gate.created_at > latest_gate.created_at:
                    latest_gate = gate

            if latest_gate:
                decision = latest_gate.decision
                logger.info(f"Latest gate check decision for final check: {decision}")
                if decision == GateDecision.GATE_DONE.value:
                    # 如果质检通过，标记任务为完成
                    self.global_state.update_task_status(TaskStatus.FULFILLED)
                    logger.info("Final quality check passed, task fulfilled")
                    # 切换到DONE状态
                    return (ControllerState.DONE, TriggerRole.EVALUATOR_FINAL_CHECK, "Final quality check passed", TriggerCode.FINAL_CHECK_PASSED)
                elif decision == GateDecision.GATE_FAIL.value:
                    # 最终质检失败
                    logger.info("Final quality check failed, task rejected")
                    # 切换到PLAN状态
                    return (ControllerState.PLAN, TriggerRole.EVALUATOR_FINAL_CHECK, "Final quality check failed", TriggerCode.FINAL_CHECK_FAILED)
                    
            # 其他状态，继续等待
            logger.info(f"Final quality check failed.")
            return (ControllerState.PLAN, TriggerRole.EVALUATOR_FINAL_CHECK, "Final quality check failed", TriggerCode.FINAL_CHECK_FAILED)
            
        except Exception as e:
            logger.error(f"Error in FINAL_CHECK state: {e}")
            self.global_state.add_event("controller", "error", f"FINAL_CHECK state error: {str(e)}")
            # 最终质检失败
            return (ControllerState.PLAN, TriggerRole.EVALUATOR_FINAL_CHECK, f"Final check failed: {str(e)}", TriggerCode.FINAL_CHECK_FAILED) 