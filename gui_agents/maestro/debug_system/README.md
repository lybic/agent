# Agent调试系统

这是一个简洁而强大的调试系统，支持从快照恢复状态并调试所有核心组件。

## 核心功能

### 1. 快照恢复
- 从快照文件恢复 `global_state`
- 提取组件的配置参数
- 重建调试环境

### 2. 组件调试
- **Worker调试**: 单步执行 `process_subtask_and_create_command()`
- **Evaluator调试**: 调试评估逻辑
- **Manager调试**: 调试管理逻辑

### 3. 参数重建
从快照中自动重建各组件的参数：

```python
# Worker参数
worker_params = {
    "tools_dict": tools_dict,
    "global_state": global_state,
    "platform": platform,
    "enable_search": enable_search,
    "client_password": client_password
}

# Evaluator参数
evaluator_params = {
    "global_state": global_state,
    "tools_dict": tools_dict
}

# Manager参数
manager_params = {
    "tools_dict": tools_dict,
    "global_state": global_state,
    "local_kb_path": local_kb_path,
    "platform": platform,
    "enable_search": enable_search
}
```

## 使用方法

### 基本使用

```python
from debug_system.main_debugger import create_debugger

# 创建调试器
debugger = create_debugger()

# 列出可用快照
snapshots = debugger.list_snapshots()

# 从快照调试Worker
debugger.debug_worker_from_snapshot("snapshot_001")

# 单步执行Worker
debugger.step_worker_execution()

# 获取当前状态
state = debugger.get_current_debug_state()
```

### 交互式调试

```python
# 启动交互式调试模式
debugger.interactive_debug()
```

可用命令：
- `list` - 列出所有快照
- `info <snapshot_id>` - 显示快照信息
- `debug_worker <snapshot_id>` - 调试Worker
- `debug_evaluator <snapshot_id>` - 调试Evaluator
- `debug_manager <snapshot_id>` - 调试Manager
- `step_worker` - 单步执行Worker
- `state` - 显示当前状态
- `reset` - 重置调试会话
- `quit` - 退出调试模式

## 调试流程

1. **加载快照**: `debugger.load_snapshot(snapshot_id)`
2. **恢复状态**: 自动恢复 `global_state` 和配置参数
3. **重建组件**: 使用恢复的参数创建组件实例
4. **单步调试**: 调用组件的核心方法进行调试
5. **状态观察**: 观察组件状态和全局状态的变化

## 系统架构

```
MainDebugger
├── SnapshotDebugger (快照恢复)
│   ├── load_snapshot()
│   ├── get_worker_params()
│   ├── get_evaluator_params()
│   └── get_manager_params()
└── ComponentDebugger (组件调试)
    ├── debug_worker()
    ├── debug_evaluator()
    ├── debug_manager()
    └── step_worker()
```

## 优势

- **简洁**: 设计简单，易于理解和使用
- **完整**: 支持所有核心组件的调试
- **灵活**: 可以从任何快照点重新开始调试
- **实用**: 直接调用组件的核心方法进行调试
- **状态完整**: 保持完整的运行时状态和配置

这个调试系统完美地实现了你提到的核心思想：从快照恢复状态，重建组件，然后进行单步调试！ 