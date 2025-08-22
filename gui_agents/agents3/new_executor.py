"""
New Executor Implementation
专门负责从global state中获取和执行动作的执行器模块
"""

import time
import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from gui_agents.agents3.hardware_interface import HardwareInterface
from .new_global_state import NewGlobalState
from .enums import SubtaskStatus
from desktop_env.desktop_env import DesktopEnv

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
        执行指定subtask的动作
        
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
            
            # 执行动作
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
            self.global_state.add_event("executor", "code_execution_completed", 
                f"Code execution completed in {execution_time:.2f}s")
            
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
            
            # 记录执行开始事件
            self.global_state.add_event("executor", "action_start", 
                f"Starting action execution for subtask {subtask_id}")
            
            # 执行硬件动作
            try:
                self.hwi.dispatchDict(action)
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
                self.global_state.add_event("executor", "action_success", 
                    f"Action executed successfully for subtask {subtask_id} in {execution_time:.2f}s")
                
                # 可以选择更新subtask状态为已执行，但状态管理应该由Controller决定
                # self.global_state.update_subtask_status(subtask_id, SubtaskStatus.FULFILLED, "Action executed successfully")
                
            else:
                # 记录执行失败事件
                self.global_state.add_event("executor", "action_error", 
                    f"Action execution failed for subtask {subtask_id}: {error_message}")
                
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