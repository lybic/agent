#!/usr/bin/env python3
"""调试runtime/20250824_183617任务"""

import json
import os
import sys
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from gui_agents.maestro.debug_system.main_debugger import create_debugger
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保在项目根目录运行此脚本")
    sys.exit(1)


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='调试指定的运行时任务和快照')
    parser.add_argument(
        '--runtime', '-r',
        default='runtime/20250824_183617',
        help='运行时目录路径 (默认: runtime/20250824_183617)'
    )
    parser.add_argument(
        '--snapshot', '-s',
        help='要调试的快照名称 (例如: snapshot_20250824_183624)'
    )
    parser.add_argument(
        '--list-only', '-l',
        action='store_true',
        help='仅列出可用快照，不启动调试'
    )
    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='启动交互式调试模式'
    )
    
    return parser.parse_args()


def main():
    """主调试函数"""
    args = parse_arguments()
    
    # 写死运行时路径和快照名称
    runtime_path = "runvmrun_20250826_010444/20250826_010445"
    snapshots_path = f"{runtime_path}/snapshots"
    target_snapshot = "snapshot_20250826_012616"
    
    print("=== 运行时任务调试器 ===")
    print(f"目标运行时: {runtime_path}")
    print(f"目标快照: {target_snapshot}")
    
    # 检查运行时目录是否存在
    if not Path(runtime_path).exists():
        print(f"❌ 运行时目录不存在: {runtime_path}")
        return
    
    # 创建调试器，指定正确的路径
    try:
        debugger = create_debugger(snapshot_dir=snapshots_path, state_dir=runtime_path)
        print("✅ 调试器创建成功")
    except Exception as e:
        print(f"❌ 创建调试器失败: {e}")
        return
    
    # 直接使用硬编码的快照名称，跳过扫描
    print(f"\n=== 使用硬编码快照: {target_snapshot} ===")
    
    # 显示快照的详细信息
    print(f"\n=== 分析快照: {target_snapshot} ===")
    try:
        debugger.show_snapshot_info(target_snapshot)
    except Exception as e:
        print(f"⚠️  显示快照信息失败: {e}")
    
    # # 调试Manager组件
    # print(f"\n=== 调试Manager组件 ===")
    # if debugger.debug_manager_from_snapshot(target_snapshot):
    #     print("✅ Manager组件调试成功")
    # else:
    #     print("❌ Manager组件调试失败")

    # 调试Worker组件
    print(f"\n=== 调试Worker组件 ===")
    if debugger.debug_worker_from_snapshot(target_snapshot):
        print("✅ Worker组件调试成功")
    else:
        print("❌ Worker组件调试失败")
        

    # 启动交互式调试模式
    if args.interactive:
        print(f"\n=== 启动交互式调试模式 ===")
        print("输入 'help' 查看可用命令")
        try:
            debugger.interactive_debug()
        except KeyboardInterrupt:
            print("\n\n调试会话被中断")
        except Exception as e:
            print(f"\n交互式调试出错: {e}")
    else:
        print(f"\n💡 使用 --interactive 或 -i 启动交互式调试模式")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    except Exception as e:
        print(f"\n程序执行出错: {e}")
        import traceback
        traceback.print_exc() 