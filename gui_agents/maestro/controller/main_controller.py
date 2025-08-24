"""
Main Controller for Agent-S
整合所有模块并提供统一的接口
"""

import time
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import platform

from gui_agents.maestro.Action import Screenshot

from ..data_models import SubtaskData, TaskData
from desktop_env.desktop_env import DesktopEnv
from ..hardware_interface import HardwareInterface
from PIL import Image

from ..utils.screenShot import scale_screenshot_dimensions
from ...store.registry import Registry

from ..new_global_state import NewGlobalState
from ..new_manager import NewManager
from ..new_executor import NewExecutor
from ..enums import ControllerState, TaskStatus, SubtaskStatus

from .config_manager import ConfigManager
from .rule_engine import RuleEngine
from .state_handlers import StateHandlers
from .state_machine import StateMachine

logger = logging.getLogger(__name__)


class MainController:
    """主控制器，整合所有模块并提供统一的接口"""
    
    def __init__(
        self,
        platform: str = platform.system().lower(),
        memory_root_path: str = os.getcwd(),
        memory_folder_name: str = "kb_s2",
        kb_release_tag: str = "v0.2.2",
        enable_takeover: bool = False,
        enable_search: bool = False,
        enable_rag: bool = False,
        backend: str = "pyautogui",
        user_query: str = "",
        max_steps: int = 50,
        env: Optional[DesktopEnv] = None,
        env_password: str = "password",
        log_dir: str = "logs",
        datetime_str: str = datetime.now().strftime("%Y%m%d_%H%M%S")
    ):
        # 初始化全局状态
        self.global_state = self._registry_global_state(log_dir, datetime_str)
        
        # 基本配置
        self.platform = platform
        self.user_query = user_query
        self.max_steps = max_steps
        self.env = env
        self.env_password = env_password
        
        # 初始化配置管理器
        self.config_manager = ConfigManager(memory_root_path, memory_folder_name)
        self.tools_dict = self.config_manager.load_tools_configuration()
        self.local_kb_path = self.config_manager.setup_knowledge_base(platform)
        
        # 初始化manager
        manager_params = {
            "tools_dict": self.tools_dict,
            "global_state": self.global_state,
            "local_kb_path": self.local_kb_path,
            "platform": self.platform,
            "enable_search": enable_search
        }
        self.manager = NewManager(**manager_params)

        # 初始化硬件接口
        backend_kwargs = {
            "platform": platform, 
            "env_controller": self.env
        }
        self.hwi = HardwareInterface(backend=backend, **backend_kwargs)
        logger.info(f"Hardware interface initialized with backend: {backend}")

        # 初始化executor
        executor_params = {
            "global_state": self.global_state,
            "hardware_interface": self.hwi,
            "env_controller": self.env
        }
        self.executor = NewExecutor(**executor_params)
        logger.info("Executor initialized")
        
        # 初始化规则引擎
        rule_engine_params: Dict[str, Any] = dict(
            global_state=self.global_state,
            max_steps=self.max_steps
        )
        self.rule_engine = RuleEngine(**rule_engine_params)
        
        # 初始化状态处理器
        state_handlers_params: Dict[str, Any] = dict(
            global_state=self.global_state,
            manager=self.manager,
            executor=self.executor,
            tools_dict=self.tools_dict,
            platform=self.platform,
            enable_search=enable_search,
            env_password=self.env_password
        )
        self.state_handlers = StateHandlers(**state_handlers_params)
        
        # 初始化状态机
        state_machine_params: Dict[str, Any] = dict(
            global_state=self.global_state,
            rule_engine=self.rule_engine,
            state_handlers=self.state_handlers
        )
        self.state_machine = StateMachine(**state_machine_params)
        
        # 初始化计数器
        self.reset_counters()
        
        # 初始化任务，生成第一次截图
        self._handle_task_init()
    
    def _registry_global_state(self, log_dir: str, datetime_str: str):
        """注册全局状态"""
        # Ensure necessary directory structure exists
        timestamp_dir = os.path.join(log_dir, datetime_str)
        cache_dir = os.path.join(timestamp_dir, "cache", "screens")
        state_dir = os.path.join(timestamp_dir, "state")

        os.makedirs(cache_dir, exist_ok=True)
        os.makedirs(state_dir, exist_ok=True)

        global_state = NewGlobalState(
            screenshot_dir=cache_dir,
            state_dir=state_dir,
            agent_log_path=os.path.join(timestamp_dir, "agent_log.json"),
            display_info_path=os.path.join(timestamp_dir, "display.json")
        )
        Registry.register("GlobalStateStore", global_state)
        return global_state
    
    def _handle_task_init(self):
        """立项状态处理"""
        logger.info("Handling INIT state")
        self.global_state.set_task_objective(self.user_query)
        # 初始化控制器状态
        self.global_state.reset_controller_state()
        logger.info("MainController initialized")

        # 首次获取截图
        screenshot: Image.Image = self.hwi.dispatch(Screenshot())  # type: ignore
        self.global_state.set_screenshot(scale_screenshot_dimensions(screenshot, self.hwi))
    
    def execute_single_step(self, steps: int = 1) -> None:
        """单步执行若干次状态机逻辑（执行 steps 步，不进入循环）"""
        if steps is None or steps <= 0:
            steps = 1
            
        try:
            for step_index in range(steps):
                # 1. 检查是否应该终止（单步序列）
                if self.state_machine.should_exit_loop(self.max_steps):
                    logger.info("Task fulfilled or rejected, terminating single step batch")
                    break

                # 2. 获取当前状态
                current_state = self.state_machine.get_current_state()
                logger.info(f"Current state (single step {step_index + 1}/{steps}): {current_state}")

                # 3. 根据状态执行相应处理（一次一步）
                self._handle_state(current_state)

                # 4. 每步结束后，处理规则并更新状态
                self.state_machine.process_rules_and_update_states()

        except Exception as e:
            logger.error(f"Error in single step batch: {e}")
            self.global_state.add_event(
                "controller", "error", f"Single step batch error: {str(e)}")
            # 错误恢复：回到INIT状态（单步序列）
            self.state_machine.switch_state(
                ControllerState.INIT, "error_recovery_single_step", f"Error recovery from single step batch: {str(e)}")
    
    def execute_main_loop(self) -> None:
        """主循环执行 - 基于状态状态机"""
        logger.info("Starting main loop execution")

        # 记录主循环开始时间
        main_loop_start_time = time.time()

        while True:
            try:
                # 1. 检查是否应该退出循环
                if self.state_machine.should_exit_loop(self.max_steps):
                    logger.info("Task fulfilled or rejected, breaking main loop")
                    break

                # 2. 获取当前状态
                current_state = self.state_machine.get_current_state()

                # 3. 根据状态执行相应处理
                self._handle_state(current_state)
                
                # 如果是执行动作状态，增加步数计数
                if current_state == ControllerState.EXECUTE_ACTION:
                    self.increment_step_count()

                # 4. 每次循环结束后，处理规则并更新状态
                self.state_machine.process_rules_and_update_states()

                # 5. 增加轮次计数
                self.increment_turn_count()

                # 6. 状态间短暂等待
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                self.global_state.log_operation(
                    "controller", "error", {"error": f"Main loop error: {str(e)}"})
                # 错误恢复：回到INIT状态
                self.state_machine.switch_state(
                    ControllerState.INIT, "error_recovery", f"Error recovery from main loop: {str(e)}")
                time.sleep(1)

        # 记录主循环结束统计
        main_loop_duration = time.time() - main_loop_start_time
        counters = self.get_counters()
        self.global_state.log_operation(
            "controller", "main_loop_completed", {
                "duration": main_loop_duration,
                "step_count": counters["step_count"],
                "turn_count": counters["turn_count"],
                "final_state": self.state_machine.get_current_state().value
            })
        logger.info(
            f"Main loop completed in {main_loop_duration:.2f}s with {counters['step_count']} steps and {counters['turn_count']} turns"
        )
    
    def _handle_state(self, current_state: ControllerState):
        """根据状态执行相应处理"""
        if current_state == ControllerState.INIT:
            new_state, trigger, details = self.state_handlers.handle_init_state()
            self.state_machine.switch_state(new_state, trigger, details)
            
        elif current_state == ControllerState.GET_ACTION:
            new_state, trigger, details = self.state_handlers.handle_get_action_state()
            self.state_machine.switch_state(new_state, trigger, details)
            
        elif current_state == ControllerState.EXECUTE_ACTION:
            new_state, trigger, details = self.state_handlers.handle_execute_action_state()
            self.state_machine.switch_state(new_state, trigger, details)
            
        elif current_state == ControllerState.QUALITY_CHECK:
            new_state, trigger, details = self.state_handlers.handle_quality_check_state()
            self.state_machine.switch_state(new_state, trigger, details)
            
        elif current_state == ControllerState.PLAN:
            new_state, trigger, details = self.state_handlers.handle_plan_state()
            self.state_machine.switch_state(new_state, trigger, details)
            
        elif current_state == ControllerState.SUPPLEMENT:
            new_state, trigger, details = self.state_handlers.handle_supplement_state()
            self.state_machine.switch_state(new_state, trigger, details)
            
        elif current_state == ControllerState.FINAL_CHECK:
            new_state, trigger, details = self.state_handlers.handle_final_check_state()
            self.state_machine.switch_state(new_state, trigger, details)
            
        elif current_state == ControllerState.DONE:
            logger.info("Task completed")
        else:
            logger.error(f"Unknown state: {current_state}")
            self.state_machine.switch_state(
                ControllerState.INIT, "unknown_state", f"Unknown state encountered: {current_state}")
    
    def get_controller_info(self) -> Dict[str, Any]:
        """获取控制器信息"""
        return {
            "current_state": self.state_machine.get_current_state().value,
            "state_start_time": self.global_state.get_controller_state_start_time(),
            "state_switch_count": self.state_machine.get_state_switch_count(),
            "plan_num": self.global_state.get_plan_num(),
            "controller_state": self.global_state.get_controller_state(),
            "task_id": self.global_state.task_id,
            "executor_status": self.executor.get_execution_status()
        }

    def reset_controller(self):
        """重置控制器状态"""
        logger.info("Resetting controller")
        self.state_machine.reset_state_switch_count()
        self.global_state.reset_controller_state()
        self.reset_counters()  # 重置计数器
        
        # 重置plan_num
        task = self.global_state.get_task()
        if task:
            task.plan_num = 0
            self.global_state.set_task(task)
            logger.info("Plan number reset to 0")
        
        logger.info("Controller reset completed")

    def reset_counters(self) -> None:
        """重置统计计数器"""
        self.step_count = 0
        self.turn_count = 0
        logger.info("Counters reset: step_count=0, turn_count=0")

    def increment_step_count(self) -> None:
        """增加步数计数"""
        self.step_count += 1
        logger.debug(f"Step count incremented: {self.step_count}")

    def increment_turn_count(self) -> None:
        """增加轮次计数"""
        self.turn_count += 1
        logger.debug(f"Turn count incremented: {self.turn_count}")

    def get_counters(self) -> Dict[str, int]:
        """获取当前计数器状态"""
        return {"step_count": self.step_count, "turn_count": self.turn_count} 