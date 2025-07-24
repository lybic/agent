# GUI Agent Unit Tests

This directory contains unit tests for the Manager and Worker modules in the GUI Agent S2 version.

## Test Contents

1. **Manager Module Tests** (`test_manager.py`):
   - `_generate_step_by_step_plan`: Tests high-level plan generation functionality
   - `_generate_dag`: Tests directed acyclic graph (DAG) generation functionality
   - `_topological_sort`: Tests DAG topological sorting functionality
   - `get_action_queue`: Tests action queue generation functionality

2. **Worker Module Tests** (`test_worker.py`):
   - `reset`: Tests Worker state reset functionality
   - `flush_messages`: Tests message history management functionality
   - `generate_next_action`: Tests action generation functionality
   - `clean_worker_generation_for_reflection`: Tests work output cleaning functionality

## Running Tests

### Running All Tests

```bash
cd <project root directory>
python -m gui_agents.unit_test.run_tests
```

### Running Specific Tests

```bash
cd <project root directory>
python -m gui_agents.unit_test.run_tests manager  # Run Manager tests
python -m gui_agents.unit_test.run_tests worker   # Run Worker tests
```
