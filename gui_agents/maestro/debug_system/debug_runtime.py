#!/usr/bin/env python3
"""极简调试函数：避免层层嵌套与多余错误处理"""
from typing import Optional

from gui_agents.maestro.debug_system.main_debugger import MainDebugger


def run_debug(runtime_path: str, snapshot_id: str, component: str = "manager") -> None:
    debugger = MainDebugger(
        runtime_path=runtime_path,
        snapshot_id=snapshot_id,
    )

    if component == "manager":
        debugger.debug_manager()
    elif component == "worker":
        debugger.debug_worker()
    elif component == "evaluator":
        debugger.debug_evaluator()
    else:
        raise ValueError(f"Unknown component: {component}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run snapshot/component debug easily from CLI")
    parser.add_argument(
        "--runtime",
        default="runtime/20250826_141730",
        help="Runtime directory path (default: runtime/20250826_141730)",
    )
    parser.add_argument(
        "--snapshot",
        default="snapshot_20250826_141736",
        help="Snapshot id/name (default: snapshot_20250826_141736)",
    )
    parser.add_argument(
        "--component",
        choices=["manager", "worker", "evaluator"],
        default="manager",
        help="Which component to debug (default: manager)",
    )

    # 写死运行时路径和快照名称
    runtime_path = "runtime/20250826_141730"
    snapshot_id = "snapshot_20250826_141736"
    component = "manager"
    # args = parser.parse_args()
    run_debug(
        runtime_path=runtime_path, 
        snapshot_id=snapshot_id, 
        component=component
    ) 