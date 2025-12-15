# Lybic GUI Agent RESTful API

RESTful API server for Lybic GUI Agent, providing HTTP/REST interface similar to the gRPC service functionality.

## Installation

Install the optional RESTful API dependencies:

```bash
pip install lybic-guiagents[restful]
```

Or install individual dependencies:

```bash
pip install fastapi sse-starlette uvicorn pydantic
```

## Running the Server

### Using the CLI command:

```bash
lybic-guiagent-restful
```

### Using Python module:

```bash
python -m gui_agents.restful_app
```

### Configuration via Environment Variables:

```bash
# Server configuration
export RESTFUL_HOST=0.0.0.0
export RESTFUL_PORT=8080
export LOG_LEVEL=INFO

# Lybic authentication (used as default if not provided in requests)
export LYBIC_API_KEY=your_api_key
export LYBIC_ORG_ID=your_org_id
export LYBIC_API_ENDPOINT=https://api.lybic.cn/

# Task configuration
export TASK_MAX_TASKS=5
export LOG_DIR=runtime

# Optional: Prometheus metrics
export ENABLE_PROMETHEUS=true
export PROMETHEUS_PORT=8000

lybic-guiagent-restful
```

### Using Docker:

```bash
docker build -t lybic-guiagent .
docker run -p 8080:8080 \
  -e LYBIC_API_KEY=your_api_key \
  -e LYBIC_ORG_ID=your_org_id \
  lybic-guiagent /app/.venv/bin/lybic-guiagent-restful
```

## API Endpoints

### 1. Get Agent Info
```
GET /api/agent/info
```

Returns server information including version, max concurrent tasks, log level, and domain.

**Response:**
```json
{
  "version": "0.7.6",
  "max_concurrent_tasks": 5,
  "log_level": "INFO",
  "domain": "hostname"
}
```

### 2. Run Agent (Streaming)
```
POST /api/agent/run
```

Run an agent task with Server-Sent Events (SSE) streaming for real-time progress updates.

**Request Body:**
```json
{
  "instruction": "Open calculator and compute 123 + 456",
  "sandbox_id": "optional-existing-sandbox-id",
  "max_steps": 50,
  "mode": "fast",
  "platform": "Windows",
  "shape": "beijing-2c-4g-cpu",
  "destroy_sandbox": false,
  "continue_context": false,
  "task_id": "optional-previous-task-id",
  "authentication": {
    "api_key": "your_api_key",
    "org_id": "your_org_id",
    "api_endpoint": "https://api.lybic.cn/"
  },
  "stage_model_config": {
    "grounding_model": {
      "model_name": "gpt-4o",
      "provider": "openai",
      "api_key": "sk-your-openai-key"
    },
    "action_generator_model": {
      "model_name": "claude-3-5-sonnet-20241022",
      "provider": "anthropic",
      "api_key": "sk-ant-your-anthropic-key"
    },
    "embedding_model": {
      "model_name": "text-embedding-3-large",
      "provider": "openai"
    }
  }
}
```

**Request Parameters:**
- `instruction` (required): Task instruction in natural language
- `sandbox_id` (optional): Use existing sandbox ID
- `max_steps` (optional, default: 50): Maximum steps for execution
- `mode` (optional, default: "fast"): Agent mode - "normal" or "fast"
- `platform` (optional, default: "Windows"): Platform - "Windows", "Ubuntu", or "Android"
- `shape` (optional, default: "beijing-2c-4g-cpu"): Sandbox shape/size
- `destroy_sandbox` (optional, default: false): Destroy sandbox after completion
- `continue_context` (optional, default: false): Continue from previous task
- `task_id` (optional): Previous task ID for context continuation
- `authentication` (optional): Lybic authentication (uses env vars if not provided)
- `stage_model_config` (optional): Stage-specific model configurations for different agent components

**Response (SSE Stream):**
```
event: starting
data: {"task_id": "uuid", "stage": "starting", "message": "Task starting", "timestamp": 1234567890}

event: running
data: {"task_id": "uuid", "stage": "running", "message": "Step 1...", "timestamp": 1234567891}

event: finished
data: {"task_id": "uuid", "stage": "finished", "message": "Task completed successfully", "timestamp": 1234567892}
```

### 3. Submit Task (Async)
```
POST /api/agent/submit
```

Submit a task asynchronously and receive a task ID immediately for later status checking.

**Request Body:**
Same as `/api/agent/run`

**Response:**
```json
{
  "task_id": "task-uuid",
  "status": "pending"
}
```

### 4. Get Task Status
```
GET /api/agent/status?task_id={task_id}
```

Query the status of a submitted task.

