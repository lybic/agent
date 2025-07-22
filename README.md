<h1 align="center">
  Lybic GUI Agent:
  <small>A Framework for Computer Use Agents</small>
</h1>

## 🥳 Updates
- [x] **2025/07/31**: Released v0.1.0 of [Lybic GUI Agent] library, with support for Windows, Mac, Linux and Lybic API!

## Table of Contents

1. [🛠️ Installation & Setup](#%EF%B8%8F-installation--setup) 
2. [🚀 Usage](#-usage)

## 🛠️ Installation & Setup

> ❗**Warning**❗: If you are on a Linux machine, creating a `conda` environment will interfere with `pyatspi`. As of now, there's no clean solution for this issue. Proceed through the installation without using `conda` or any virtual environment.

> ⚠️**Disclaimer**⚠️: To leverage the full potential of Lybic GUI Agent, we support multiple model providers including OpenAI, Anthropic, Gemini, and Doubao. For the best visual grounding performance, we recommend using UI-TARS models.

### Installation

You can use UV (a modern Python package manager) for installation:

```bash
# 1. Install UV if not already installed
pip install uv
# 2. Install the python 3.12
uv install python 3.12.11
# 3. Create a virtual environment
uv venv
# 4. Activate the virtual environment
source .venv/bin/activate
# 5. Install dependencies
uv pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
# 6. Install the package locally in development mode
uv pip install -e .
```

### API Key Configuration

The simplest way to configure API keys is to:

1. Copy `gui_agents/.env.example` to `gui_agents/.env`
2. Edit the `.env` file and add your API keys

```bash
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GEMINI_API_KEY=your_gemini_key
DOUBAO_API_KEY=your_doubao_key
```

### Tool Configuration

We provide two pre-configured tool settings:

- `tools_config_en.json`: Configured for English language models (Gemini, Exa)
- `tools_config_cn.json`: Configured for Chinese language models (Doubao, bocha)

The agent uses `tools_config.json` by default. You can:

- Copy either `tools_config_en.json` or `tools_config_cn.json` to `tools_config.json`
- Or create your own custom configuration

```bash
# For English models
cp gui_agents/tools/tools_config_en.json gui_agents/tools/tools_config.json

# For Chinese models
cp gui_agents/tools/tools_config_cn.json gui_agents/tools/tools_config.json
```

> ❗**Warning**❗: The agent will directly run python code to control your computer. Please use with care.

## 🚀 Usage

> **Note**: Our recommended configuration uses Claude 3.7 or Doubao 1.6 for reasoning and UI-TARS for visual grounding. You can customize the model configuration in the tools configuration files.

### CLI

Run Lybic GUI Agent with the command-line interface:

```sh
lybic_gui_agent
```

This will show a user query prompt where you can enter your instructions and interact with the agent.

### Python SDK

First, import the necessary modules:

```python
import pyautogui
import io
from lybicguiagents.gui_agents.agents.agent_s import AgentS2
from lybicguiagents.gui_agents.agents.hardware_interface import HardwareInterface
from lybicguiagents.gui_agents.agents.global_state import GlobalState
from lybicguiagents.gui_agents.agents.store.registry import Registry

# Load your environment variables
from dotenv import load_dotenv
load_dotenv()

# Detect current platform
import platform
current_platform = platform.system().lower()
```

Initialize the global state and agent:

```python
# Get screen dimensions
screen_width, screen_height = pyautogui.size()
scaled_width, scaled_height = screen_width, screen_height

# Create necessary directories
import os
import datetime
log_dir = "runtime"
datetime_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
timestamp_dir = os.path.join(log_dir, datetime_str)
cache_dir = os.path.join(timestamp_dir, "cache", "screens")
state_dir = os.path.join(timestamp_dir, "state")
os.makedirs(cache_dir, exist_ok=True)
os.makedirs(state_dir, exist_ok=True)

# Initialize global state
Registry.register(
    "GlobalStateStore",
    GlobalState(
        screenshot_dir=cache_dir,
        tu_path=os.path.join(state_dir, "tu.json"),
        search_query_path=os.path.join(state_dir, "search_query.json"),
        completed_subtasks_path=os.path.join(state_dir, "completed_subtasks.json"),
        failed_subtasks_path=os.path.join(state_dir, "failed_subtasks.json"),
        remaining_subtasks_path=os.path.join(state_dir, "remaining_subtasks.json"),
        termination_flag_path=os.path.join(state_dir, "termination_flag.json"),
        running_state_path=os.path.join(state_dir, "running_state.json"),
        display_info_path=os.path.join(timestamp_dir, "display.json"),
    )
)

# Initialize agent
agent = AgentS2(
    platform=current_platform,
    screen_size=[scaled_width, scaled_height]
)
```

Run the agent:

```python
# Hardware interface for interacting with the system
hwi = HardwareInterface(backend="pyautogui", platform=current_platform)

# Get the global state
global_state = Registry.get("GlobalStateStore")

# Set the user instruction
instruction = "Open Chrome and search for 'Lybic GUI Agent'"
global_state.set_Tu(instruction)

# Get screenshot
screenshot = hwi.dispatch(Screenshot())
screenshot = screenshot.resize((scaled_width, scaled_height), Image.LANCZOS)
global_state.set_screenshot(screenshot)
obs = global_state.get_obs_for_manager()

# Run the agent
info, action = agent.predict(instruction=instruction, observation=obs)

# Execute the action
hwi.dispatchDict(action[0])
```

### Knowledge Base

Lybic GUI Agent uses a knowledge base that continually updates during inference. The knowledge base is downloaded when initializing `AgentS2` and stored in the specified memory folder. You can configure the knowledge base location:

```python
agent = AgentS2(
    platform=current_platform,
    screen_size=[scaled_width, scaled_height],
    memory_root_path="/path/to/memory",
    memory_folder_name="kb_s2",
    kb_release_tag="v0.2.2"
)
```

### OSWorld

To deploy Lybic GUI Agent in OSWorld, follow the [OSWorld Deployment instructions](osworld_setup/OSWorld.md).

For provider-specific setup instructions, see the documentation in the respective provider directories.
