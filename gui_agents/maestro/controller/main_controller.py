"""
Main Controller for Agent-S
整合所有模块并提供统一的接口
"""

import time
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
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
from ..enums import ControllerState, TaskStatus, SubtaskStatus, TriggerCode, TriggerRole

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
        datetime_str: str = datetime.now().strftime("%Y%m%d_%H%M%S"),
        enable_snapshots: bool = True,
        snapshot_interval: int = 10,  # 每N步自动创建快照
        create_checkpoint_snapshots: bool = True  # 是否在关键状态创建检查点快照
    ):
        # 快照配置
        self.enable_snapshots = enable_snapshots
        self.snapshot_interval = snapshot_interval
        self.create_checkpoint_snapshots = create_checkpoint_snapshots
        self.last_snapshot_step = 0
        
        # 初始化全局状态
        self.global_state = self._registry_global_state(log_dir, datetime_str)
        
        # 基本配置
        self.platform = platform
        self.user_query = user_query
        self.max_steps = max_steps
        self.env = env
        self.env_password = env_password
        self.enable_search = enable_search
        self.enable_takeover = enable_takeover
        self.enable_rag = enable_rag
        self.backend = backend
        
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
        
        # 创建初始快照
        if self.enable_snapshots:
            self._create_initial_snapshot()

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
    
    def _create_initial_snapshot(self):
        """创建初始快照"""
        try:
            if self.enable_snapshots:
                # 准备配置参数
                config_params = {
                    "tools_dict": self.tools_dict,
                    "platform": self.platform,
                    "enable_search": self.enable_search,
                    "env_password": self.env_password,
                    "enable_takeover": self.enable_takeover,
                    "enable_rag": self.enable_rag,
                    "backend": self.backend,
                    "max_steps": self.max_steps
                }
                
                snapshot_id = self.global_state.create_snapshot(
                    description=f"Initial state for task: {self.user_query}",
                    snapshot_type="initial",
                    config_params=config_params
                )
                logger.info(f"Initial snapshot created: {snapshot_id}")
        except Exception as e:
            logger.warning(f"Failed to create initial snapshot: {e}")

    def _should_create_auto_snapshot(self) -> bool:
        """判断是否应该创建自动快照"""
        if not self.enable_snapshots:
            return False
        
        current_step = self.step_count
        return (current_step - self.last_snapshot_step) >= self.snapshot_interval

    def _create_auto_snapshot(self):
        """创建自动快照"""
        try:
            if self._should_create_auto_snapshot():
                # 准备配置参数
                config_params = {
                    "tools_dict": self.tools_dict,
                    "platform": self.platform,
                    "enable_search": self.enable_search,
                    "env_password": self.env_password,
                    "enable_takeover": self.enable_takeover,
                    "enable_rag": self.enable_rag,
                    "backend": self.backend,
                    "max_steps": self.max_steps
                }
                
                snapshot_id = self.global_state.create_snapshot(
                    description=f"Auto snapshot at step {self.step_count}",
                    snapshot_type="auto",
                    config_params=config_params
                )
                self.last_snapshot_step = self.step_count
                logger.debug(f"Auto snapshot created: {snapshot_id}")
        except Exception as e:
            logger.warning(f"Failed to create auto snapshot: {e}")

    def _create_checkpoint_snapshot(self, checkpoint_name: str = ""):
        """创建检查点快照"""
        try:
            if self.enable_snapshots and self.create_checkpoint_snapshots:
                if not checkpoint_name:
                    checkpoint_name = f"checkpoint_step_{self.step_count}"
                
                snapshot_id = self.global_state.create_snapshot(
                    description=f"Checkpoint: {checkpoint_name}",
                    snapshot_type="checkpoint"
                )
                logger.info(f"Checkpoint snapshot created: {snapshot_id}")
                return snapshot_id
        except Exception as e:
            logger.warning(f"Failed to create checkpoint snapshot: {e}")
        return None

    def _create_error_snapshot(self, error_message: str, error_type: str = "unknown"):
        """创建错误快照"""
        try:
            if self.enable_snapshots:
                snapshot_id = self.global_state.create_snapshot(
                    description=f"Error: {error_message}",
                    snapshot_type=f"error_{error_type}"
                )
                logger.info(f"Error snapshot created: {snapshot_id}")
                return snapshot_id
        except Exception as e:
            logger.warning(f"Failed to create error snapshot: {e}")
        return None

    def _handle_snapshot_creation(self, current_state: ControllerState):
        """处理快照创建逻辑"""
        if not self.enable_snapshots:
            return
        
        try:
            # 检查是否应该创建自动快照
            self._create_auto_snapshot()
            
            # 在关键状态创建检查点快照
            if self.create_checkpoint_snapshots:
                if current_state in [ControllerState.PLAN, ControllerState.QUALITY_CHECK, ControllerState.FINAL_CHECK]:
                    self._create_checkpoint_snapshot(f"checkpoint_{current_state.value.lower()}")
                    
        except Exception as e:
            logger.warning(f"Error in snapshot creation: {e}")
    
    def execute_single_step(self, steps: int = 1) -> None:
        """单步执行若干次状态机逻辑（执行 steps 步，不进入循环）"""
        if steps is None or steps <= 0:
            steps = 1
            
        try:
            for step_index in range(steps):
                # 1. 检查是否应该终止（单步序列）
                if self.state_machine.should_exit_loop():
                    logger.info("Task fulfilled or rejected, terminating single step batch")
                    break

                # 2. 获取当前状态
                current_state = self.state_machine.get_current_state()
                logger.info(f"Current state (single step {step_index + 1}/{steps}): {current_state}")

                # 3. 处理快照创建
                self._handle_snapshot_creation(current_state)

                # 4. 根据状态执行相应处理（一次一步）
                self._handle_state(current_state)

                # 5. 每步结束后，处理规则并更新状态
                self.state_machine.process_rules_and_update_states()

        except Exception as e:
            logger.error(f"Error in single step batch: {e}")
            # 创建错误快照
            self._create_error_snapshot(str(e), "single_step_batch")
            
            self.global_state.add_event(
                "controller", "error", f"Single step batch error: {str(e)}")
            # 错误恢复：回到INIT状态（单步序列）
            self.state_machine.switch_state(
                ControllerState.INIT, TriggerRole.CONTROLLER, f"Error recovery from single step batch: {str(e)}", TriggerCode.ERROR_RECOVERY)
    
    def execute_main_loop(self) -> None:
        """主循环执行 - 基于状态状态机"""
        logger.info("Starting main loop execution")

        # 记录主循环开始时间
        main_loop_start_time = time.time()

        while True:
            try:
                # 1. 检查是否应该退出循环
                if self.state_machine.should_exit_loop():
                    logger.info("Task fulfilled or rejected, breaking main loop")
                    break

                # 2. 获取当前状态
                current_state = self.state_machine.get_current_state()

                # 3. 处理快照创建
                self._handle_snapshot_creation(current_state)

                # 4. 根据状态执行相应处理
                self._handle_state(current_state)
                
                # 如果是执行动作状态，增加步数计数
                if current_state == ControllerState.EXECUTE_ACTION:
                    self.increment_step_count()

                # 5. 每次循环结束后，处理规则并更新状态
                self.state_machine.process_rules_and_update_states()

                # 6. 增加轮次计数
                self.increment_turn_count()

                # 7. 状态间短暂等待
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                # 创建错误快照
                self._create_error_snapshot(str(e), "main_loop")
                
                self.global_state.log_operation(
                    "controller", "error", {"error": f"Main loop error: {str(e)}"})
                # 错误恢复：回到INIT状态
                self.state_machine.switch_state(
                    ControllerState.INIT, TriggerRole.CONTROLLER, f"Error recovery from main loop: {str(e)}", TriggerCode.ERROR_RECOVERY)
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
        
        # 创建完成快照
        if self.enable_snapshots:
            self._create_checkpoint_snapshot("task_completed")
        
        logger.info(
            f"Main loop completed in {main_loop_duration:.2f}s with {counters['step_count']} steps and {counters['turn_count']} turns"
        )
    
    def _handle_state(self, current_state: ControllerState):
        """根据状态执行相应处理"""
        if current_state == ControllerState.INIT:
            new_state, trigger_role, trigger_details, trigger_code = self.state_handlers.handle_init_state()
            self.state_machine.switch_state(new_state, trigger_role, trigger_details, trigger_code)
            
        elif current_state == ControllerState.GET_ACTION:
            new_state, trigger_role, trigger_details, trigger_code = self.state_handlers.handle_get_action_state()
            self.state_machine.switch_state(new_state, trigger_role, trigger_details, trigger_code)
            
        elif current_state == ControllerState.EXECUTE_ACTION:
            new_state, trigger_role, trigger_details, trigger_code = self.state_handlers.handle_execute_action_state()
            self.state_machine.switch_state(new_state, trigger_role, trigger_details, trigger_code)
            
        elif current_state == ControllerState.QUALITY_CHECK:
            new_state, trigger_role, trigger_details, trigger_code = self.state_handlers.handle_quality_check_state()
            self.state_machine.switch_state(new_state, trigger_role, trigger_details, trigger_code)
            
        elif current_state == ControllerState.PLAN:
            new_state, trigger_role, trigger_details, trigger_code = self.state_handlers.handle_plan_state()
            self.state_machine.switch_state(new_state, trigger_role, trigger_details, trigger_code)
            
        elif current_state == ControllerState.SUPPLEMENT:
            new_state, trigger_role, trigger_details, trigger_code = self.state_handlers.handle_supplement_state()
            self.state_machine.switch_state(new_state, trigger_role, trigger_details, trigger_code)
            
        elif current_state == ControllerState.FINAL_CHECK:
            new_state, trigger_role, trigger_details, trigger_code = self.state_handlers.handle_final_check_state()
            self.state_machine.switch_state(new_state, trigger_role, trigger_details, trigger_code)
            
        elif current_state == ControllerState.DONE:
            logger.info("Task completed")
        else:
            logger.error(f"Unknown state: {current_state}")
            self.state_machine.switch_state(
                ControllerState.INIT, TriggerRole.CONTROLLER, f"Unknown state encountered: {current_state}", TriggerCode.UNKNOWN_STATE)
    
    def get_controller_info(self) -> Dict[str, Any]:
        """获取控制器信息"""
        return {
            "current_state": self.state_machine.get_current_state().value,
            "state_start_time": self.global_state.get_controller_state_start_time(),
            "state_switch_count": self.state_machine.get_state_switch_count(),
            "plan_num": self.global_state.get_plan_num(),
            "controller_state": self.global_state.get_controller_state(),
            "task_id": self.global_state.task_id,
            "executor_status": self.executor.get_execution_status(),
            "snapshot_info": {
                "enabled": self.enable_snapshots,
                "interval": self.snapshot_interval,
                "last_snapshot_step": self.last_snapshot_step,
                "checkpoint_snapshots": self.create_checkpoint_snapshots,
                "note": "Use create_manual_snapshot() to create snapshots"
            }
        }

    def reset_controller(self):
        """重置控制器状态"""
        logger.info("Resetting controller")
        self.state_machine.reset_state_switch_count()
        self.global_state.reset_controller_state()
        self.reset_counters()  # 重置计数器
        
        # 重置快照相关状态
        self.last_snapshot_step = 0
        
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

    # ========= Snapshot Management Methods =========
    def create_manual_snapshot(self, description: str = "") -> Optional[str]:
        """手动创建快照"""
        try:
            if not self.enable_snapshots:
                logger.warning("Snapshots are disabled")
                return None
            
            if not description:
                description = f"Manual snapshot at step {self.step_count}"
            
            snapshot_id = self.global_state.create_snapshot(description, "manual")
            logger.info(f"Manual snapshot created: {snapshot_id}")
            return snapshot_id
            
        except Exception as e:
            logger.error(f"Failed to create manual snapshot: {e}")
            return None

 