**Response:**
```json
{
  "task_id": "task-uuid",
  "status": "completed",
  "message": "Task finished with status: completed",
  "result": null,
  "sandbox": {
    "id": "sandbox-id",
    "shape_name": "beijing-2c-4g-cpu"
  },
  "execution_statistics": {
    "steps": 15,
    "duration_seconds": 45.2,
    "input_tokens": 1234,
    "output_tokens": 567,
    "total_tokens": 1801,
    "cost": 0.05,
    "currency_symbol": "￥"
  }
}
```

**Status Values:**
- `pending`: Task is queued
- `running`: Task is currently executing
- `completed`: Task finished successfully
- `failed`: Task encountered an error
- `cancelled`: Task was cancelled

### 5. Cancel Task
```
POST /api/agent/cancel
```

Cancel a running task.

**Request Body:**
```json
{
  "task_id": "task-uuid"
}
```

**Response:**
```json
{
  "task_id": "task-uuid",
  "success": true,
  "message": "Task has been successfully cancelled"
}
```

### 6. List Tasks
```
GET /api/agent/tasks?limit=100&offset=0
```

List all tasks with pagination.

**Query Parameters:**
- `limit` (optional, default: 100): Maximum number of tasks to return
- `offset` (optional, default: 0): Number of tasks to skip

**Response:**
```json
{
  "tasks": [
    {
      "task_id": "task-uuid-1",
      "status": "completed",
      "instruction": "Open calculator",
      "created_at": 1234567890.123,
      "final_state": "completed"
    }
  ],
  "total": 150,
  "limit": 100,
  "offset": 0
}
```

### 7. Create Sandbox
```
POST /api/sandbox/create
```

Create a new sandbox environment.

**Request Body:**
```json
{
  "name": "my-sandbox",
  "maxLifeSeconds": 3600,
  "projectId": "optional-project-id",
  "shape": "beijing-2c-4g-cpu",
  "authentication": {
    "api_key": "your_api_key",
    "org_id": "your_org_id",
    "api_endpoint": "https://api.lybic.cn/"
  }
}
```

**Response:**
```json
{
  "sandbox_id": "sandbox-uuid",
  "shape": "beijing-2c-4g-cpu",
  "status": "created"
}
```

## Model Configuration with stage_model_config

The `stage_model_config` parameter allows you to configure different LLM models for different agent components. This provides the same functionality as the gRPC server's `StageModelConfig`.

### Supported Model Configurations

The `stage_model_config` allows you to configure different LLM models for different agent components. Each component serves a specific purpose in the agent's execution pipeline:

| Configuration Field | Tool Name | Purpose | Agent Mode | Recommended Models |
|---------------------|-----------|---------|------------|-------------------|
| `web_search_engine` | websearch | Web search engine | Normal | `exa`, `ark` |
| `context_fusion_model` | context_fusion | Fuse context from multiple sources | Normal | GPT-4o, Claude-3.5-Sonnet, Gemini-2.5-Pro |
| `subtask_planner_model` | subtask_planner | Break down tasks into subtasks | Normal | GPT-4o, Claude-3.5-Sonnet, Gemini-2.5-Pro |
| `traj_reflector_model` | traj_reflector | Reflect on execution trajectory | Normal | GPT-4o, Claude-3.5-Sonnet, Gemini-2.5-Pro |
| `memory_retrival_model` | memory_retrival | Retrieve relevant memory | Normal | GPT-4o, Claude-3.5-Sonnet, Gemini-2.5-Pro |
| `grounding_model` | grounding | Ground UI elements in screenshots | Normal/Fast | Qwen-VL-Max, Doubao-1.5-UI-Tars, GPT-4o |
| `task_evaluator_model` | evaluator | Evaluate task completion | Normal | GPT-4o, Claude-3.5-Sonnet, Gemini-2.5-Pro |
| `action_generator_model` | action_generator | Generate actions (Normal mode) | Normal | GPT-4o, Claude-3.5-Sonnet, Gemini-2.5-Pro, DeepSeek-R1 |
| `action_generator_with_takeover_model` | action_generator_with_takeover | Generate actions with takeover | Normal | GPT-4o, Claude-3.5-Sonnet, Gemini-2.5-Pro |
| `fast_action_generator_model` | fast_action_generator | Generate actions (Fast mode) | Fast | GPT-4o, Claude-3.5-Sonnet, Gemini-2.5-Pro |
| `fast_action_generator_with_takeover_model` | fast_action_generator_with_takeover | Generate actions with takeover (Fast) | Fast | GPT-4o, Claude-3.5-Sonnet, Gemini-2.5-Pro |
| `dag_translator_model` | dag_translator | Translate task to DAG | Normal | GPT-4o, Claude-3.5-Sonnet, Gemini-2.5-Pro |
| `embedding_model` | embedding | Generate text embeddings | Normal/Fast | text-embedding-3-large, Gemini-Embedding, Jina-v4 |
| `query_formulator_model` | query_formulator | Formulate search queries | Normal | GPT-4o, Claude-3.5-Sonnet, Gemini-2.5-Pro |
| `narrative_summarization_model` | narrative_summarization | Summarize task narrative | Normal | GPT-4o, Claude-3.5-Sonnet, Gemini-2.5-Pro |
| `text_span_model` | text_span | Extract text spans | Normal | GPT-4o, Claude-3.5-Sonnet, Gemini-2.5-Pro |
| `episode_summarization_model` | episode_summarization | Summarize episodes | Normal | GPT-4o, Claude-3.5-Sonnet, Gemini-2.5-Pro |

