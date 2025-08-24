"""
主调试器 - 整合快照调试和组件调试功能
"""

from typing import Dict, Any, Optional
from .snapshot_debugger import SnapshotDebugger
from .component_debugger import ComponentDebugger


class MainDebugger:
    """主调试器 - 提供完整的调试功能"""
    
    def __init__(self, snapshot_dir: str = "snapshots", state_dir: str = "runtime"):
        self.snapshot_debugger = SnapshotDebugger(snapshot_dir, state_dir)
        self.component_debugger = ComponentDebugger(self.snapshot_debugger)
        
    def list_snapshots(self) -> list:
        """列出所有可用快照"""
        return self.snapshot_debugger.list_snapshots()
    
    def show_snapshot_info(self, snapshot_id: str):
        """显示快照信息"""
        info = self.snapshot_debugger.get_snapshot_info(snapshot_id)
        if info:
            print(f"\n=== 快照信息: {snapshot_id} ===")
            print(f"描述: {info.get('description', '无')}")
            print(f"类型: {info.get('snapshot_type', '无')}")
            print(f"创建时间: {info.get('created_at', '无')}")
            print(f"配置参数: {info.get('config_params', {})}")
        else:
            print(f"快照 {snapshot_id} 不存在或无法读取")
    
    def debug_worker_from_snapshot(self, snapshot_id: str) -> bool:
        """从快照调试Worker"""
        print(f"\n=== 从快照调试Worker: {snapshot_id} ===")
        worker = self.component_debugger.debug_worker(snapshot_id)
        if worker:
            print("✅ Worker组件创建成功，可以开始单步调试")
            return True
        else:
            print("❌ Worker组件创建失败")
            return False
    
    def debug_evaluator_from_snapshot(self, snapshot_id: str) -> bool:
        """从快照调试Evaluator"""
        print(f"\n=== 从快照调试Evaluator: {snapshot_id} ===")
        evaluator = self.component_debugger.debug_evaluator(snapshot_id)
        if evaluator:
            print("✅ Evaluator组件创建成功，可以开始调试")
            return True
        else:
            print("❌ Evaluator组件创建失败")
            return False
    
    def debug_manager_from_snapshot(self, snapshot_id: str) -> bool:
        """从快照调试Manager"""
        print(f"\n=== 从快照调试Manager: {snapshot_id} ===")
        manager = self.component_debugger.debug_manager(snapshot_id)
        if manager:
            print("✅ Manager组件创建成功，可以开始调试")
            return True
        else:
            print("❌ Manager组件创建失败")
            return False
    
    def step_worker_execution(self) -> bool:
        """单步执行Worker"""
        return self.component_debugger.step_worker()
    
    def get_current_debug_state(self) -> Dict[str, Any]:
        """获取当前调试状态"""
        return {
            "worker_state": self.component_debugger.get_worker_state(),
            "evaluator_state": self.component_debugger.get_evaluator_state(),
            "manager_state": self.component_debugger.get_manager_state(),
            "global_state": self.snapshot_debugger.global_state.get_controller_state() if self.snapshot_debugger.global_state else {}
        }
    
    def reset_debug_session(self):
        """重置调试会话"""
        self.component_debugger.reset_debug_session()
        print("调试会话已重置")
    
    def interactive_debug(self):
        """交互式调试模式"""
        print("\n=== 交互式调试模式 ===")
        print("可用命令:")
        print("  list - 列出所有快照")
        print("  info <snapshot_id> - 显示快照信息")
        print("  debug_worker <snapshot_id> - 调试Worker")
        print("  debug_evaluator <snapshot_id> - 调试Evaluator")
        print("  debug_manager <snapshot_id> - 调试Manager")
        print("  step_worker - 单步执行Worker")
        print("  state - 显示当前状态")
        print("  reset - 重置调试会话")
        print("  quit - 退出调试模式")
        
        while True:
            try:
                command = input("\n调试命令> ").strip().split()
                if not command:
                    continue
                    
                cmd = command[0].lower()
                
                if cmd == "quit":
                    print("退出调试模式")
                    break
                elif cmd == "list":
                    snapshots = self.list_snapshots()
                    if snapshots:
                        print("可用快照:")
                        for snapshot in snapshots:
                            print(f"  - {snapshot}")
                    else:
                        print("没有可用的快照")
                elif cmd == "info" and len(command) > 1:
                    self.show_snapshot_info(command[1])
                elif cmd == "debug_worker" and len(command) > 1:
                    self.debug_worker_from_snapshot(command[1])
                elif cmd == "debug_evaluator" and len(command) > 1:
                    self.debug_evaluator_from_snapshot(command[1])
                elif cmd == "debug_manager" and len(command) > 1:
                    self.debug_manager_from_snapshot(command[1])
                elif cmd == "step_worker":
                    self.step_worker_execution()
                elif cmd == "state":
                    state = self.get_current_debug_state()
                    print("当前调试状态:")
                    for key, value in state.items():
                        print(f"  {key}: {value}")
                elif cmd == "reset":
                    self.reset_debug_session()
                else:
                    print("未知命令或参数不足")
                    
            except KeyboardInterrupt:
                print("\n退出调试模式")
                break
            except Exception as e:
                print(f"命令执行错误: {e}")


def create_debugger(snapshot_dir: str = "snapshots", state_dir: str = "runtime") -> MainDebugger:
    """创建调试器实例"""
    return MainDebugger(snapshot_dir, state_dir) 