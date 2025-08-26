import os
import shutil
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


class SimpleSnapshot:
    """增强的快照系统 - 复制state文件夹、记录截图ID，并保存关键配置参数"""
    
    def __init__(self, runtime_dir: str):
        self.runtime_dir = Path(runtime_dir)
        self.snapshots_dir = self.runtime_dir / "snapshots"
        self.state_dir = self.runtime_dir / "state"
        self.screenshots_dir = self.runtime_dir / "cache" / "screens"
        
        # 确保快照目录存在
        self.snapshots_dir.mkdir(exist_ok=True)
    
    def create_snapshot(self, description: str = "", snapshot_type: str = "manual", 
                       config_params: Optional[Dict[str, Any]] = None) -> str:
        """
        创建快照
        
        Args:
            description: 快照描述
            snapshot_type: 快照类型
            config_params: 关键配置参数，包括：
                - tools_dict: 工具配置字典
                - platform: 平台信息
                - enable_search: 搜索开关
                - env_password: 环境密码
                - enable_takeover: 接管开关
                - enable_rag: RAG开关
                - backend: 后端类型
                - max_steps: 最大步数
        """
        # 生成快照ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_id = f"snapshot_{timestamp}"
        
        # 创建快照目录
        snapshot_dir = self.snapshots_dir / snapshot_id
        snapshot_dir.mkdir(exist_ok=True)
        
        # 1. 复制整个state文件夹
        if self.state_dir.exists():
            state_backup = snapshot_dir / "state"
            # 如果目标目录已存在，先删除
            if state_backup.exists():
                shutil.rmtree(state_backup)
            shutil.copytree(self.state_dir, state_backup)
            # print(f"✅ 已复制state文件夹到: {state_backup}")
        
        # 2. 获取当前截图ID列表
        screenshot_ids = []
        if self.screenshots_dir.exists():
            # 支持多种图片格式
            for ext in ['*.png', '*.jpg', '*.jpeg', '*.webp']:
                for screenshot_file in self.screenshots_dir.glob(ext):
                    screenshot_ids.append(screenshot_file.stem)
        
        # 3. 记录快照元数据和配置参数
        metadata = {
            "snapshot_id": snapshot_id,
            "timestamp": timestamp,
            "description": description,
            "type": snapshot_type,
            "screenshot_ids": screenshot_ids,
            "state_folder_copied": True,
            "config_params": config_params or {}
        }
        
        # 保存元数据
        metadata_file = snapshot_dir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        # print(f"🎯 快照创建成功: {snapshot_id}")
        # print(f"   描述: {description}")
        # print(f"   截图数量: {len(screenshot_ids)}")
        # if config_params:
        #     print(f"   配置参数: {list(config_params.keys())}")
        
        return snapshot_id
    
    def restore_snapshot(self, snapshot_id: str, target_runtime_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        恢复快照
        
        Returns:
            包含恢复信息和配置参数的字典
        """
        snapshot_dir = self.snapshots_dir / snapshot_id
        
        if not snapshot_dir.exists():
            print(f"❌ 快照不存在: {snapshot_id}")
            return {}
        
        # 读取元数据
        metadata_file = snapshot_dir / "metadata.json"
        if not metadata_file.exists():
            print(f"❌ 快照元数据文件不存在: {metadata_file}")
            return {}
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 确定目标目录
        if target_runtime_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target_path = self.runtime_dir.parent / f"{self.runtime_dir.name}_restored_from_{snapshot_id}_{timestamp}"
        else:
            target_path = Path(target_runtime_dir)
        
        target_path.mkdir(parents=True, exist_ok=True)
        
        # 1. 恢复state文件夹
        state_backup = snapshot_dir / "state"
        if state_backup.exists():
            target_state = target_path / "state"
            if target_state.exists():
                shutil.rmtree(target_state)
            shutil.copytree(state_backup, target_state)
            print(f"✅ 已恢复state文件夹到: {target_state}")
        
        # 2. 恢复cache/screens文件夹
        target_cache = target_path / "cache"
        target_screenshots = target_cache / "screens"
        target_screenshots.mkdir(parents=True, exist_ok=True)
        
        restored_count = 0
        for screenshot_id in metadata.get("screenshot_ids", []):
            # 尝试多种图片格式
            source_file = None
            target_file = None
            for ext in ['.png', '.jpg', '.jpeg', '.webp']:
                test_source = self.screenshots_dir / f"{screenshot_id}{ext}"
                if test_source.exists():
                    source_file = test_source
                    target_file = target_screenshots / f"{screenshot_id}{ext}"
                    break
            
            if source_file and target_file:
                shutil.copy2(source_file, target_file)
                restored_count += 1
        
        print(f"✅ 已恢复 {restored_count} 个截图到: {target_screenshots}")
        
        # 3. 创建display.json文件（如果不存在）
        target_display = target_path / "display.json"
        if not target_display.exists():
            default_display = {
                "restored_from_snapshot": snapshot_id,
                "restore_time": datetime.now().isoformat(),
                "operations": {}
            }
            with open(target_display, 'w', encoding='utf-8') as f:
                json.dump(default_display, f, indent=2, ensure_ascii=False)
            print(f"✅ 已创建display.json文件")
        
        # 保存恢复信息
        restore_info = {
            "restored_from": snapshot_id,
            "restore_time": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "target_directory": str(target_path),
            "screenshots_restored": restored_count
        }
        
        restore_file = target_path / "restore_info.json"
        with open(restore_file, 'w', encoding='utf-8') as f:
            json.dump(restore_info, f, indent=2, ensure_ascii=False)
        
        print(f"🎉 快照恢复成功！")
        print(f"   目标目录: {target_path}")
        print(f"   恢复的截图: {restored_count}")
        
        # 返回恢复信息和配置参数
        return {
            "restore_info": restore_info,
            "target_directory": str(target_path),
            "config_params": metadata.get("config_params", {}),
            "snapshot_metadata": metadata
        }
    
    def restore_snapshot_and_create_globalstate(self, snapshot_id: str, target_runtime_dir: Optional[str] = None) -> tuple:
        """
        恢复快照并创建GlobalState对象
        
        Returns:
            (restore_result, global_state_path) 元组
            restore_result: 恢复结果字典
            global_state_path: 恢复后的全局状态路径，可直接用于创建NewGlobalState
        """
        # 先恢复快照
        restore_result = self.restore_snapshot(snapshot_id, target_runtime_dir)
        
        if not restore_result:
            return {}, None
        
        # 返回恢复结果和路径
        target_path = restore_result.get("target_directory")
        return restore_result, target_path
    
    def list_snapshots(self) -> list:
        """列出所有快照"""
        snapshots = []
        
        for snapshot_dir in self.snapshots_dir.iterdir():
            if snapshot_dir.is_dir():
                metadata_file = snapshot_dir / "metadata.json"
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        snapshots.append(metadata)
                    except:
                        continue
        
        # 按时间排序
        snapshots.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return snapshots
    
    def delete_snapshot(self, snapshot_id: str) -> bool:
        """删除快照"""
        snapshot_dir = self.snapshots_dir / snapshot_id
        
        if not snapshot_dir.exists():
            print(f"❌ 快照不存在: {snapshot_id}")
            return False
        
        try:
            shutil.rmtree(snapshot_dir)
            print(f"✅ 快照删除成功: {snapshot_id}")
            return True
        except Exception as e:
            print(f"❌ 删除快照失败: {e}")
            return False


# 使用示例
if __name__ == "__main__":
    # 使用当前运行时目录
    runtime_dir = "runtime/20250824_162344"
    
    # 创建快照系统
    snapshot_system = SimpleSnapshot(runtime_dir)
    
    # 模拟配置参数
    config_params = {
        "tools_dict": {"example": "config"},
        "platform": "darwin",
        "enable_search": True,
        "env_password": "password123"
    }
    
    # 创建快照
    snapshot_id = snapshot_system.create_snapshot("测试增强快照", "test", config_params)
    
    # 列出所有快照
    snapshots = snapshot_system.list_snapshots()
    print(f"\n📋 现有快照数量: {len(snapshots)}")
    
    # 恢复快照
    # restore_result = snapshot_system.restore_snapshot(snapshot_id)
    # print(f"恢复结果: {restore_result}") 