**Note:** 
- `action_generator_model` serves as the default configuration for all LLM tools (except `grounding_model` and `embedding_model`) if no specific configuration is provided.
- In **Fast mode**, only `grounding_model`, `embedding_model`, and `fast_action_generator_model` are used.
- In **Normal mode**, all components may be used depending on the task complexity.

### Supported Model Providers

For detailed information about supported models and providers, see `gui_agents/tools/model.md`. Key providers include:

- **OpenAI**: gpt-4o, gpt-4.1, o1, o3-mini, text-embedding-3-large
- **Anthropic**: claude-opus-4, claude-sonnet-4, claude-3-7-sonnet, claude-3-5-sonnet-20241022
- **Google Gemini**: gemini-2.5-pro, gemini-2.5-flash, gemini-2.0-flash, text-embedding-004
- **Alibaba Qwen**: qwen-max-latest, qwen-vl-max-latest (grounding), text-embedding-v4
- **ByteDance Doubao**: doubao-1-5-ui-tars-250428 (grounding), doubao-seed-1-6-flash
- **DeepSeek**: deepseek-chat, deepseek-reasoner
- **Zhipu GLM**: GLM-4-Plus, GLM-4-AirX (grounding), Embedding-3
- **xAI Grok**: grok-3-beta, grok-beta
- **Proxy Platforms**: Monica, OpenRouter (support multiple providers)

### LLM Config Fields

Each model configuration supports:
- `model_name` (required): Model name (e.g., "gpt-4o", "claude-3-5-sonnet-20241022", "gemini-2.5-pro")
- `provider` (optional): Provider name (e.g., "openai", "anthropic", "gemini", "doubao")
- `api_key` (optional): API key for this specific model
- `api_endpoint` (optional): Custom API endpoint (useful for proxy services or self-hosted models)

### Benefits

1. Use different models for different components
2. Use different API keys per model or per task
3. Override default configurations from environment variables
4. Support multi-tenant scenarios with per-user API keys
5. Cost optimization by using cheaper models for less critical components

### Examples

**Example 1: Use different models for different components**
```bash
curl -X POST http://localhost:8080/api/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "Open calculator and compute 123 + 456",
    "stage_model_config": {
      "grounding_model": {
        "model_name": "gpt-4o",
        "provider": "openai",
        "api_key": "sk-your-openai-key"
      },
      "action_generator_model": {
        "model_name": "claude-3-5-sonnet-20241022",
        "provider": "anthropic",
        "api_key": "sk-ant-your-anthropic-key"
      },
      "embedding_model": {
        "model_name": "text-embedding-3-large",
        "provider": "openai"
      }
    },
    "authentication": {
      "api_key": "your_lybic_api_key",
      "org_id": "your_lybic_org_id"
    }
  }'
```

**Example 2: Use custom endpoint**
```bash
curl -X POST http://localhost:8080/api/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "Search for latest AI news",
    "stage_model_config": {
      "action_generator_model": {
        "model_name": "deepseek-chat",
        "provider": "openai",
        "api_key": "your-deepseek-key",
        "api_endpoint": "https://api.deepseek.com/v1"
      }
    },
    "authentication": {
      "api_key": "your_lybic_api_key",
      "org_id": "your_lybic_org_id"
    }
  }'
```

## Interactive API Documentation

Once the server is running, you can access:

- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc
- **OpenAPI JSON**: http://localhost:8080/openapi.json

## Example Usage

### Python Client Example:

