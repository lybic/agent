<p align="center">
  <img src="https://raw.githubusercontent.com/lybic/agent/main/assets/logo.png" alt="Lybic Logo" width="400"/>
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

Lybic GUI Agent is an open-source framework that enables developers and businesses to create intelligent computer-use agents that can understand and interact with graphical user interfaces across Windows, macOS, and Linux platforms, primarily through cloud-based sandbox environments.

This Docker image provides a convenient way to run the Lybic GUI Agent as either a command-line tool or a gRPC service.

## ✨ Features

- **Multiple LLMs providers**: OpenAI, Anthropic, Google, xAI, AzureOpenAI, DeepSeek, Qwen, Doubao, ZhipuGLM
- **Aggregation Model Provider**: Bedrock, Groq, Monica, OpenRouter, SiliconFlow
- **RAG**: We support RAG, and this capability is provided as an extension
- **Cross-Platform GUI Control**: Windows, Linux, macOS, Android Supported
- **Observability**: Supported
- **Local Deployment**: Supported
- **Cloud Sandbox Environment**: Supported

## How to Use This Image

### Configuration

Before running the container, you need to create an environment file (e.g., `.env`) to store your API keys.

1.  Create a file named `.env`.
2.  Add your API keys to it. The required keys depend on the tools you configure. For the `lybic` backend (recommended for Docker), you will need:

    ```bash
    # .env file
    
    # Lybic Cloud Sandbox
    LYBIC_API_KEY=your_lybic_api_key
    LYBIC_ORG_ID=your_lybic_org_id
    
    # LLM Provider Keys (depending on your tool_config.json)
    OPENAI_API_KEY=your_openai_key
    ANTHROPIC_API_KEY=your_anthropic_key
    GOOGLE_API_KEY=your_google_key
    
    # Search Provider (optional)
    ARK_API_KEY=your_ark_api_key
    ```

### Running the Agent (CLI Mode)

The image's default command starts the agent in an interactive command-line interface. You can run it using the following command, making sure to provide your `.env` file.

```sh
docker run --rm -it --env-file .env agenticlybic/guiagent
```

This will start the agent with the `lybic` backend by default. You can then enter your instructions at the prompt.

#### CLI Examples

**Run in interactive mode with the `lybic` backend:**

```sh
docker run --rm -it --env-file .env agenticlybic/guiagent --backend lybic
```

**Run a single query and then exit:**

```sh
docker run --rm -it --env-file .env agenticlybic/guiagent --backend lybic --query "Find the result of 8 × 7 on a calculator"
```

**Run in fast mode:**

```sh
docker run --rm -it --env-file .env agenticlybic/guiagent --backend lybic --mode fast
```

### Running the Agent (gRPC Service Mode)

You can also run the agent as a gRPC service, which is ideal for distributed architectures. The service runs on port `50051`.

To start the gRPC server, override the default command:

```sh
docker run --rm -it -p 50051:50051 --env-file .env agenticlybic/guiagent /app/.venv/bin/lybic-guiagent-grpc
```

> **Note**: The `-p 50051:50051` flag maps the container's gRPC port to your host machine.

#### Python Client Example for gRPC

Once the service is running, you can interact with it using a gRPC client.

First, ensure you have the necessary gRPC libraries and generated protobuf stubs:

```sh
# Install gRPC tools
pip install grpcio grpcio-tools

# Clone the repo to get the .proto file
git clone https://github.com/lybic/agent.git

# Generate stubs from the .proto file
python -m grpc_tools.protoc -Iagent/gui_agents/proto --python_out=agent/gui_agents/proto/pb --grpc_python_out=agent/gui_agents/proto/pb --pyi_out=agent/gui_agents/proto/pb agent/gui_agents/proto/agent.proto
```

Then, you can use the following script to communicate with the agent:

```python
import asyncio
import grpc
# Make sure to adjust the import path based on where you generated the stubs
from lybic.gui_agents.proto.pb import agent_pb2, agent_pb2_grpc

async def run_agent_instruction():
    # Connect to the gRPC server
    async with grpc.aio.insecure_channel('localhost:50051') as channel:
        # Create a stub for the Agent service
        stub = agent_pb2_grpc.AgentStub(channel)

        # Create a request to run an instruction
        request = agent_pb2.RunAgentInstructionRequest(
            instruction="Open a calculator and compute 1 + 1"
        )

        print(f"Sending instruction: '{request.instruction}'")

        # Call the RunAgentInstruction RPC and iterate over the stream of responses
        try:
            async for response in stub.RunAgentInstruction(request):
                print(f"[{response.stage}] {response.message}")
        except grpc.aio.AioRpcError as e:
            print(f"An error occurred: {e.details()}")

if __name__ == '__main__':
    asyncio.run(run_agent_instruction())
```

## Image Details

-   **Base Image**: `debian:bookworm-slim`
-   **Exposed Port**: `50051` (for gRPC service)
-   **Default Command**: `lybic-guiagent` (starts the interactive CLI)
-   **gRPC Entrypoint**: `/app/.venv/bin/lybic-guiagent-grpc`

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

## ❤️ Community

Join our community groups to connect with other developers and get support.

<div align="center" style="display: flex; justify-content: center; gap: 20px; flex-wrap: wrap;">
  <img src="https://raw.githubusercontent.com/lybic/agent/main/assets/feishu.png" alt="Lark Group" style="width: 200px; height: auto;"/>
  <img src="https://raw.githubusercontent.com/lybic/agent/main/assets/wechat.jpg" alt="WeChat Group" style="width: 200px; height: auto;"/>
  <img src="https://raw.githubusercontent.com/lybic/agent/main/assets/qq.png" alt="QQ Group" style="width: 200px; height: auto;"/>
</div>

## License

This project is distributed under the Apache 2.0 License.
