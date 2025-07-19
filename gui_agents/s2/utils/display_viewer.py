#!/usr/bin/env python
"""
Display Viewer - 用于按时间顺序展示 display.json 文件中的操作记录

使用方法:
    python -m lybicguiagents.gui_agents.s2.utils.display_viewer --file /path/to/display.json [--output text|json] [--filter module1,module2]
"""

import os
import sys
import json
import argparse
import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# 添加颜色常量
COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "bg_red": "\033[41m",
    "bg_green": "\033[42m",
    "bg_yellow": "\033[43m",
    "bg_blue": "\033[44m",
    "bg_magenta": "\033[45m",
    "bg_cyan": "\033[46m",
}

# 为不同模块分配颜色
MODULE_COLORS = {
    "manager": COLORS["green"],
    "worker": COLORS["blue"],
    "agent": COLORS["magenta"],
    "grounding": COLORS["cyan"],
    "hardware": COLORS["yellow"],
    "knowledge": COLORS["red"],
    "other": COLORS["white"]
}

def load_display_json(file_path: str) -> Dict:
    """
    加载 display.json 文件
    
    Args:
        file_path: display.json 文件路径
        
    Returns:
        解析后的 JSON 数据
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"错误: 文件 '{file_path}' 不存在")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"错误: 文件 '{file_path}' 不是有效的 JSON 格式")
        sys.exit(1)
    except Exception as e:
        print(f"错误: 读取文件 '{file_path}' 时出错: {e}")
        sys.exit(1)

def flatten_operations(data: Dict) -> List[Dict]:
    """
    将所有模块的操作记录展平为一个按时间排序的列表
    
    Args:
        data: display.json 的数据
        
    Returns:
        按时间排序的操作记录列表
    """
    all_operations = []
    
    if "operations" not in data:
        return all_operations
        
    for module, operations in data["operations"].items():
        for op in operations:
            # 添加模块信息
            op["module"] = module
            all_operations.append(op)
    
    # 按时间戳排序
    all_operations.sort(key=lambda x: x.get("timestamp", 0))
    
    return all_operations

def format_timestamp(timestamp: float) -> str:
    """
    将时间戳格式化为可读的日期时间
    
    Args:
        timestamp: UNIX 时间戳
        
    Returns:
        格式化的日期时间字符串
    """
    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def format_duration(duration: float) -> str:
    """
    格式化持续时间
    
    Args:
        duration: 持续时间（秒）
        
    Returns:
        格式化的持续时间字符串
    """
    if duration < 0.001:
        return f"{duration * 1000000:.2f}μs"
    elif duration < 1:
        return f"{duration * 1000:.2f}ms"
    else:
        return f"{duration:.2f}s"

def format_tokens(tokens: List[int]) -> str:
    """
    格式化 tokens 信息
    
    Args:
        tokens: [输入tokens, 输出tokens, 总tokens]
        
    Returns:
        格式化的 tokens 字符串
    """
    if not tokens or len(tokens) < 3:
        return "N/A"
        
    return f"in:{tokens[0]} out:{tokens[1]} total:{tokens[2]}"

def truncate_text(text: str, max_length: int = 100) -> str:
    """
    截断文本，超过最大长度时添加省略号
    
    Args:
        text: 原始文本
        max_length: 最大长度
        
    Returns:
        截断后的文本
    """
    if not text:
        return ""
        
    if isinstance(text, (dict, list)):
        text = str(text)
        
    if len(text) <= max_length:
        return text
        
    return text[:max_length - 3] + "..."

def display_text_format(operations: List[Dict], filter_modules: Optional[List[str]] = None) -> None:
    """
    以文本格式显示操作记录
    
    Args:
        operations: 操作记录列表
        filter_modules: 要筛选的模块列表
    """
    for i, op in enumerate(operations):
        # 如果指定了模块过滤，则跳过不匹配的模块
        if filter_modules and op["module"] not in filter_modules:
            continue
            
        module = op["module"]
        operation = op.get("operation", "unknown")
        timestamp = format_timestamp(op.get("timestamp", 0))
        
        # 使用模块对应的颜色
        color = MODULE_COLORS.get(module, COLORS["reset"])
        
        # 输出基本信息
        print(f"{i+1:3d} | {timestamp} | {color}{module:10}{COLORS['reset']} | {COLORS['bold']}{operation}{COLORS['reset']}")
        
        # 输出详细信息
        if "duration" in op:
            print(f"     └─ Duration: {format_duration(op['duration'])}")
            
        if "tokens" in op:
            print(f"     └─ Tokens: {format_tokens(op['tokens'])}")
            
        if "cost" in op:
            print(f"     └─ Cost: {op['cost']}")
            
        if "content" in op:
            content = truncate_text(op["content"])
            print(f"     └─ Content: {content}")
            
        if "status" in op:
            print(f"     └─ Status: {op['status']}")
            
        print()

def display_json_format(operations: List[Dict], filter_modules: Optional[List[str]] = None) -> None:
    """
    以 JSON 格式显示操作记录
    
    Args:
        operations: 操作记录列表
        filter_modules: 要筛选的模块列表
    """
    # 如果指定了模块过滤，则筛选操作
    if filter_modules:
        filtered_ops = [op for op in operations if op["module"] in filter_modules]
    else:
        filtered_ops = operations
        
    # 输出为格式化的 JSON
    print(json.dumps(filtered_ops, indent=2, ensure_ascii=False))

def find_latest_display_json() -> Optional[str]:
    """
    查找最新的 display.json 文件
    
    Returns:
        最新的 display.json 文件路径，如果找不到则返回 None
    """
    # 查找当前目录下的 runtime 文件夹
    runtime_dir = Path("runtime")
    if not runtime_dir.exists() or not runtime_dir.is_dir():
        # 尝试查找上级目录
        parent_runtime = Path("..") / "runtime"
        if parent_runtime.exists() and parent_runtime.is_dir():
            runtime_dir = parent_runtime
        else:
            return None
            
    # 查找所有时间戳文件夹
    timestamp_dirs = [d for d in runtime_dir.iterdir() if d.is_dir()]
    if not timestamp_dirs:
        return None
        
    # 按照文件夹名称（时间戳）排序，取最新的
    latest_dir = sorted(timestamp_dirs)[-1]
    display_file = latest_dir / "display.json"
    
    if display_file.exists():
        return str(display_file)
        
    return None

def main():
    parser = argparse.ArgumentParser(description="按时间顺序展示 display.json 文件中的操作记录")
    parser.add_argument("--file", help="display.json 文件路径")
    parser.add_argument("--output", choices=["text", "json"], default="text", help="输出格式 (默认: text)")
    parser.add_argument("--filter", help="要筛选的模块，用逗号分隔 (例如: manager,worker)")
    
    args = parser.parse_args()
    
    # 如果没有指定文件，则尝试查找最新的 display.json
    file_path = args.file
    if not file_path:
        file_path = find_latest_display_json()
        if not file_path:
            print("错误: 找不到 display.json 文件，请使用 --file 参数指定文件路径")
            sys.exit(1)
        print(f"使用最新的 display.json 文件: {file_path}")
    
    # 加载数据
    data = load_display_json(file_path)
    
    # 展平并排序操作
    operations = flatten_operations(data)
    
    # 处理模块过滤
    filter_modules = None
    if args.filter:
        filter_modules = [module.strip() for module in args.filter.split(",")]
    
    # 根据输出格式显示
    if args.output == "json":
        display_json_format(operations, filter_modules)
    else:
        display_text_format(operations, filter_modules)

if __name__ == "__main__":
    """
    python gui_agents/s2/utils/display_viewer.py --file /Users/haoguangfu/Downloads/深维智能/客户方案/gui-agent/lybicguiagents/runtime/20250718_190307/display.json
    """
    main() 