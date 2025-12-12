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
  "ark_apikey": "optional-llm-api-key"
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
- `ark_apikey` (optional): API key for LLM models (OpenAI, Anthropic, etc.)

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

## Model Configuration with ark_apikey

The `ark_apikey` parameter allows you to specify a custom API key for LLM models used by the agent. This is similar to the `LLMConfig` functionality in the gRPC server.

When `ark_apikey` is provided, it will be applied to all LLM-based tools in the agent:
- Grounding model
- Action generator models
- Embedding models
- Planning models
- And all other LLM-based components

This allows you to:
1. Use different API keys for different tasks
2. Override the default API key configured in environment variables
3. Support multi-tenant scenarios where different users have different API keys

**Example:**
```bash
curl -X POST http://localhost:8080/api/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "Open calculator and compute 123 + 456",
    "ark_apikey": "sk-your-openai-api-key",
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
        "ark_apikey": "your_llm_api_key"  # Optional
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
| Model Config | ark_apikey parameter | LLMConfig protobuf |
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
4. The `ark_apikey` parameter allows per-request API key specification for multi-tenant scenarios
5. API keys are not logged or exposed in responses

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
