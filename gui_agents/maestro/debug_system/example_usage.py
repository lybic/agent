"""
调试系统使用示例
"""

from main_debugger import create_debugger


def main():
    """主函数 - 演示调试系统的使用"""
    
    # 创建调试器
    debugger = create_debugger()
    
    print("=== Agent调试系统 ===")
    print("这个系统允许你从快照恢复状态并调试各个组件")
    
    # 列出可用快照
    snapshots = debugger.list_snapshots()
    if snapshots:
        print(f"\n发现 {len(snapshots)} 个快照:")
        for snapshot in snapshots:
            print(f"  - {snapshot}")
        
        # 显示第一个快照的信息
        first_snapshot = snapshots[0]
        debugger.show_snapshot_info(first_snapshot)
        debugger.debug_worker_from_snapshot(first_snapshot)
        
    else:
        print("没有可用的快照")
        print("请先运行系统创建一些快照")
    
    # 启动交互式调试模式
    print("\n启动交互式调试模式...")
    debugger.interactive_debug()


if __name__ == "__main__":
    main() 