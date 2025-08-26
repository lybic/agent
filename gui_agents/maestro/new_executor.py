"""
New Executor Implementation
专门负责从global state中获取和执行动作的执行器模块
"""

import time
import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from gui_agents.maestro.data_models import CommandData
from gui_agents.maestro.hardware_interface import HardwareInterface
from .new_global_state import NewGlobalState
from .enums import ExecStatus, SubtaskStatus
from desktop_env.desktop_env import DesktopEnv
from PIL import Image
from gui_agents.maestro.Action import Screenshot
from gui_agents.maestro.utils.screenShot import scale_screenshot_dimensions

# 设置日志
logger = logging.getLogger(__name__)


class NewExecutor:
    """动作执行器 - 负责获取和执行动作"""
    
    def __init__(self, global_state: NewGlobalState, hardware_interface: HardwareInterface, env_controller: Optional[DesktopEnv] = None):
        """
        初始化执行器
        
        Args:
            global_state: 全局状态管理器
            hardware_interface: 硬件接口
            env_controller: 环境控制器，用于执行代码脚本
        """
        self.global_state = global_state
        self.hwi = hardware_interface
        self.env_controller = env_controller.controller if env_controller is not None else None
        self.execution_timeout = 30  # 单次执行超时时间(秒)
        
        logger.info("NewExecutor initialized")

    # ========== 纯执行（不更新 global_state） ==========
    def _run_code_blocks(self, code_blocks: List[Tuple[str, str]]) -> Tuple[bool, str, Optional[str]]:
        """仅执行代码块，返回 (success, combined_output, last_status)。不做任何 global_state 更新。"""
        if not self.env_controller:
            return False, "No environment controller available for code execution", None
        results = []
        last_status: Optional[str] = None
        for lang, code in code_blocks:
            try:
                if lang in ["bash", "shell", "sh"]:
                    output_dict = self.env_controller.run_bash_script(code)
                    status = (output_dict or {}).get("status")
                    last_status = status
                    if status == "success":
                        results.append(f"[BASH] Success: {(output_dict or {}).get('output', '')}")
                    else:
                        out = (output_dict or {}).get('output', '')
                        err = (output_dict or {}).get('error', '')
                        msg = out if out else err
                        results.append(f"[BASH] Error: {msg}")
                elif lang in ["python", "py"]:
                    output_dict = self.env_controller.run_python_script(code)
                    status = (output_dict or {}).get("status")
                    last_status = status
                    if status == "error":
                        out = (output_dict or {}).get('output', '')
                        err = (output_dict or {}).get('error', '')
                        msg = out if out else err
                        results.append(f"[PYTHON] Error: {msg}")
                    else:
                        results.append(f"[PYTHON] Success: {(output_dict or {}).get('message', '')}")
                else:
                    results.append(f"[{lang.upper()}] Unsupported language")
            except Exception as e:
                last_status = "error"
                results.append(f"[{lang.upper()}] Execution error: {str(e)}")
        success = last_status == "success"
        return success, "\n".join(results), last_status

    # ========== 执行硬件动作 ==========
    def _run_hardware_action(self, action: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Image.Image]]:
        """仅与硬件交互执行动作，返回 (success, error_message, screenshot)。不做任何 global_state 更新。"""
        try:
            self.hwi.dispatchDict(action)
            time.sleep(3)
            screenshot: Image.Image = self.hwi.dispatch(Screenshot())  # type: ignore
            return True, None, screenshot
        except Exception as e:
            return False, str(e), None
    
    # ========== 执行命令 ==========
    def execute_command(self, command: CommandData) -> Dict[str, Any]:
        """
        执行传入的 command（只执行，不触碰 global_state）：
        - 根据 subtask 的 assignee_role 选择执行路径
        - operator -> 仅硬件执行
        - technician -> 仅代码执行
        - analyst -> 不落库artifact，仅返回意图信息
        - 不写入 artifact、不更新 exec_status、不更新 screenshot、不递增 step
        """
        try:
            subtask_id: Optional[str] = getattr(command, "subtask_id", None)
            if not subtask_id:
                return self._create_execution_result(False, "command.subtask_id 为空")
            subtask = self.global_state.get_subtask(subtask_id)
            if not subtask:
                return self._create_execution_result(False, "Subtask not found")

            assignee_role = getattr(subtask, "assignee_role", "operator")
            start_ts = time.time()

            if assignee_role == "operator":
                ok, err, _shot = self._run_hardware_action(command.action)
                return self._create_execution_result(
                    success=ok,
                    error_message=err,
                    execution_time=time.time() - start_ts,
                    action=command.action,
                )

            if assignee_role == "technician":
                # 代码块 or 字符串中提取代码块
                if isinstance(command.action, list) and command.action:
                    code_blocks: List[Tuple[str, str]] = []
                    for item in command.action:
                        if isinstance(item, list) and len(item) == 2:
                            lang, code = item
                            if isinstance(lang, str) and isinstance(code, str):
                                code_blocks.append((lang, code))
                    if not code_blocks:
                        return self._create_execution_result(False, "Invalid code blocks format in command.action")
                    success, combined_output, _ = self._run_code_blocks(code_blocks)
                    return self._create_execution_result(
                        success=success,
                        execution_time=time.time() - start_ts,
                        action={"type": "code_blocks_execution", "result": combined_output}
                    )
                elif isinstance(command.action, str):
                    code_blocks = self._extract_code_blocks(command.action)
                    if not code_blocks:
                        return self._create_execution_result(False, "No code blocks found in string action")
                    success, combined_output, _ = self._run_code_blocks(code_blocks)
                    return self._create_execution_result(
                        success=success,
                        execution_time=time.time() - start_ts,
                        action={"type": "code_blocks_execution", "result": combined_output}
                    )
                else:
                    return self._create_execution_result(False, "Action is not in expected format for technician role")

            if assignee_role == "analyst":
                # 不写入artifact，仅返回意图信息
                return self._create_execution_result(
                    success=True,
                    execution_time=time.time() - start_ts,
                    action={"type": "analysis_intent", "payload": command.action}
                )

            # 兜底：未知角色按硬件执行
            ok, err, _shot = self._run_hardware_action(command.action)
            return self._create_execution_result(
                success=ok,
                error_message=err,
                execution_time=time.time() - start_ts,
                action=command.action,
            )
        except Exception as e:
            return self._create_execution_result(False, f"execute_command failed: {e}")
    
    # ========== 执行当前动作 ==========
    def execute_current_action(self) -> Dict[str, Any]:
        """
        执行指定subtask的动作（使用该 subtask 的“当前最新 command”）。
        保留以兼容旧用法；若需执行指定 command，请使用 execute_command。
        """
        try:
            subtask_id = self.global_state.get_task().current_subtask_id
            logger.info(f"Starting action execution for subtask: {subtask_id}")
            
            # 获取相关的command（当前最新）
            if not subtask_id:
                error_msg = f"No subtask_id found"
                logger.warning(error_msg)
                return self._create_execution_result(False, error_msg)
            command = self.global_state.get_current_command_for_subtask(subtask_id)
            if not command:
                error_msg = f"No command found for subtask {subtask_id}"
                logger.warning(error_msg)
                return self._create_execution_result(False, error_msg)
            
            # 检查是否有action需要执行
            if not command.action:
                error_msg = f"No action defined in command for subtask {subtask_id}"
                logger.warning(error_msg)
                return self._create_execution_result(False, error_msg)
            
            # 获取当前subtask的assignee_role
            subtask = self.global_state.get_subtask(subtask_id)
            if not subtask:
                return self._create_execution_result(False, "Subtask not found")
            
            assignee_role = getattr(subtask, "assignee_role", "operator")
            
            # 根据assignee_role选择不同的执行方式
            if assignee_role == "operator":
                return self._execute_action(subtask_id, command.action)
                
            elif assignee_role == "technician":
                if isinstance(command.action, list) and command.action:
                    code_blocks = []
                    for item in command.action:
                        if isinstance(item, list) and len(item) == 2:
                            lang, code = item
                            if isinstance(lang, str) and isinstance(code, str):
                                code_blocks.append((lang, code))
                    if code_blocks:
                        return self._execute_code_blocks(code_blocks, subtask_id)
                    else:
                        return self._create_execution_result(False, "Invalid code blocks format in action")
                elif isinstance(command.action, str):
                    code_blocks = self._extract_code_blocks(command.action)
                    if code_blocks:
                        return self._execute_code_blocks(code_blocks, subtask_id)
                    else:
                        return self._create_execution_result(False, "No code blocks found in string action")
                else:
                    return self._create_execution_result(False, "Action is not in expected format for technician role")
                    
            elif assignee_role == "analyst":
                try:
                    if isinstance(command.action, dict) and "analysis" in command.action:
                        analysis_result = command.action.get("analysis", "")
                        recommendations = command.action.get("recommendations", [])
                        artifact_data = {
                            "subtask_id": subtask_id,
                            "type": "analysis_result",
                            "analysis": analysis_result,
                            "recommendations": recommendations,
                            "timestamp": time.time(),
                            "source": "analyst_memorize_analysis"
                        }
                        self.global_state.add_artifact("analysis_result", artifact_data)
                        return self._create_execution_result(True, action={"type": "analysis_artifact_stored", "artifact": artifact_data})
                    else:
                        artifact_data = {
                            "subtask_id": subtask_id,
                            "action": command.action,
                            "timestamp": time.time(),
                            "type": "action_artifact"
                        }
                        self.global_state.add_artifact("action_artifact", artifact_data)
                        return self._create_execution_result(True, action={"type": "artifact_stored", "artifact": artifact_data})
                except Exception as e:
                    error_msg = f"Failed to store artifact: {str(e)}"
                    logger.error(error_msg)
                    return self._create_execution_result(False, error_msg)
                    
            else:
                logger.warning(f"Unknown assignee_role '{assignee_role}', falling back to hardware execution")
                return self._execute_action(subtask_id, command.action)
            
        except Exception as e:
            error_msg = f"Exception in execute_current_action: {str(e)}"
            logger.error(error_msg)
            return self._create_execution_result(False, error_msg)


    # ========== 执行代码块 ==========
    def _execute_code_blocks(self, code_blocks: List[Tuple[str, str]], subtask_id: str, command_id: Optional[str] = None) -> Dict[str, Any]:
        """
        执行代码块列表
        
        Args:
            code_blocks: 代码块列表，每个元素为 (语言, 代码) 的元组
            subtask_id: 子任务ID，用于更新命令的 post_screenshot_id
            command_id: 若提供，则精准更新该 command 的执行状态；否则回退至当前最新 command
        """
        if not self.env_controller:
            error_msg = "No environment controller available for code execution"
            logger.warning(error_msg)
            return self._create_execution_result(False, error_msg)
        
        execution_start = time.time()
        
        try:
            # 纯执行
            success, combined_output, last_status = self._run_code_blocks(code_blocks)

            execution_time = time.time() - execution_start
            
            # 记录执行结果（状态更新）
            self.global_state.add_event("executor", "code_blocks_execution_completed", 
                f"Code blocks execution completed in {execution_time:.2f}s")
            exec_status = ExecStatus.EXECUTED if success else ExecStatus.ERROR
            # 精确或回退更新执行状态
            target_command_id = command_id
            if not target_command_id:
                current_cmd = self.global_state.get_current_command_for_subtask(subtask_id)
                target_command_id = getattr(current_cmd, "command_id", None) if current_cmd else None
            if target_command_id:
                self.global_state.update_command_exec_status(
                    target_command_id, # type: ignore
                    exec_status,
                    combined_output,
                )
            
            # 硬件截图（与执行逻辑分离）
            ok, err, screenshot = self._run_hardware_action({"type": "Screenshot"})
            if ok and screenshot is not None:
                self.global_state.set_screenshot(
                    scale_screenshot_dimensions(screenshot, self.hwi))
            
            # 获取新截图的ID并更新命令的 post_screenshot_id
            new_screenshot_id = self.global_state.get_screenshot_id()
            if new_screenshot_id:
                if not target_command_id:
                    current_cmd = self.global_state.get_current_command_for_subtask(subtask_id)
                    target_command_id = getattr(current_cmd, "command_id", None) if current_cmd else None
                if target_command_id:
                    self.global_state.update_command_post_screenshot(
                        target_command_id, new_screenshot_id) # type: ignore
                    logger.info(f"Updated post_screenshot_id for command {target_command_id}: {new_screenshot_id}")
            
            self.global_state.increment_step_num()
            
            return self._create_execution_result(
                success=success,
                execution_time=execution_time,
                action={"type": "code_blocks_execution", "result": combined_output}
            )
            
        except Exception as e:
            execution_time = time.time() - execution_start
            error_msg = f"Code blocks execution failed: {str(e)}"
            logger.error(error_msg)
            return self._create_execution_result(False, error_msg, execution_time)
    
    # ========== 提取代码块 ==========
    def _extract_code_blocks(self, text: str) -> List[Tuple[str, str]]:
        """从markdown样式的文本中提取代码块"""
        # 匹配 ```language\ncode\n``` 的模式
        pattern = r'```(\w+)\n(.*?)\n```'
        matches = re.findall(pattern, text, re.DOTALL)
        
        code_blocks = []
        for lang, code in matches:
            lang = lang.lower()
            code = code.strip()
            if code:
                code_blocks.append((lang, code))
        
        return code_blocks

    # ========== 执行动作 ==========
    def _execute_action(self, subtask_id: str, action: Dict[str, Any], command_id: Optional[str] = None) -> Dict[str, Any]:
        """
        执行具体的动作
        
        Args:
            subtask_id: subtask ID
            action: 要执行的动作字典
            command_id: 若提供，则精准更新该 command 的截图与执行状态
        """
        execution_start = time.time()
        
        try:
            logger.info(f"Executing action for subtask {subtask_id}: {action}")
            
            # memorize 动作特殊处理（写入 artifact），执行逻辑与状态更新适度分离
            if isinstance(action, dict) and action.get("type") == "Memorize":
                information = action.get("information", "")
                if information:
                    # 业务写入
                    self.global_state.add_memorize_artifact(subtask_id, information)
                    logger.info(f"Memorize action processed for subtask {subtask_id}: {information[:100]}...")
                    
                    execution_success = True
                    error_message = None
                    execution_time = time.time() - execution_start
                    
                    # 状态更新
                    self._record_execution_result(subtask_id, execution_success, error_message, execution_time)
                    target_command_id = command_id
                    if not target_command_id:
                        current_command = self.global_state.get_current_command_for_subtask(subtask_id)
                        target_command_id = getattr(current_command, "command_id", None) if current_command else None
                    if target_command_id:
                        msg_preview = information.replace("\n", " ").strip()[:200]
                        exec_msg = f"Memorize stored ({len(information)} chars): {msg_preview}{'...' if len(information) > 200 else ''}"
                        self.global_state.update_command_exec_status(
                            target_command_id, # type: ignore
                            ExecStatus.EXECUTED,
                            exec_message=exec_msg,
                        )
                    
                    return self._create_execution_result(
                        success=execution_success,
                        error_message=error_message,
                        execution_time=execution_time,
                        action=action
                    )
            
            # 纯执行（硬件交互）
            ok, err, screenshot = self._run_hardware_action(action)
            execution_success = ok
            error_message = err
            
            # 截图写入
            if ok and screenshot is not None:
                self.global_state.set_screenshot(
                    scale_screenshot_dimensions(screenshot, self.hwi))
            
            # 获取新截图的ID并更新命令的 post_screenshot_id
            new_screenshot_id = self.global_state.get_screenshot_id()
            if new_screenshot_id:
                target_command_id = command_id
                if not target_command_id:
                    current_command = self.global_state.get_current_command_for_subtask(subtask_id)
                    target_command_id = getattr(current_command, "command_id", None) if current_command else None
                if target_command_id:
                    self.global_state.update_command_post_screenshot(
                        target_command_id, new_screenshot_id) # type: ignore
                    logger.info(f"Updated post_screenshot_id for command {target_command_id}: {new_screenshot_id}")
            
            # 记录与状态更新
            execution_time = time.time() - execution_start
            self._record_execution_result(subtask_id, execution_success, error_message, execution_time)

            # 可选：根据执行结果写入该 command 的状态
            target_command_id = command_id
            if not target_command_id:
                current_command = self.global_state.get_current_command_for_subtask(subtask_id)
                target_command_id = getattr(current_command, "command_id", None) if current_command else None
            if target_command_id:
                self.global_state.update_command_exec_status(
                    target_command_id, # type: ignore
                    ExecStatus.EXECUTED if execution_success else ExecStatus.ERROR,
                    exec_message=("Action executed" if execution_success else f"Action failed: {error_message}")
                )
            
            # 返回结果
            result = self._create_execution_result(
                success=execution_success,
                error_message=error_message,
                execution_time=execution_time,
                action=action
            )
            
            logger.info(f"Action execution completed for subtask {subtask_id} in {execution_time:.2f}s")
            return result
            
        except Exception as e:
            execution_time = time.time() - execution_start
            error_msg = f"Exception during action execution: {str(e)}"
            logger.error(error_msg)
            
            # 记录执行异常
            self._record_execution_result(subtask_id, False, error_msg, execution_time)
            
            return self._create_execution_result(False, error_msg, execution_time)
    
    # ========== 记录执行结果 ==========
    def _record_execution_result(self, subtask_id: str, success: bool, error_message: Optional[str], execution_time: float):
        """记录执行结果到global state"""
        try:
            if success:
                # 记录成功执行事件
                self.global_state.log_operation("executor", "action_success", {
                    "subtask_id": subtask_id,
                    "execution_time": execution_time
                })
                
                # 可以选择更新subtask状态为已执行，但状态管理应该由Controller决定
                # self.global_state.update_subtask_status(subtask_id, SubtaskStatus.FULFILLED, "Action executed successfully")
                
            else:
                # 记录执行失败事件
                self.global_state.log_operation("executor", "action_error", {
                    "subtask_id": subtask_id,
                    "error_message": error_message,
                    "execution_time": execution_time
                })
                
                # 可以选择更新subtask状态为失败，但状态管理应该由Controller决定
                # self.global_state.update_subtask_status(subtask_id, SubtaskStatus.REJECTED, f"Action execution failed: {error_message}")
                
        except Exception as e:
            logger.warning(f"Failed to record execution result: {e}")
    
    # 创建标准化的执行结果
    def _create_execution_result(self, success: bool, error_message: Optional[str] = None, execution_time: float = 0.0, action: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """创建标准化的执行结果"""
        result = {
            "success": success,
            "execution_time": execution_time,
            "timestamp": time.time()
        }
        
        if error_message:
            result["error_message"] = error_message
        
        if action:
            result["action"] = action
            
        return result
        
        
    def get_execution_status(self) -> Dict[str, Any]:
        """获取执行器状态信息"""
        return {
            "executor_type": "NewExecutor",
            "hardware_backend": getattr(self.hwi, 'backend', 'unknown'),
            "execution_timeout": self.execution_timeout
        } 