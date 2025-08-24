"""
New Executor Implementation
专门负责从global state中获取和执行动作的执行器模块
"""

import time
import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from gui_agents.maestro.hardware_interface import HardwareInterface
from .new_global_state import NewGlobalState
from .enums import SubtaskStatus
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
    
    def execute_current_action(self, subtask_id: str) -> Dict[str, Any]:
        """
        执行指定subtask的动作，根据assignee_role选择不同的执行方式
        
        Args:
            subtask_id: 要执行的subtask ID
            
        Returns:
            执行结果字典，包含success, error_message, execution_time等
        """
        try:
            logger.info(f"Starting action execution for subtask: {subtask_id}")
            
            # 获取相关的command
            command = self._get_command_for_subtask(subtask_id)
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
            
            assignee_role = getattr(subtask, "assignee_role", "operator")  # 默认为operator
            
            # 根据assignee_role选择不同的执行方式
            if assignee_role == "operator":
                # operator执行硬件动作
                logger.info(f"Operator role detected, executing hardware action for subtask {subtask_id}")
                return self._execute_action(subtask_id, command.action)
                
            elif assignee_role == "technician":
                # technician执行代码块
                logger.info(f"Technician role detected, executing code blocks for subtask {subtask_id}")
                
                # Technician的action是List[Tuple[str, str]]格式的代码块列表
                if isinstance(command.action, list) and command.action:
                    # 验证代码块格式
                    code_blocks = []
                    for item in command.action:
                        if isinstance(item, tuple) and len(item) == 2:
                            lang, code = item
                            if isinstance(lang, str) and isinstance(code, str):
                                code_blocks.append((lang, code))
                    
                    if code_blocks:
                        # 执行代码块
                        logger.info(f"Executing {len(code_blocks)} code blocks for technician role")
                        execution_result = self.execute_code_blocks(code_blocks)
                        
                        if execution_result["success"]:
                            # 执行成功，返回执行结果
                            return execution_result
                        else:
                            # 执行失败，返回错误信息
                            return execution_result
                    else:
                        return self._create_execution_result(False, "Invalid code blocks format in action")
                elif isinstance(command.action, str):
                    # 如果是字符串，尝试提取代码块（兼容性处理）
                    code_blocks = self._extract_code_blocks(command.action)
                    if code_blocks:
                        logger.info(f"Extracted and executing {len(code_blocks)} code blocks from string action")
                        execution_result = self.execute_code_blocks(code_blocks)
                        return execution_result
                    else:
                        return self._create_execution_result(False, "No code blocks found in string action")
                else:
                    return self._create_execution_result(False, "Action is not in expected format for technician role")
                    
            elif assignee_role == "analyst":
                # analyst写入到globalstate的artifacts
                logger.info(f"Analyst role detected, storing artifact for subtask {subtask_id}")
                try:
                    # 检查action中是否包含memorize分析结果
                    if isinstance(command.action, dict) and "analysis" in command.action:
                        analysis_result = command.action.get("analysis", "")
                        recommendations = command.action.get("recommendations", [])
                        extracted_data = command.action.get("extracted_data", {})
                        
                        # 创建结构化的artifact数据
                        artifact_data = {
                            "subtask_id": subtask_id,
                            "type": "analysis_result",
                            "analysis": analysis_result,
                            "recommendations": recommendations,
                            "extracted_data": extracted_data,
                            "timestamp": time.time(),
                            "source": "analyst_memorize_analysis"
                        }
                        
                        # 添加到artifacts
                        self.global_state.add_artifact(subtask_id, artifact_data)
                        
                        return self._create_execution_result(
                            success=True,
                            action={"type": "analysis_artifact_stored", "artifact": artifact_data}
                        )
                    else:
                        # 普通artifact存储
                        artifact_data = {
                            "subtask_id": subtask_id,
                            "action": command.action,
                            "timestamp": time.time(),
                            "type": "action_artifact"
                        }
                        
                        # 添加到artifacts
                        self.global_state.add_artifact(subtask_id, artifact_data)
                        
                        return self._create_execution_result(
                            success=True,
                            action={"type": "artifact_stored", "artifact": artifact_data}
                        )
                    
                except Exception as e:
                    error_msg = f"Failed to store artifact: {str(e)}"
                    logger.error(error_msg)
                    return self._create_execution_result(False, error_msg)
                    
            else:
                # 未知角色，默认执行硬件动作
                logger.warning(f"Unknown assignee_role '{assignee_role}', falling back to hardware execution")
                return self._execute_action(subtask_id, command.action)
            
        except Exception as e:
            error_msg = f"Exception in execute_current_action: {str(e)}"
            logger.error(error_msg)
            return self._create_execution_result(False, error_msg)

    def execute_code_script(self, script_content: str, script_type: str = "auto") -> Dict[str, Any]:
        """
        执行代码脚本（bash或python）
        
        Args:
            script_content: 脚本内容
            script_type: 脚本类型 ("bash", "python", "auto")
            
        Returns:
            执行结果字典
        """
        if not self.env_controller:
            error_msg = "No environment controller available for code execution"
            logger.warning(error_msg)
            return self._create_execution_result(False, error_msg)
        
        execution_start = time.time()
        
        try:
            # 自动检测脚本类型
            if script_type == "auto":
                script_type = self._detect_script_type(script_content)
            
            # 提取代码块
            code_blocks = self._extract_code_blocks(script_content)
            if not code_blocks:
                error_msg = "No code blocks found in script content"
                logger.warning(error_msg)
                return self._create_execution_result(False, error_msg)
            
            results = []
            for lang, code in code_blocks:
                try:
                    if lang in ["bash", "shell", "sh"]:
                        output_dict = self.env_controller.run_bash_script(code)
                        status = (output_dict or {}).get("status")
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
                    results.append(f"[{lang.upper()}] Execution error: {str(e)}")
            
            execution_time = time.time() - execution_start
            execution_result = "\n".join(results)
            
            # 记录执行结果
            self.global_state.log_operation("executor", "code_execution_completed", {
                "execution_time": execution_time,
                "script_type": script_type,
                "result": execution_result
            })
            
            return self._create_execution_result(
                success=True,
                execution_time=execution_time,
                action={"type": "code_execution", "script_type": script_type, "result": execution_result}
            )
            
        except Exception as e:
            execution_time = time.time() - execution_start
            error_msg = f"Code execution failed: {str(e)}"
            logger.error(error_msg)
            return self._create_execution_result(False, error_msg, execution_time)

    def execute_code_blocks(self, code_blocks: List[Tuple[str, str]]) -> Dict[str, Any]:
        """
        执行代码块列表
        
        Args:
            code_blocks: 代码块列表，每个元素为 (语言, 代码) 的元组
            
        Returns:
            执行结果字典
        """
        if not self.env_controller:
            error_msg = "No environment controller available for code execution"
            logger.warning(error_msg)
            return self._create_execution_result(False, error_msg)
        
        execution_start = time.time()
        
        try:
            results = []
            for lang, code in code_blocks:
                try:
                    if lang in ["bash", "shell", "sh"]:
                        output_dict = self.env_controller.run_bash_script(code)
                        status = (output_dict or {}).get("status")
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
                    results.append(f"[{lang.upper()}] Execution error: {str(e)}")
            
            execution_time = time.time() - execution_start
            execution_result = "\n".join(results)
            
            # 记录执行结果
            self.global_state.add_event("executor", "code_blocks_execution_completed", 
                f"Code blocks execution completed in {execution_time:.2f}s")
            
            screenshot: Image.Image = self.hwi.dispatch(
                Screenshot())  # type: ignore
            self.global_state.set_screenshot(
                scale_screenshot_dimensions(screenshot, self.hwi))
            self.global_state.increment_step_num()
            
            return self._create_execution_result(
                success=True,
                execution_time=execution_time,
                action={"type": "code_blocks_execution", "result": execution_result}
            )
            
        except Exception as e:
            execution_time = time.time() - execution_start
            error_msg = f"Code blocks execution failed: {str(e)}"
            logger.error(error_msg)
            return self._create_execution_result(False, error_msg, execution_time)

    def _detect_script_type(self, content: str) -> str:
        """自动检测脚本类型"""
        content_lower = content.lower()
        if "```bash" in content_lower or "#!/bin/bash" in content_lower:
            return "bash"
        elif "```python" in content_lower or "#!/usr/bin/env python" in content_lower:
            return "python"
        else:
            # 默认返回bash
            return "bash"

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
    
    def _get_command_for_subtask(self, subtask_id: str):
        """获取指定subtask的最新command"""
        try:
            # 使用新的GlobalState方法获取当前command
            command = self.global_state.get_current_command_for_subtask(subtask_id)
            if command:
                logger.debug(f"Found current command {command.command_id} for subtask {subtask_id}")
            else:
                logger.debug(f"No current command found for subtask {subtask_id}")
            return command
            
        except Exception as e:
            logger.error(f"Error getting current command for subtask {subtask_id}: {e}")
            return None
    
    def _execute_action(self, subtask_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行具体的动作
        
        Args:
            subtask_id: subtask ID
            action: 要执行的动作字典
            
        Returns:
            执行结果
        """
        execution_start = time.time()
        
        try:
            logger.info(f"Executing action for subtask {subtask_id}: {action}")
            
            # 检查是否是memorize动作
            if isinstance(action, dict) and action.get("type") == "memorize":
                information = action.get("information", "")
                if information:
                    # 调用add_memorize_artifact方法
                    self.global_state.add_memorize_artifact(subtask_id, information)
                    logger.info(f"Memorize action processed for subtask {subtask_id}: {information[:100]}...")
                    
                    # 记录执行成功事件
                    self.global_state.add_event("executor", "memorize_success", 
                        f"Memorize action executed successfully for subtask {subtask_id}")
                    
                    execution_success = True
                    error_message = None
                    execution_time = time.time() - execution_start
                    
                    # 记录执行结果
                    self._record_execution_result(subtask_id, execution_success, error_message, execution_time)
                    
                    return self._create_execution_result(
                        success=execution_success,
                        error_message=error_message,
                        execution_time=execution_time,
                        action=action
                    )
            
            # 记录执行开始事件
            self.global_state.log_operation("executor", "action_start", {
                "subtask_id": subtask_id,
                "action": action
            })
            
            # 执行硬件动作
            try:
                self.hwi.dispatchDict(action)
                time.sleep(3)
                screenshot: Image.Image = self.hwi.dispatch(
                    Screenshot())  # type: ignore
                self.global_state.set_screenshot(
                    scale_screenshot_dimensions(screenshot, self.hwi))
                self.global_state.increment_step_num()
                execution_success = True
                error_message = None
                logger.info(f"Action executed successfully for subtask {subtask_id}")
                
            except Exception as e:
                execution_success = False
                error_message = str(e)
                logger.warning(f"Hardware dispatch failed for subtask {subtask_id}: {error_message}")
            
            execution_time = time.time() - execution_start
            
            # 记录执行结果
            self._record_execution_result(subtask_id, execution_success, error_message, execution_time)
            
            # 创建执行结果
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
    
    def _create_execution_result(self, success: bool, error_message: Optional[str] = None, 
                               execution_time: float = 0.0, action: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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