# GUI Agent 单元测试

本目录包含对GUI Agent S2版本中Manager和Worker模块的单元测试。

## 测试内容

1. **Manager模块测试** (`test_manager.py`):
   - `_generate_step_by_step_plan`: 测试高级计划生成功能
   - `_generate_dag`: 测试有向无环图(DAG)生成功能
   - `_topological_sort`: 测试DAG拓扑排序功能
   - `get_action_queue`: 测试动作队列生成功能

2. **Worker模块测试** (`test_worker.py`):
   - `reset`: 测试Worker状态重置功能
   - `flush_messages`: 测试消息历史管理功能
   - `generate_next_action`: 测试动作生成功能
   - `clean_worker_generation_for_reflection`: 测试工作输出清理功能

## 运行测试

### 运行所有测试

```bash
cd <项目根目录>
python -m gui_agents.unit_test.run_tests
```

### 运行特定测试

```bash
cd <项目根目录>
python -m gui_agents.unit_test.run_tests manager  # 运行Manager测试
python -m gui_agents.unit_test.run_tests worker   # 运行Worker测试
```
