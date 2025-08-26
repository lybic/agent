#!/usr/bin/env python3
"""
快照恢复工具 - 恢复快照并创建GlobalState
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from gui_agents.maestro.simple_snapshot import SimpleSnapshot
from gui_agents.maestro.new_global_state import NewGlobalState
from gui_agents.maestro.controller.main_controller import MainController
from desktop_env.desktop_env import DesktopEnv


def _build_env_from_config(env_config: Dict[str, Any]) -> Optional[DesktopEnv]:
    """根据快照中的 env 配置重建 DesktopEnv。失败时返回 None。"""
    try:
        if not env_config or not env_config.get("present"):
            return None

        provider_name = env_config.get("provider_name", "vmware")
        path_to_vm = env_config.get("path_to_vm")
        action_space = env_config.get("action_space", "pyautogui")
        headless = bool(env_config.get("headless", False))
        require_a11y_tree = bool(env_config.get("require_a11y_tree", False))
        os_type_value = env_config.get("os_type") or os.getenv("USE_PRECREATE_VM", "Windows")

        if not path_to_vm:
            # 缺少必要的 VM 路径时无法构建
            return None

        env = DesktopEnv(
            provider_name=provider_name,
            path_to_vm=path_to_vm,
            action_space=action_space,
            headless=headless,
            require_a11y_tree=require_a11y_tree,
            os_type=os_type_value,
        )
        # 若需要，调用 reset 以确保内部状态就绪
        try:
            env.reset()
        except Exception:
            pass
        return env
    except Exception:
        return None


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
            return None, None, {}
        
        print("📋 可用的快照:")
        for i, snapshot in enumerate(snapshots):
            print(f"  {i+1}. {snapshot['snapshot_id']}")
            print(f"     描述: {snapshot['description']}")
            print(f"     类型: {snapshot['type']}")
            print(f"     时间: {snapshot['timestamp']}")
            print()

    
    print(f"🔄 正在恢复快照: {snapshot_id}")
    
    # 恢复快照
    restore_result = snapshot_system.restore_snapshot(
        str(snapshot_id), target_dir
    )

    target_path = restore_result.get('target_directory')
    
    if not restore_result or not target_path:
        print("❌ 快照恢复失败")
        return None, None, {}
    
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
        
        return global_state, target_path, config_params
        
    except Exception as e:
        print(f"❌ 创建GlobalState失败: {e}")
        return None, target_path, {}


def restore_maincontroller_from_globalstate(runtime_dir: str, snapshot_id: Optional[str] = None, target_dir: Optional[str] = None) -> Optional[Tuple[MainController, str, Dict[str, Any]]]:
    """
    恢复快照 -> 构建GlobalState -> 构建MainController（跳过初始化），并返回控制器、恢复目录与配置
    """
    global_state, target_path, config_params = restore_snapshot_and_create_globalstate(runtime_dir, snapshot_id, target_dir)
    if global_state is None:
        return None

    # 从配置参数中提取控制器相关设置（提供合理默认值）
    platform_value = config_params.get("platform", sys.platform)
    backend_value = config_params.get("backend", "pyautogui")
    enable_search_value = bool(config_params.get("enable_search", False))
    enable_takeover_value = bool(config_params.get("enable_takeover", False))
    enable_rag_value = bool(config_params.get("enable_rag", False))
    max_steps_value = int(config_params.get("max_steps", 50))
    env_password_value = config_params.get("env_password", "")

    # 保护性检查：target_path 需要可用
    if not target_path:
        print("❌ 无法确定恢复目录 target_path")
        return None

    # 恢复环境信息：优先使用快照中的 env 配置
    env: Optional[DesktopEnv] = None
    try:
        env_config = config_params.get("env") or {}
        env = _build_env_from_config(env_config)
    except Exception as e:
        print(f"⚠️ 环境恢复失败（将继续无环境运行）: {e}")
        env = None

    controller = MainController(
        platform=platform_value,
        enable_takeover=enable_takeover_value,
        enable_search=enable_search_value,
        enable_rag=enable_rag_value,
        backend=backend_value,
        user_query=(global_state.get_task().objective if hasattr(global_state, 'get_task') else ""),
        max_steps=max_steps_value,
        env=env,
        env_password=env_password_value,
        log_dir=str(Path(target_path)),
        datetime_str=Path(target_path).name,
        enable_snapshots=True,
        global_state=global_state,
        initialize_controller=False
    )

    print("✅ MainController 从快照恢复完成，可直接执行主循环")
    return controller, target_path, config_params



def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="快照恢复工具")
    parser.add_argument("runtime_dir", help="运行时目录路径")
    parser.add_argument("--snapshot", "-s", help="快照ID")
    parser.add_argument("--target", "-t", help="目标恢复目录")
    parser.add_argument("--run", action="store_true", help="恢复后立即运行主循环")
    
    args = parser.parse_args()
    
    # 检查运行时目录是否存在
    if not Path(args.runtime_dir).exists():
        print(f"❌ 运行时目录不存在: {args.runtime_dir}")
        return
    
    if args.run:
        result = restore_maincontroller_from_globalstate(args.runtime_dir, args.snapshot, args.target)
        if result is not None:
            controller, target_path, _ = result
            controller.execute_main_loop()
        return
    
    # 仅恢复快照并创建GlobalState
    global_state, target_path, _ = restore_snapshot_and_create_globalstate(
        args.runtime_dir, args.snapshot, args.target
    )
    
    if global_state:
        print(f"\n🎯 使用说明:")
        print(f"   1. GlobalState对象已创建，可以直接使用")
        print(f"   2. 恢复的目录: {target_path}")
        print(f"   3. 可以调用 global_state.get_task() 等方法读取信息")
        print(f"   4. 所有状态文件已恢复到: {target_path}/state/")
        print(f"   5. 截图已恢复到: {target_path}/cache/screens/")
        print(f"   6. 调用 restore_maincontroller_from_globalstate(...).execute_main_loop() 可继续执行")


if __name__ == "__main__":
    main() 