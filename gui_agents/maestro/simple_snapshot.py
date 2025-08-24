import os
import shutil
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


class SimpleSnapshot:
    """简单的快照系统 - 只复制state文件夹和记录截图ID"""
    
    def __init__(self, runtime_dir: str):
        self.runtime_dir = Path(runtime_dir)
        self.snapshots_dir = self.runtime_dir / "snapshots"
        self.state_dir = self.runtime_dir / "state"
        self.screenshots_dir = self.runtime_dir / "cache" / "screens"  # 修复：使用正确的截图目录
        
        # 确保快照目录存在
        self.snapshots_dir.mkdir(exist_ok=True)
    
    def create_snapshot(self, description: str = "", snapshot_type: str = "manual") -> str:
        """创建快照"""
        # 生成快照ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_id = f"snapshot_{timestamp}"
        
        # 创建快照目录
        snapshot_dir = self.snapshots_dir / snapshot_id
        snapshot_dir.mkdir(exist_ok=True)
        
        # 1. 复制整个state文件夹
        if self.state_dir.exists():
            state_backup = snapshot_dir / "state"
            shutil.copytree(self.state_dir, state_backup)
            print(f"✅ 已复制state文件夹到: {state_backup}")
        
        # 2. 获取当前截图ID列表 - 修复：从cache/screens目录获取
        screenshot_ids = []
        if self.screenshots_dir.exists():
            for screenshot_file in self.screenshots_dir.glob("*.png"):
                screenshot_ids.append(screenshot_file.stem)
        
        # 3. 记录快照元数据
        metadata = {
            "snapshot_id": snapshot_id,
            "timestamp": timestamp,
            "description": description,
            "type": snapshot_type,
            "screenshot_ids": screenshot_ids,
            "state_folder_copied": True
        }
        
        # 保存元数据
        metadata_file = snapshot_dir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        print(f"🎯 快照创建成功: {snapshot_id}")
        print(f"   描述: {description}")
        print(f"   截图数量: {len(screenshot_ids)}")
        
        return snapshot_id
    
    def restore_snapshot(self, snapshot_id: str, target_runtime_dir: Optional[str] = None) -> bool:
        """恢复快照"""
        snapshot_dir = self.snapshots_dir / snapshot_id
        
        if not snapshot_dir.exists():
            print(f"❌ 快照不存在: {snapshot_id}")
            return False
        
        # 读取元数据
        metadata_file = snapshot_dir / "metadata.json"
        if not metadata_file.exists():
            print(f"❌ 快照元数据文件不存在: {metadata_file}")
            return False
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 确定目标目录
        if target_runtime_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target_path = self.runtime_dir.parent / f"{self.runtime_dir.name}_restored_from_{snapshot_id}_{timestamp}"
        else:
            target_path = Path(target_runtime_dir)
        
        target_path.mkdir(exist_ok=True)
        
        # 恢复state文件夹
        state_backup = snapshot_dir / "state"
        if state_backup.exists():
            target_state = target_path / "state"
            if target_state.exists():
                shutil.rmtree(target_state)
            shutil.copytree(state_backup, target_state)
            print(f"✅ 已恢复state文件夹到: {target_state}")
        
        # 恢复截图（从原目录复制）- 修复：复制到cache/screens目录
        target_screenshots = target_path / "cache" / "screens"
        target_screenshots.mkdir(parents=True, exist_ok=True)
        
        restored_count = 0
        for screenshot_id in metadata.get("screenshot_ids", []):
            source_file = self.screenshots_dir / f"{screenshot_id}.png"
            if source_file.exists():
                target_file = target_screenshots / f"{screenshot_id}.png"
                shutil.copy2(source_file, target_file)
                restored_count += 1
        
        print(f"✅ 已恢复 {restored_count} 个截图到: {target_screenshots}")
        
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
        
        return True
    
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
    
    # 创建快照
    snapshot_id = snapshot_system.create_snapshot("测试简单快照", "test")
    
    # 列出所有快照
    snapshots = snapshot_system.list_snapshots()
    print(f"\n📋 现有快照数量: {len(snapshots)}")
    
    # 恢复快照
    # snapshot_system.restore_snapshot(snapshot_id) 