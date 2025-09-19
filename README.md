<div align="center">

**[English](./README.md) | [中文](./README-zh.md) | [日本語](./README-jp.md)**

<br/>
</div>

<p align="center">
  <img src="assets/logo.png" alt="Lybic Logo" width="400"/>
</p>
<h1 align="center">
  Lybic GUI Agent: <small>An open-source agentic framework for Computer Use Agents</small> 
</h1>

<p align="center">
    <small>Supported OS:</small>
    <img src="https://img.shields.io/badge/OS-Windows-blue?logo=windows&logoColor=white" alt="Windows">
    <img src="https://img.shields.io/badge/OS-macOS-black?logo=apple&logoColor=white" alt="macOS">
    <img src="https://img.shields.io/badge/OS-Linux-yellow?logo=linux&logoColor=black" alt="Linux">
    <br/>
    <small>Latest Version:</small><a href="https://pypi.org/project/lybic-guiagents/"><img alt="PyPI" src="https://img.shields.io/pypi/v/lybic-guiagents"></a>
    &nbsp;
    <a href="https://github.com/lybic/agent/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/pypi/l/lybic-guiagents"></a>
    &nbsp;
    <a href="https://github.com/lybic/agent"><img alt="Stars" src="https://img.shields.io/github/stars/lybic/agent?style=social"></a>
</p>

## What is Lybic GUI Agent?

Lybic platform placeholder - comprehensive AI platform for building and deploying intelligent agents

Lybic GUI Agent is an open-source framework that enables developers and businesses to create intelligent computer-use agents,mobile-use agents, and intelligent agents that can understand and interact with graphical user interfaces across Windows, macOS, Linux and Android(via lybic Android Sandbox) platforms.

<!-- <p align="center"><small>Lybic GUI Agent is based upon the <a href="https://github.com/simular-ai/Agent-S">Agent-S</a> codebase, allowing us to focus on making the best interaction experience with Lybic while maintaining a familiar execution logic.</small></p> -->

<div align="center">

<p>Skip the setup? Try Lybic GUI Agent in our <a href="https://playground.lybic.cn/">Playground</a> with a few clicks.(Only in the Chinese mainland supported)

</div>

