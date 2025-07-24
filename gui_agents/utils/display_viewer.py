#!/usr/bin/env python
"""
Display Viewer - Used to display operation records in display.json file in chronological order

Usage:
    python -m lybicguiagents.gui_agents.utils.display_viewer --file /path/to/display.json [--output text|json] [--filter module1,module2]
"""

import os
import sys
import json
import argparse
import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Add color constants
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

# Assign colors to different modules
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
    Load display.json file
    
    Args:
        file_path: Path to display.json file
        
    Returns:
        Parsed JSON data
    """
    try:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except UnicodeDecodeError:
            print(
                f"Warning: Failed to decode '{file_path}' with utf-8, retrying with GB2312..."
            )
            with open(file_path, 'r', encoding='gb2312') as f:
                return json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{file_path}' does not exist")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: File '{file_path}' is not a valid JSON format")
        sys.exit(1)
    except Exception as e:
        print(f"Error: An error occurred while reading file '{file_path}': {e}")
        sys.exit(1)


def flatten_operations(data: Dict) -> List[Dict]:
    """
    Flatten all module operation records into a time-sorted list
    
    Args:
        data: display.json data
        
    Returns:
        List of operation records sorted by time
    """
    all_operations = []

    if "operations" not in data:
        return all_operations

    for module, operations in data["operations"].items():
        for op in operations:
            # Add module information
            op["module"] = module
            all_operations.append(op)

    # Sort by timestamp
    all_operations.sort(key=lambda x: x.get("timestamp", 0))

    return all_operations


def format_timestamp(timestamp: float) -> str:
    """
    Format timestamp into readable datetime
    
    Args:
        timestamp: UNIX timestamp
        
    Returns:
        Formatted datetime string
    """
    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def format_duration(duration: float) -> str:
    """
    Format duration
    
    Args:
        duration: Duration (seconds)
        
    Returns:
        Formatted duration string
    """
    if duration < 0.001:
        return f"{duration * 1000000:.2f}μs"
    elif duration < 1:
        return f"{duration * 1000:.2f}ms"
    else:
        return f"{duration:.2f}s"


def format_tokens(tokens: List[int]) -> str:
    """
    Format tokens information
    
    Args:
        tokens: [input tokens, output tokens, total tokens]
        
    Returns:
        Formatted tokens string
    """
    if not tokens or len(tokens) < 3:
        return "N/A"

    return f"in:{tokens[0]} out:{tokens[1]} total:{tokens[2]}"


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Truncate text, add ellipsis when exceeding maximum length
    
    Args:
        text: Original text
        max_length: Maximum length
        
    Returns:
        Truncated text
    """
    if not text:
        return ""

    if isinstance(text, (dict, list)):
        text = str(text)

    if len(text) <= max_length:
        return text

    return text[:max_length - 3] + "..."


def display_text_format(operations: List[Dict],
                        filter_modules: Optional[List[str]] = None) -> None:
    """
    Display operation records in text format
    
    Args:
        operations: List of operation records
        filter_modules: List of modules to filter
    """
    for i, op in enumerate(operations):
        # Skip modules that don't match the filter if a filter is specified
        if filter_modules and op["module"] not in filter_modules:
            continue

        module = op["module"]
        operation = op.get("operation", "unknown")
        timestamp = format_timestamp(op.get("timestamp", 0))

        # Use the color corresponding to the module
        color = MODULE_COLORS.get(module, COLORS["reset"])

        # Output basic information
        print(
            f"{i+1:3d} | {timestamp} | {color}{module:10}{COLORS['reset']} | {COLORS['bold']}{operation}{COLORS['reset']}"
        )

        # Output detailed information
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


def display_json_format(operations: List[Dict],
                        filter_modules: Optional[List[str]] = None) -> None:
    """
    Display operation records in JSON format
    
    Args:
        operations: List of operation records
        filter_modules: List of modules to filter
    """
    # Filter operations if modules are specified
    if filter_modules:
        filtered_ops = [
            op for op in operations if op["module"] in filter_modules
        ]
    else:
        filtered_ops = operations

    # Output as formatted JSON
    print(json.dumps(filtered_ops, indent=2, ensure_ascii=False))


def find_latest_display_json() -> Optional[str]:
    """
    Find the latest display.json file
    
    Returns:
        Path to the latest display.json file, or None if not found
    """
    # Look for the runtime folder in the current directory
    runtime_dir = Path("runtime")
    if not runtime_dir.exists() or not runtime_dir.is_dir():
        # Try looking in the parent directory
        parent_runtime = Path("..") / "runtime"
        if parent_runtime.exists() and parent_runtime.is_dir():
            runtime_dir = parent_runtime
        else:
            return None

    # Find all timestamp folders
    timestamp_dirs = [d for d in runtime_dir.iterdir() if d.is_dir()]
    if not timestamp_dirs:
        return None

    # Sort by folder name (timestamp) and take the latest
    latest_dir = sorted(timestamp_dirs)[-1]
    display_file = latest_dir / "display.json"

    if display_file.exists():
        return str(display_file)

    return None


def main():
    parser = argparse.ArgumentParser(
        description=
        "Display operation records in display.json file in chronological order")
    parser.add_argument("--file", help="Path to display.json file")
    parser.add_argument("--output",
                        choices=["text", "json"],
                        default="text",
                        help="Output format (default: text)")
    parser.add_argument(
        "--filter",
        help="Modules to filter, separated by commas (e.g., manager,worker)")

    args = parser.parse_args()

    # If no file is specified, try to find the latest display.json
    file_path = args.file
    if not file_path:
        file_path = find_latest_display_json()
        if not file_path:
            print(
                "Error: Cannot find display.json file, please specify file path using --file parameter"
            )
            sys.exit(1)
        print(f"Using the latest display.json file: {file_path}")

    # Load data
    data = load_display_json(file_path)

    # Flatten and sort operations
    operations = flatten_operations(data)

    # Handle module filtering
    filter_modules = None
    if args.filter:
        filter_modules = [module.strip() for module in args.filter.split(",")]

    # Display based on output format
    if args.output == "json":
        display_json_format(operations, filter_modules)
    else:
        display_text_format(operations, filter_modules)


if __name__ == "__main__":
    """
    python gui_agents/s2/utils/display_viewer.py --file /Users/haoguangfu/Downloads/深维智能/客户方案/gui-agent/lybicguiagents/runtime/20250718_190307/display.json
    """
    main()
