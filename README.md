<h1 align="center">
  Lybic GUI Agent:
  <small>A Framework for Computer Use Agents</small>
</h1>

Lybic GUI Agent is based upon the [Agent-S](https://github.com/simular-ai/Agent-S) codebase, allowing us to focus on making the best interaction experience with Lybic while maintaining a familiar execution logic.

## 🥳 Updates
- [x] **2025/07/25**: Released v0.1.0 of [Lybic GUI Agent](https://git.flam.dev/lybic/agent/lybicguiagents) library, with support for Windows, Mac, Ubuntu and Lybic API!

## Table of Contents

1. [🛠️ Installation & Setup](#%EF%B8%8F-installation--setup) 
2. [🚀 Usage](#-usage)

## 🛠️ Installation & Setup

> ❗**Warning**❗: If you are on a Linux machine, creating a `conda` environment will interfere with `pyatspi`. As of now, there's no clean solution for this issue. Proceed through the installation without using `conda` or any virtual environment.

> ⚠️**Disclaimer**⚠️: To leverage the full potential of Lybic GUI Agent, we support multiple model providers including OpenAI, Anthropic, Gemini, and Doubao. For the best visual grounding performance, we recommend using UI-TARS models.

### Installation

You can use [UV](https://docs.astral.sh/uv/getting-started/installation/) (a modern Python package manager)  for installation:

```bash
# 1. Install UV if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh
# testing uv installation
uv --version

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

> **Note**: Our recommended configuration uses `doubao-1-5-ui-tars-250428` for `"tool_name": "grounding" or "fast_action_generator"` and `claude-sonnet-4-20250514` or `doubao-seed-1-6-250615` for other tools such as `"tool_name": "action_generator"`. You can customize the model configuration in the tools configuration files. Do not modify the `"tool_name"` in `tools_config.json` file. To change the `"provider"` and `"model_name"` in `tools_config.json` file, see [model.md](gui_agents/tools/model.md)

## 🚀 Usage

### Command Line Interface

Run Lybic GUI Agent with python in the command-line interface:

```sh
python gui_agents/cli_app.py [OPTIONS]
```

This will show a user query prompt where you can enter your instructions and interact with the agent.

### Options

- `--backend [lybic|pyautogui|pyautogui_vmware]`: Specifies the backend to use for controlling the GUI. Defaults to `lybic`.

- `--query "YOUR_QUERY"`: Optional, can be input during the runtime; if provided, the agent will execute the query and then exit. 
- `--max-steps NUMBER`: Sets the maximum number of steps the agent can take. Defaults to `50`.
- `--mode [normal|fast]`: (Optional) Selects the agent mode. `normal` runs the full agent with detailed reasoning and memory, while `fast` mode executes actions more quickly with less reasoning overhead. Defaults to `normal`.

### Examples

Run in interactive mode with the `lybic` backend:
```sh
python gui_agents/cli_app.py --backend lybic
```

Run a single query with the `pyautogui` backend and a maximum of 20 steps:
```sh
python gui_agents/cli_app.py --backend pyautogui --query "计算器中求 8 × 7 的结果" --max-steps 20
```

Run in fast mode with the `pyautogui` backend:
```sh
python gui_agents/cli_app.py --backend pyautogui --mode fast
```

> ❗**Warning**❗: The agent will directly control your computer with `--backend pyautogui`. Please use with care.

### Lybic Sandbox Configuration

The simplest way to configure Lybic Sandbox is still to edit the `.env` file and add your API keys, as mentioned in the [API Key Configuration](#api-key-configuration) section.


```bash
LYBIC_API_KEY=your_lybic_api_key
LYBIC_ORG_ID=your_lybic_org_id
LYBIC_ENDPOINT_URL=https://api.lybic.cn
LYBIC_MAX_LIFE_SECONDS=3600
```

> **Note**: If you want to use a precreated Lybic Sandbox in [Lybic Dashboard](https://dashboard.lybic.cn/orgs/agent-dev/sandboxes), you need to set the `LYBIC_PRECREATE_SID` to the precreated Sandbox ID.

> 
> ```bash
> LYBIC_PRECREATE_SID=SBX-XXXXXXXXXXXXXXX
> ```

### VMware Configuration

To use PyAutoGUI with VMware, you need to install [VMware Workstation Pro](https://www.vmware.com/products/desktop-hypervisor/workstation-and-fusion) (on Windows) and create a virtual machine. 

Next, you need to download the [`Windows-x86.zip`](https://huggingface.co/datasets/xlangai/ubuntu_osworld/resolve/main/Ubuntu-x86.zip) and [`Ubuntu-x86.zip`](https://huggingface.co/datasets/xlangai/ubuntu_osworld/resolve/main/Ubuntu-x86.zip) from Hugging Face. Then unzip them into `./vmware_vm_data/Windows-x86` and `./vmware_vm_data/Ubuntu-x86` directory.

Finally, you need to edit the `.env` file and set the `USE_PRECREATE_VM` environment variable to the name of the virtual machine. `USE_PRECREATE_VM` support `Windows` and `Ubuntu` on x86 arch computer.


```bash
USE_PRECREATE_VM=Ubuntu
```