# Destroy Sandbox Feature

## Overview

The destroy sandbox feature allows you to automatically delete Lybic sandboxes after task completion. This is useful for:
- Cleaning up resources after automated tests
- Preventing accumulation of unused sandboxes
- Managing sandbox costs in production environments

**Note:** This feature is **disabled by default** to prevent accidental deletion of sandboxes. It only applies to sandboxes created by the backend instance, not pre-created sandboxes.

## Usage

### CLI Application

Add the `--destroy-sandbox` flag to destroy the sandbox after task completion:

```bash
# With automatic sandbox creation
python gui_agents/cli_app.py --backend lybic --query "Open calculator" --destroy-sandbox

# With fast mode
python gui_agents/cli_app.py --backend lybic --mode fast --query "Search for Python" --destroy-sandbox

# With pre-created sandbox (sandbox will NOT be destroyed)
python gui_agents/cli_app.py --backend lybic --lybic-sid SBX-XXXXX --query "Test task" --destroy-sandbox
```

### gRPC Application

Set the `destroySandbox` field in the `RunAgentInstructionRequest`:

```python
import grpc
from gui_agents.proto.pb import agent_pb2, agent_pb2_grpc

# Connect to gRPC server
channel = grpc.insecure_channel('localhost:50051')
stub = agent_pb2_grpc.AgentStub(channel)

# Create request with destroy sandbox enabled
request = agent_pb2.RunAgentInstructionRequest(
    instruction="Open calculator and add 2 + 2",
    destroySandbox=True  # Enable sandbox destruction
)

# Execute task
for response in stub.RunAgentInstruction(request):
    print(f"Stage: {response.stage}, Message: {response.message}")
```

### Service Layer

Use the `destroy_sandbox` parameter in the service API:

```python
from gui_agents import AgentService

# Create service instance
service = AgentService()

# Execute task with sandbox destruction enabled
result = service.execute_task(
    instruction="Take a screenshot",
    destroy_sandbox=True  # Enable sandbox destruction
)

print(f"Task status: {result.status}")
print(f"Task result: {result.result}")

# For async execution
handle = service.execute_task_async(
    instruction="Search for information",
    destroy_sandbox=True
)

# Check status later
status = service.get_task_status(handle.task_id)
```

## Behavior Details

### When Sandboxes Are Destroyed

Sandboxes are destroyed in the following cases:
- ✅ Sandboxes created automatically by the backend
- ✅ After task completion (success or failure)
- ✅ Even if the task throws an exception (cleanup in finally block)

### When Sandboxes Are NOT Destroyed

Sandboxes are **not** destroyed in these cases:
- ❌ Pre-created sandboxes (when using `--lybic-sid` or providing a sandbox ID)
- ❌ When `--destroy-sandbox` flag is not specified (default behavior)
- ❌ When using non-Lybic backends (PyAutoGUI, ADB, etc.)

### Example Logs

When sandbox destruction is successful:
```
INFO: Destroying sandbox as requested...
INFO: Successfully destroyed sandbox: SBX-01K1X6ZKAERXAN73KTJ1XXJXAF
```

When using a pre-created sandbox:
```
INFO: Skipping destruction of pre-created sandbox: SBX-01K1X6ZKAERXAN73KTJ1XXJXAF
```

When destruction fails:
```
ERROR: Failed to destroy sandbox SBX-01K1X6ZKAERXAN73KTJ1XXJXAF: Connection timeout
```

## Best Practices

1. **Use in CI/CD**: Enable sandbox destruction in automated test environments to prevent resource buildup
2. **Disable in development**: Keep the default (disabled) during development to inspect sandbox state after task completion
3. **Pre-created sandboxes**: Use pre-created sandboxes when you want to preserve the environment across multiple tasks
4. **Error handling**: The feature gracefully handles destruction failures and logs the error without affecting task results

## Configuration

### Environment Variables

No additional environment variables are needed. The feature uses existing Lybic credentials:
- `LYBIC_API_KEY`: Your Lybic API key
- `LYBIC_ORG_ID`: Your Lybic organization ID
- `LYBIC_API_ENDPOINT`: Lybic API endpoint (optional, defaults to https://api.lybic.cn)

### Service Configuration

For the service layer, you can set default behavior (though defaults are always False):

```python
from gui_agents import AgentService, ServiceConfig

config = ServiceConfig.from_env()
service = AgentService(config=config)

# Override per-task
service.execute_task("Task", destroy_sandbox=True)
```

## Troubleshooting

### Sandbox not destroyed

**Problem**: Sandbox still exists after task completion with `--destroy-sandbox` flag.

**Solutions**:
1. Check if you're using a pre-created sandbox (`--lybic-sid` or sandbox ID in request)
2. Verify you're using Lybic backend (not PyAutoGUI or others)
3. Check logs for error messages during destruction
4. Ensure you have proper Lybic API credentials

### Permission errors

**Problem**: "Failed to destroy sandbox: Permission denied"

**Solutions**:
1. Verify your API key has sandbox deletion permissions
2. Check if the sandbox was created by a different organization
3. Contact Lybic support if the sandbox is locked or protected

## API Reference

### CLI Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--destroy-sandbox` | flag | False | Destroy sandbox after task completion |

### gRPC Protobuf

```protobuf
message RunAgentInstructionRequest {
  string instruction = 1;
  optional Sandbox sandbox = 2;
  optional CommonConfig runningConfig = 3;
  optional bool destroySandbox = 4;  // New field
}
```

### Service API

```python
def execute_task(
    self,
    instruction: str,
    destroy_sandbox: bool | None = None,  # Defaults to False
    **kwargs
) -> TaskResult:
    ...
```

## Related Documentation

- [Lybic SDK Documentation](https://lybic.ai/docs/sdk/python)
- [CLI Application Guide](../README.md#cli-usage)
- [gRPC API Reference](../gui_agents/proto/agent.proto)
- [Service Layer Documentation](../gui_agents/service/README.md)
