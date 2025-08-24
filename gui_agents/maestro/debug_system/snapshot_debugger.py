"""
快照调试器 - 从快照恢复状态并准备调试环境
"""

import json
import os
from typing import Dict, Any, Optional
from ..new_global_state import NewGlobalState
from ..simple_snapshot import SimpleSnapshot


class SnapshotDebugger:
    """快照调试器 - 从快照恢复状态并准备调试环境"""
    
    def __init__(self, snapshot_dir: str = "snapshots", state_dir: str = "runtime"):
        self.snapshot_dir = snapshot_dir
        self.state_dir = state_dir
        self.global_state = None
        self.snapshot_data = None
        
    def load_snapshot(self, snapshot_id: str) -> bool:
        """加载指定快照"""
        try:
            # 创建快照系统
            snapshot_system = SimpleSnapshot(self.state_dir)
            
            # 使用 restore_snapshot_and_create_globalstate 方式恢复快照
            restore_result, target_path = snapshot_system.restore_snapshot_and_create_globalstate(
                snapshot_id, None
            )
            
            if not restore_result or not target_path:
                print(f"❌ 快照恢复失败: {snapshot_id}")
                return False
            
            # 从恢复结果中读取快照数据
            self.snapshot_data = restore_result.get("snapshot_metadata", {})
            
            # 构建路径
            state_dir = os.path.join(target_path, "state")
            cache_dir = os.path.join(target_path, "cache")
            screens_dir = os.path.join(cache_dir, "screens")
            display_path = os.path.join(target_path, "display.json")
            
            # 创建GlobalState对象
            self.global_state = NewGlobalState(
                screenshot_dir=screens_dir,
                state_dir=state_dir,
                display_info_path=display_path
            )
            
            print(f"✅ 成功加载快照: {snapshot_id}")
            print(f"   恢复目录: {target_path}")
            print(f"   状态目录: {state_dir}")
            print(f"   截图目录: {screens_dir}")
            return True
                
        except Exception as e:
            print(f"❌ 加载快照失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_worker_params(self) -> Dict[str, Any]:
        """获取Worker参数"""
        if not self.snapshot_data:
            raise ValueError("请先加载快照")
            
        config_params = self.snapshot_data.get('config_params', {})
        
        # 从快照中提取Worker所需参数
        worker_params = {
            "tools_dict": config_params.get('tools_dict', {}),
            "global_state": self.global_state,
            "platform": config_params.get('platform', 'default'),
            "enable_search": config_params.get('enable_search', True),
            "client_password": config_params.get('client_password', '')
        }
        
        return worker_params
    
    def get_evaluator_params(self) -> Dict[str, Any]:
        """获取Evaluator参数"""
        if not self.snapshot_data:
            raise ValueError("请先加载快照")
            
        config_params = self.snapshot_data.get('config_params', {})
        
        evaluator_params = {
            "global_state": self.global_state,
            "tools_dict": config_params.get('tools_dict', {})
        }
        
        return evaluator_params
    
    def get_manager_params(self) -> Dict[str, Any]:
        """获取Manager参数"""
        if not self.snapshot_data:
            raise ValueError("请先加载快照")
            
        config_params = self.snapshot_data.get('config_params', {})
        
        manager_params = {
            "tools_dict": config_params.get('tools_dict', {}),
            "global_state": self.global_state,
            "local_kb_path": config_params.get('local_kb_path', ''),
            "platform": config_params.get('platform', 'default'),
            "enable_search": config_params.get('enable_search', True)
        }
        
        return manager_params
    
    def list_snapshots(self) -> list:
        """列出所有可用快照"""
        snapshots = []
        if os.path.exists(self.snapshot_dir):
            for item in os.listdir(self.snapshot_dir):
                item_path = os.path.join(self.snapshot_dir, item)
                # 检查是否是目录
                if os.path.isdir(item_path):
                    # 检查目录中是否有metadata.json文件
                    metadata_file = os.path.join(item_path, "metadata.json")
                    if os.path.exists(metadata_file):
                        snapshots.append(item)
                # 兼容旧的.json文件格式
                elif item.endswith('.json'):
                    snapshot_id = item[:-5]  # 移除.json后缀
                    snapshots.append(snapshot_id)
        return sorted(snapshots)
    
    def get_snapshot_info(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """获取快照信息"""
        try:
            # 首先尝试作为目录处理
            snapshot_dir = os.path.join(self.snapshot_dir, snapshot_id)
            metadata_file = os.path.join(snapshot_dir, "metadata.json")
            
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            # 兼容旧的.json文件格式
            snapshot_file = os.path.join(self.snapshot_dir, f"{snapshot_id}.json")
            if os.path.exists(snapshot_file):
                with open(snapshot_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"读取快照信息失败: {e}")
        return None 