## 🥳 Updates
- [x] **2025/09/14**: The paper has been accepted by [arxiv](https://arxiv.org/abs/2509.11067)
- [x] **2025/09/09**: We achieved the world's first place in the 50-step length of [OS-world](https://os-world.github.io/)!
- [x] **2025/08/08**: Released v0.1.0 of [Lybic GUI Agent](https://github.com/lybic/agent) library, with support for Windows, Mac, Ubuntu and Lybic API!

## Table of Contents

1. [💡 Introduction](#-introduction)
2. [🛠️ Installation & Setup](#%EF%B8%8F-installation--setup) 
3. [🚀 Usage](#-usage)
4. [🔧 Troubleshooting](#-troubleshooting)
5. [💬 Citations](#-citations)

## 💡 Introduction

## ✨ Feature Agentic Lybic Support

- **Multiple LLMs providers**:  OpenAI, Anthropic, Google, xAI , AzureOpenAI, DeepSeek, Qwen, Doubao, ZhipuGLM
  - **Aggregation Model Provider**:  Bedrock, Groq, Monica, OpenRouter, SiliconFlow
- **RAG**: We support RAG, and this capability is provided as an extension
- **Cross-Platform GUI Control**: Windows, Linux, macOS, Android Supported
- **Observability**: Supported
- **Local Deployment**: Supported
- **Cloud Sandbox Environment**: Supported

<p align="center">🎉 Agents Online Demo</p>

[![Our demo](https://img.youtube.com/vi/GaOoYoRKWhE/maxresdefault.jpg)](https://www.youtube.com/watch?v=GaOoYoRKWhE)

<p align="center">🎯 Current Results</p>

<div align="center">
  <table border="0" cellspacing="0" cellpadding="5">
    <tr>
      <th>Benchmark</th>
      <th>Lybic GUI Agent</th>
      <th>Previous SOTA</th>
    </tr>
    <tr>
      <td>OSWorld Verified (50 step)</td>
      <td><b>57.1%</b></td>
      <td>54.2%</td>
    </tr>
  </table>
</div>

<p align="center">
  <img src="assets/structure.png" alt="Lybic GUI Agent system structure" width="700"/>
</p>
<p align="center"><b>Fig. Lybic GUI Agent system structure</b></p>

## 🛠️ Installation & Setup

> [!WARNING]
> To leverage the full potential of Lybic GUI Agent, we support multiple model providers including OpenAI, Anthropic, Gemini, and Doubao. For the best visual grounding performance, we recommend using UI-TARS models.

### Installation(from pip)

You can install Lybic GUI Agent by using pip:

```bash
pip install lybic-guiagents
```

### Installation(from source code)

You can use [UV](https://docs.astral.sh/uv/getting-started/installation/) (a modern Python package manager) version 0.8.5 for installation:

```bash
# 1. Install UV if not already installed
# macOS and Linux
curl -LsSf https://astral.sh/uv/0.8.5/install.sh | sh
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/0.8.5/install.ps1 | iex"

# testing uv installation, version should be 0.8.5
uv --version

# 2. Install the python 3.12
uv python install 3.12.11

# 3. Create a virtual environment
uv venv -p 3.12.11

# 4. Activate the virtual environment
# macOS and Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate

# 5. Install dependencies (using locked versions)
uv sync

# 6. Install the package locally in development mode
uv pip install -e .
```

### API Key Configuration

The simplest way to configure API keys is to:

1. Copy `gui_agents/.env.example` to `gui_agents/.env`
2. Edit the `.env` file and add your API keys

### Tool Configuration

We provide two pre-configured tool settings:

- `tools_config_en.json`: Configured for English language models (Gemini, Exa)
- `tools_config_cn.json`: Configured for Chinese language models (Doubao, bocha)

The agent uses `tools_config.json` by default. You can:

- Copy either `tools_config_en.json` or `tools_config_cn.json` to `tools_config.json`
- Or create your own custom configuration

If you are using `tools_config_cn.json` and use `pyautogui` backend, the environment variable only `ARK_API_KEY` should be set.

If you are using `tools_config_en.json` and use `pyautogui` backend, you should set those 3 environment variables:

```bash
GEMINI_ENDPOINT_URL=https://generativelanguage.googleapis.com/v1beta/openai/
GEMINI_API_KEY=your_gemini_api_key
ARK_API_KEY=your_ark_api_key
```

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
- `--enable-takeover`: (Optional) Enables user takeover functionality, allowing the agent to pause and request user intervention when needed. By default, user takeover is disabled.
- `--disable-search`: (Optional) Disables web search functionality. By default, web search is enabled.

### Examples

Run in interactive mode with the `lybic` backend:
```sh
python gui_agents/cli_app.py --backend lybic
```


Run a single query with the `pyautogui` backend and a maximum of 20 steps:
```sh
python gui_agents/cli_app.py --backend pyautogui --query "Find the result of 8 × 7 on a calculator" --max-steps 20
```

Run in fast mode with the `pyautogui` backend:
```sh
python gui_agents/cli_app.py --backend pyautogui --mode fast
```

> [!WARNING]
> The agent will directly control your computer with `--backend pyautogui`. Please use with care.

### Lybic Sandbox Configuration

The simplest way to configure Lybic Sandbox is still to edit the `.env` file and add your API keys, as mentioned in the [API Key Configuration](#api-key-configuration) section.


```bash
LYBIC_API_KEY=your_lybic_api_key
LYBIC_ORG_ID=your_lybic_org_id
LYBIC_MAX_LIFE_SECONDS=3600
```

> **Note**: If you want to use a precreated Lybic Sandbox in [Lybic Dashboard](https://dashboard.lybic.cn/), you need to set the `LYBIC_PRECREATE_SID` to the precreated Sandbox ID.

> 
> ```bash
> LYBIC_PRECREATE_SID=SBX-XXXXXXXXXXXXXXX
> ```

### Use as a service

After installing lybic-guiagents, you can run it as a service.

Main Components:
- AgentService: High-level service interface (recommended for most users)
- AgentS2, AgentSFast: Core agent implementations  
- HardwareInterface: Hardware abstraction layer
- ServiceConfig: Configuration management

Quick Start:

```python
from gui_agents import AgentService
service = AgentService()
result = service.execute_task("Take a screenshot")
print(f"Task completed: {result.status}")
```

### VMware Configuration

To use PyAutoGUI with VMware, you need to install [VMware Workstation Pro](https://www.vmware.com/products/desktop-hypervisor/workstation-and-fusion) (on Windows) and create a virtual machine. 

Next, you need to download the [`Windows-x86.zip`](https://huggingface.co/datasets/xlangai/ubuntu_osworld/resolve/main/Ubuntu-x86.zip) and [`Ubuntu-x86.zip`](https://huggingface.co/datasets/xlangai/ubuntu_osworld/resolve/main/Ubuntu-x86.zip) from Hugging Face. Then unzip them into `./vmware_vm_data/Windows-x86` and `./vmware_vm_data/Ubuntu-x86` directory.

Finally, you need to edit the `.env` file and set the `USE_PRECREATE_VM` environment variable to the name of the virtual machine. `USE_PRECREATE_VM` support `Windows` and `Ubuntu` on x86 arch computer.

```bash
USE_PRECREATE_VM=Ubuntu
```

## 🔧 Troubleshooting

### Common Runtime Issues

#### 1. API Key Configuration Issues

**Problem**: `KeyError` or authentication errors when running the agent.

**Solution**:
- Ensure your `.env` file is properly configured with valid API keys
- Check that environment variables are set correctly:
  ```bash
  # For English models
  export GEMINI_API_KEY=your_gemini_api_key
  export ARK_API_KEY=your_ark_api_key
  
  # For Chinese models  
  export ARK_API_KEY=your_ark_api_key
  ```
- Verify API key permissions and quotas

#### 2. Python Environment Issues

**Problem**: `ModuleNotFoundError` or package import errors.

**Solution**:
- Ensure you're using Python 3.12.11 as specified
- Activate the virtual environment:
  ```bash
  # macOS/Linux
  source .venv/bin/activate
  # Windows
  .venv\Scripts\activate
  ```
- Reinstall dependencies:
  ```bash
  uv sync
  uv pip install -e .
  # uv pip install -e . -i  https://pypi.tuna.tsinghua.edu.cn/simple
  ```

#### 3. Lybic Sandbox Connection Issues

**Problem**: `Connection timeout` or `Sandbox creation failed`.

**Solution**:
- Check network connectivity to Lybic servers
- Verify `LYBIC_ORG_ID` and `LYBIC_API_KEY` are correct
- Ensure sufficient quota in your Lybic account
- Try increasing `LYBIC_MAX_LIFE_SECONDS` if sandbox times out

#### 4. VMware Backend Issues

**Problem**: Virtual machine fails to start or control.

**Solution**:
- Ensure VMware Workstation Pro is properly installed
- Check that VM files are extracted to correct directories:
  - `./vmware_vm_data/Windows-x86/`
  - `./vmware_vm_data/Ubuntu-x86/`
- Verify VMware service is running
- Set correct `USE_PRECREATE_VM` environment variable

#### 5. Model Performance Issues

**Problem**: Slow response times or poor grounding accuracy.

**Solution**:

- Use recommended models for better performance:
  - Visual grounding: `doubao-1-5-ui-tars-250428`
  - Action generation: `claude-sonnet-4-20250514`
- Switch to `--mode fast` for quicker execution
- Reduce `--max-steps` for shorter tasks

### Getting Help

If you encounter issues not covered here:

1. Check the [GitHub Issues](https://github.com/lybic/agent/issues) for similar problems
2. Review the [Lybic Documentation](https://lybic.ai/docs)
3. Create a new issue with:
   - Your operating system and version
   - Python version and environment details
   - Complete error messages
   - Steps to reproduce the issue

## 💬 Citations

If you find this codebase useful, please cite:

```bibtex
@misc{guo2025agenticlybicmultiagentexecution,
      title={Agentic Lybic: Multi-Agent Execution System with Tiered Reasoning and Orchestration}, 
      author={Liangxuan Guo and Bin Zhu and Qingqian Tao and Kangning Liu and Xun Zhao and Xianzhe Qin and Jin Gao and Guangfu Hao},
      year={2025},
      eprint={2509.11067},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2509.11067}, 
}
```

---

## ❤️ Touch us:

<div align="center" style="display: flex; justify-content: center; gap: 20px; flex-wrap: wrap;">
  <img src="assets/feishu.png" alt="Lark Group" style="width: 200px; height: auto;"/>
  <img src="assets/wechat.png" alt="WeChat Group" style="width: 200px; height: auto;"/>
  <img src="assets/qq.png" alt="QQ Group" style="width: 200px; height: auto;"/>
</div>

## Stargazers over time

[![Stargazers over time](https://starchart.cc/lybic/agent.svg)](https://starchart.cc/lybic/agent)

## License

This project is distributed under Apache 2.0 License.
Therefore, you can modify the source code and release it commercially.
