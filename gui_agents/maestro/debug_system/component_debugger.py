"""
组件调试器 - 支持调试Worker、Evaluator、Manager等核心组件
"""

from typing import Dict, Any, Optional

from pyautogui import screenshot

from gui_agents.maestro.debug_system.snapshot_debugger import SnapshotDebugger
from ..controller.state_handlers import NewWorker, Evaluator
from ..controller.main_controller import NewManager


class ComponentDebugger:
    """组件调试器 - 支持调试各种核心组件"""
    
    def __init__(self, snapshot_debugger):
        self.snapshot_debugger: SnapshotDebugger = snapshot_debugger
        self.current_worker = None
        self.current_evaluator = None
        self.current_manager = None
        
    def debug_worker(self, snapshot_id: str) -> Optional[NewWorker]:
        """调试Worker组件"""
        if not self.snapshot_debugger.load_snapshot(snapshot_id):
            return None
            
        try:
            worker_params = self.snapshot_debugger.get_worker_params()
            self.current_worker = NewWorker(**worker_params)
            self.current_worker.process_subtask_and_create_command()
            print(f"Worker组件已创建，准备调试快照: {snapshot_id}")
            return self.current_worker
            
        except Exception as e:
            print(f"创建Worker组件失败: {e}")
            return None
    
    def debug_evaluator(self, snapshot_id: str) -> Optional[Evaluator]:
        """调试Evaluator组件"""
        if not self.snapshot_debugger.load_snapshot(snapshot_id):
            return None
            
        try:
            evaluator_params = self.snapshot_debugger.get_evaluator_params()
            self.current_evaluator = Evaluator(**evaluator_params)
            print(f"Evaluator组件已创建，准备调试快照: {snapshot_id}")
            return self.current_evaluator
            
        except Exception as e:
            print(f"创建Evaluator组件失败: {e}")
            return None
    
    def debug_manager(self, snapshot_id: str) -> Optional[NewManager]:
        """调试Manager组件"""
        if not self.snapshot_debugger.load_snapshot(snapshot_id):
            return None
            
        try:
            screenshot = self.snapshot_debugger.global_state.get_screenshot()
            print(f"screenshot: {screenshot.__sizeof__()}")
            manager_params = self.snapshot_debugger.get_manager_params()
            self.current_manager = NewManager(**manager_params)
            self.current_manager.plan_task("replan")
            print(f"Manager组件已创建，准备调试快照: {snapshot_id}")
            return self.current_manager
            
        except Exception as e:
            print(f"创建Manager组件失败: {e}")
            return None
    
    def step_worker(self) -> bool:
        """单步执行Worker"""
        if not self.current_worker:
            print("请先创建Worker组件")
            return False
            
        try:
            print("执行Worker单步调试...")
            self.current_worker.process_subtask_and_create_command()
            print("Worker单步执行完成")
            return True
            
        except Exception as e:
            print(f"Worker执行失败: {e}")
            return False
    
    def get_worker_state(self) -> Dict[str, Any]:
        """获取Worker当前状态"""
        if not self.current_worker:
            return {}
            
        # 这里可以根据Worker的实际结构来获取状态信息
        return {
            "worker_created": True,
            "global_state": self.snapshot_debugger.global_state.get_current_state_summary()
        }
    
    def get_evaluator_state(self) -> Dict[str, Any]:
        """获取Evaluator当前状态"""
        if not self.current_evaluator:
            return {}
            
        return {
            "evaluator_created": True,
            "global_state": self.snapshot_debugger.global_state.get_current_state_summary()
        }
    
    def get_manager_state(self) -> Dict[str, Any]:
        """获取Manager当前状态"""
        if not self.current_manager:
            return {}
            
        return {
            "manager_created": True,
            "global_state": self.snapshot_debugger.global_state.get_current_state_summary()
        }
    
    def reset_debug_session(self):
        """重置调试会话"""
        self.current_worker = None
        self.current_evaluator = None
        self.current_manager = None
        print("调试会话已重置") 