```python
import requests
import json

# Server URL
BASE_URL = "http://localhost:8080"

# Authentication
auth = {
    "api_key": "your_lybic_api_key",
    "org_id": "your_lybic_org_id"
}

# Submit a task asynchronously
response = requests.post(
    f"{BASE_URL}/api/agent/submit",
    json={
        "instruction": "Open notepad and type 'Hello World'",
        "mode": "fast",
        "max_steps": 30,
        "authentication": auth,
        "stage_model_config": {  # Optional
            "action_generator_model": {
                "model_name": "gpt-4o",
                "api_key": "your_llm_api_key"
            }
        }
    }
)
task_data = response.json()
task_id = task_data["task_id"]
print(f"Task submitted: {task_id}")

# Poll task status
import time
while True:
    response = requests.get(f"{BASE_URL}/api/agent/status?task_id={task_id}")
    status_data = response.json()
    print(f"Status: {status_data['status']}")
    
    if status_data["status"] in ["completed", "failed", "cancelled"]:
        print(f"Final state: {status_data}")
        if status_data.get("execution_statistics"):
            stats = status_data["execution_statistics"]
            print(f"Executed in {stats['steps']} steps, {stats['duration_seconds']}s")
            print(f"Tokens used: {stats['total_tokens']}, Cost: {stats['cost']} {stats['currency_symbol']}")
        break
    
    time.sleep(2)
```

### Streaming Example:

```python
import requests
import json

# For SSE streaming
def stream_task(instruction):
    url = "http://localhost:8080/api/agent/run"
    data = {
        "instruction": instruction,
        "authentication": {
            "api_key": "your_api_key",
            "org_id": "your_org_id"
        }
    }
    
    response = requests.post(url, json=data, stream=True)
    
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data:'):
                data = json.loads(line[5:])
                print(f"[{data['stage']}] {data['message']}")

stream_task("Open calculator and compute 10 + 20")
```

### cURL Examples:

```bash
# Get server info
curl http://localhost:8080/api/agent/info

# Submit task
curl -X POST http://localhost:8080/api/agent/submit \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "Open calculator",
    "authentication": {
      "api_key": "your_api_key",
      "org_id": "your_org_id"
    }
  }'

# Check task status
curl "http://localhost:8080/api/agent/status?task_id=YOUR_TASK_ID"

# Cancel task
curl -X POST http://localhost:8080/api/agent/cancel \
  -H "Content-Type: application/json" \
  -d '{"task_id": "YOUR_TASK_ID"}'

# List all tasks
curl "http://localhost:8080/api/agent/tasks?limit=10"
```

## Comparison with gRPC Service

The RESTful API provides similar functionality to the gRPC service (`grpc_app.py`) but using HTTP/REST:

| Feature | RESTful API | gRPC Service |
|---------|-------------|--------------|
| Protocol | HTTP/REST | gRPC |
| Streaming | SSE (Server-Sent Events) | gRPC Streaming |
| Task Submission | POST /api/agent/submit | RunAgentInstructionAsync |
| Task Status | GET /api/agent/status | QueryTaskStatus |
| Task Cancellation | POST /api/agent/cancel | CancelTask |
| Agent Info | GET /api/agent/info | GetAgentInfo |
| Model Config | stage_model_config parameter | StageModelConfig protobuf |
| Authentication | JSON in request body | AuthorizationInfo protobuf |

## Performance Considerations

- The RESTful API uses the same underlying agent infrastructure as the gRPC service
- SSE streaming provides near real-time updates similar to gRPC streaming
- For high-throughput scenarios, consider using the gRPC service instead
- The server enforces a maximum concurrent task limit (default: 5, configurable via `TASK_MAX_TASKS`)

## Monitoring

If Prometheus metrics are enabled:
- Metrics are exposed on port 8000 (configurable via `PROMETHEUS_PORT`)
- Metrics include task counts, execution times, token usage, and system resources
- Compatible with the same metrics as the gRPC service

## Error Handling

The API returns standard HTTP status codes:
- `200`: Success
- `400`: Bad request (invalid parameters)
- `404`: Resource not found (task ID doesn't exist)
- `500`: Internal server error
- `503`: Service unavailable (max concurrent tasks reached)

Error responses include a `detail` field with more information:
```json
{
  "detail": "Max concurrent tasks (5) reached"
}
```

## Security Notes

1. The API key and authentication credentials should be kept secure
2. Use HTTPS in production environments
3. Consider implementing rate limiting and authentication middleware
4. API keys are not logged or exposed in responses

## Troubleshooting

### Server won't start
- Check that port 8080 is not already in use
- Verify all dependencies are installed: `pip install lybic-guiagents[restful]`
- Check environment variables are correctly set

### Tasks fail immediately
- Verify Lybic authentication credentials are correct
- Check that the specified platform/shape is available
- Review logs in the `runtime/` directory

### Streaming doesn't work
- Ensure your HTTP client supports Server-Sent Events (SSE)
- Check that firewalls/proxies don't block SSE connections
- Try using the async submission endpoint instead

## License

This RESTful API is part of the Lybic GUI Agent project and is licensed under the Apache-2.0 license.
