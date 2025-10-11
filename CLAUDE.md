# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
```bash
# Create virtual environment using UV
make create-venv

# Install UV package manager
make install-uv

# Install package in development mode
uv pip install -e .
```

### Building and Publishing
```bash
# Build the Python package
make build

# Publish to PyPI
make publish

# Clean build artifacts
make clean
```

### Testing
```bash
# Run tests using pytest (available as dev dependency)
pytest

# Run specific test file
pytest gui_agents/unit_test/test_worker.py

# Run tests with coverage (if coverage is installed)
pytest --cov=gui_agents
```

### Code Quality
```bash
# The project uses UV for dependency management
# Check for dependency issues
uv check

# Update dependencies
uv sync
```

## Architecture Overview

### Core Components

**Lybic GUI Agent** is an open-source framework for creating intelligent computer-use agents that can understand and interact with graphical user interfaces across multiple platforms.

#### Main Architecture

1. **Service Layer** (`gui_agents/service/`)
   - High-level service interface (`AgentService`) - recommended for most users
   - Configuration management (`ServiceConfig`)
   - Task execution abstractions (`TaskRequest`, `TaskResult`)

2. **Agent Core** (`gui_agents/agents/`)
   - `AgentS2`: Full-featured agent with hierarchical planning and DAG modeling
   - `AgentSFast`: Streamlined version for faster execution
   - `HardwareInterface`: Hardware abstraction layer for different backends
   - `GlobalState`: Centralized state management

3. **Backend Systems** (`gui_agents/agents/Backend/`)
   - `LybicBackend`: Cloud-based sandbox environment (works in headless mode)
   - `PyAutoGUIBackend`: Local GUI automation (requires display)
   - `PyAutoGUIVMwareBackend`: VMware virtual machine control
   - `ADBBackend`: Android device control

4. **Tool System** (`gui_agents/tools/`)
   - Modular tool architecture with configurable LLM providers
   - Support for multiple AI providers (OpenAI, Anthropic, Google, xAI, etc.)
   - Tool configuration via `tools_config.json`

#### Agent Modes

- **Normal Mode**: Full agent with detailed reasoning, planning, and memory
- **Fast Mode**: Direct action generation with reduced overhead

### Key Design Patterns

1. **Multi-Agent Architecture**: Uses Manager-Worker pattern for task decomposition
2. **Grounding System**: Converts abstract plans to concrete UI actions
3. **Memory Management**: Episodic and narrative memory for learning
4. **Backend Abstraction**: Pluggable backend system for different environments

## Development Guidelines

### Adding New Tools

1. Define tool in `gui_agents/tools/tools.py`
2. Add configuration to `gui_agents/tools/tools_config.json`
3. Update tool documentation in `gui_agents/tools/model.md`

### Backend Development

1. Implement backend interface in `gui_agents/agents/Backend/`
2. Inherit from base `Backend` class
3. Add backend-specific configuration options
4. Test with `HardwareInterface`

### Agent Customization

1. Extend `AgentS2` or `AgentSFast` classes
2. Override methods: `predict()`, `reset()`, `update_memory()`
3. Configure via `tools_config` parameter

## Environment Configuration

### Required Environment Variables

Configure in `gui_agents/.env`:

```bash
# Lybic Cloud Sandbox
LYBIC_API_KEY=your_lybic_api_key
LYBIC_ORG_ID=your_lybic_org_id

# LLM Provider Keys
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key

# Search Provider (optional)
ARK_API_KEY=your_ark_api_key
```

### Tool Configuration

Copy and customize tool configuration:

```bash
# For English models
cp gui_agents/tools/tools_config_en.json gui_agents/tools/tools_config.json

# For Chinese models
cp gui_agents/tools/tools_config_cn.json gui_agents/tools/tools_config.json
```

## Usage Patterns

### CLI Application
```bash
# Interactive mode with Lybic backend
python gui_agents/cli_app.py --backend lybic

# Fast mode with single query
python gui_agents/cli_app.py --backend pyautogui --mode fast --query "Open calculator"

# Enable user takeover
python gui_agents/cli_app.py --backend lybic --enable-takeover
```

### Service Integration
```python
from gui_agents import AgentService

service = AgentService()
result = service.execute_task("Take a screenshot")
print(f"Task completed: {result.status}")
```

## Platform Support

- **Linux**: Full support with PyAutoGUI and Lybic backends
- **macOS**: Supported via PyAutoGUI and Lybic backends
- **Windows**: Native support with all backends
- **Android**: Via ADB backend (requires Lybic Android Sandbox)

## Testing Strategy

- Unit tests in `gui_agents/unit_test/`
- Integration tests in `tests/`
- Platform-specific tests for each backend
- Knowledge base tests for memory systems

## Performance Considerations

- Use `--mode fast` for quicker execution with reduced reasoning
- Configure appropriate `--max-steps` for task complexity
- Optimize tool selection in `tools_config.json` for cost/quality balance
- Consider environment compatibility when choosing backends

## Memory and Knowledge Base

- Local knowledge base storage in `kb_s2/` directory
- Episodic memory for subtask learning
- Narrative memory for task-level reflection
- Persistent state across agent sessions
