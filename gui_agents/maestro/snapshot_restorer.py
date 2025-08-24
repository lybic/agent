#!/usr/bin/env python3
"""
快照恢复工具 - 恢复快照并创建GlobalState
"""

import os
import sys
from pathlib import Path
from typing import Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from gui_agents.maestro.simple_snapshot import SimpleSnapshot
from gui_agents.maestro.new_global_state import NewGlobalState


def restore_snapshot_and_create_globalstate(runtime_dir: str, snapshot_id: Optional[str] = None, target_dir: Optional[str] = None):
    """
    恢复快照并创建GlobalState
    
    Args:
        runtime_dir: 运行时目录路径
        snapshot_id: 快照ID，如果为None则列出所有快照供选择
        target_dir: 目标恢复目录，如果为None则自动生成
    """
    # 创建快照系统
    snapshot_system = SimpleSnapshot(runtime_dir)
    
    # 如果没有指定快照ID，列出所有快照供选择
    if snapshot_id is None:
        snapshots = snapshot_system.list_snapshots()
        if not snapshots:
            print("❌ 没有找到任何快照")
            return None, None
        
        print("📋 可用的快照:")
        for i, snapshot in enumerate(snapshots):
            print(f"  {i+1}. {snapshot['snapshot_id']}")
            print(f"     描述: {snapshot['description']}")
            print(f"     类型: {snapshot['type']}")
            print(f"     时间: {snapshot['timestamp']}")
            print()
        
        try:
            choice = int(input("请选择快照编号 (1-{}): ".format(len(snapshots)))) - 1
            if 0 <= choice < len(snapshots):
                snapshot_id = snapshots[choice]['snapshot_id']
            else:
                print("❌ 无效的选择")
                return None, None
        except (ValueError, KeyboardInterrupt):
            print("❌ 输入无效或取消操作")
            return None, None
    
    print(f"🔄 正在恢复快照: {snapshot_id}")
    
    # 恢复快照
    restore_result, target_path = snapshot_system.restore_snapshot_and_create_globalstate(
        str(snapshot_id), target_dir
    )
    
    if not restore_result or not target_path:
        print("❌ 快照恢复失败")
        return None, None
    
    print(f"✅ 快照恢复成功！")
    print(f"   目标目录: {target_path}")
    
    # 创建GlobalState对象
    try:
        # 构建路径
        state_dir = Path(target_path) / "state"
        cache_dir = Path(target_path) / "cache"
        screens_dir = cache_dir / "screens"
        display_path = Path(target_path) / "display.json"
        
        # 确保目录存在
        state_dir.mkdir(exist_ok=True)
        screens_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建GlobalState
        global_state = NewGlobalState(
            screenshot_dir=str(screens_dir),
            state_dir=str(state_dir),
            display_info_path=str(display_path)
        )
        
        print(f"🎉 GlobalState创建成功！")
        print(f"   截图目录: {screens_dir}")
        print(f"   状态目录: {state_dir}")
        print(f"   显示文件: {display_path}")
        
        # 显示配置参数
        config_params = restore_result.get("config_params", {})
        if config_params:
            print(f"\n📋 快照配置参数:")
            print(f"   平台: {config_params.get('platform', 'N/A')}")
            print(f"   后端: {config_params.get('backend', 'N/A')}")
            print(f"   最大步数: {config_params.get('max_steps', 'N/A')}")
            print(f"   搜索开关: {config_params.get('enable_search', 'N/A')}")
            print(f"   接管开关: {config_params.get('enable_takeover', 'N/A')}")
            print(f"   RAG开关: {config_params.get('enable_rag', 'N/A')}")
        
        return global_state, target_path
        
    except Exception as e:
        print(f"❌ 创建GlobalState失败: {e}")
        return None, target_path


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="快照恢复工具")
    parser.add_argument("runtime_dir", help="运行时目录路径")
    parser.add_argument("--snapshot", "-s", help="快照ID")
    parser.add_argument("--target", "-t", help="目标恢复目录")
    
    args = parser.parse_args()
    
    # 检查运行时目录是否存在
    if not Path(args.runtime_dir).exists():
        print(f"❌ 运行时目录不存在: {args.runtime_dir}")
        return
    
    # 恢复快照
    global_state, target_path = restore_snapshot_and_create_globalstate(
        args.runtime_dir, args.snapshot, args.target
    )
    
    if global_state:
        print(f"\n🎯 使用说明:")
        print(f"   1. GlobalState对象已创建，可以直接使用")
        print(f"   2. 恢复的目录: {target_path}")
        print(f"   3. 可以调用 global_state.get_task() 等方法读取信息")
        print(f"   4. 所有状态文件已恢复到: {target_path}/state/")
        print(f"   5. 截图已恢复到: {target_path}/cache/screens/")


if __name__ == "__main__":
    main() 