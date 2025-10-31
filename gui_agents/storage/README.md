# Task Storage Module

This module provides a flexible storage layer for task persistence in the Lybic GUI Agent gRPC service.

## Overview

The storage module enables the gRPC service to persist task information, supporting both lightweight in-memory storage and durable external database storage. This allows task data to survive service restarts when configured with an external database.

## Architecture

### Components

1. **TaskStorage Interface** (`base.py`)
   - Abstract base class defining the storage contract
   - TaskData dataclass for structured task information
   - Defines CRUD operations for task management

2. **MemoryStorage** (`memory_storage.py`)
   - Default implementation storing data in Python dictionaries
   - Lightweight and requires no external dependencies
   - Data is lost when service restarts

3. **PostgresStorage** (`postgres_storage.py`)
   - External database implementation using PostgreSQL
   - Requires `asyncpg` library
   - Data persists across service restarts
   - Automatic schema creation and management

4. **Storage Factory** (`factory.py`)
   - Creates appropriate storage instance based on configuration
   - Reads from environment variables

## Usage

### Configuration

Set environment variables in `.env` file:

```bash
# Storage backend: memory (default) or postgres
TASK_STORAGE_BACKEND=memory

# PostgreSQL connection string (only needed for postgres backend)
# POSTGRES_CONNECTION_STRING=postgresql://user:password@host:port/database
```

### Memory Storage (Default)

No configuration needed. Tasks are stored in memory:

```python
from gui_agents.storage import create_storage

# Creates MemoryStorage by default
storage = create_storage()
```

### PostgreSQL Storage

1. Install dependencies:
```bash
pip install asyncpg
```

2. Set up PostgreSQL database:
```bash
createdb agent_tasks
```

3. Configure connection:
```bash
export TASK_STORAGE_BACKEND=postgres
export POSTGRES_CONNECTION_STRING=postgresql://postgres:password@localhost:5432/agent_tasks
```

4. The schema will be created automatically on first use:
```python
from gui_agents.storage import create_storage

# Creates PostgresStorage and initializes schema
storage = create_storage()
```

## TaskData Structure

Tasks store the following information:

```python
@dataclass
class TaskData:
    task_id: str                              # Unique task identifier
    status: str                               # pending, running, finished, error, cancelled
    query: str                                # Task instruction/query
    max_steps: int                            # Maximum execution steps
    final_state: Optional[str]                # Final completion state
    timestamp_dir: Optional[str]              # Log directory path
    execution_statistics: Optional[Dict]      # Performance metrics
    sandbox_info: Optional[Dict]              # Sandbox configuration
    created_at: Optional[datetime]            # Creation timestamp
    updated_at: Optional[datetime]            # Last update timestamp
    request_data: Optional[Dict]              # Original request data
```

## API Reference

### TaskStorage Interface

```python
class TaskStorage(ABC):
    async def create_task(self, task_data: TaskData) -> bool
    async def get_task(self, task_id: str) -> Optional[TaskData]
    async def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool
    async def delete_task(self, task_id: str) -> bool
    async def list_tasks(self, status: Optional[str] = None, 
                        limit: Optional[int] = None, 
                        offset: int = 0) -> List[TaskData]
    async def count_active_tasks(self) -> int
    async def cleanup_old_tasks(self, older_than_days: int) -> int
```

### Example Usage

```python
from gui_agents.storage import TaskData, create_storage

# Create storage instance
storage = create_storage()

# Create a new task
task_data = TaskData(
    task_id="task-123",
    status="pending",
    query="Open calculator",
    max_steps=50
)
await storage.create_task(task_data)

# Update task status
await storage.update_task("task-123", {"status": "running"})

# Get task
task = await storage.get_task("task-123")

# List all pending tasks
pending_tasks = await storage.list_tasks(status="pending")

# Count active tasks
active_count = await storage.count_active_tasks()

# Cleanup old tasks (older than 30 days)
deleted = await storage.cleanup_old_tasks(older_than_days=30)
```

## Database Schema (PostgreSQL)

When using PostgreSQL, the following schema is created automatically:

```sql
CREATE TABLE agent_tasks (
    task_id VARCHAR(255) PRIMARY KEY,
    status VARCHAR(50) NOT NULL,
    query TEXT NOT NULL,
    max_steps INTEGER NOT NULL,
    final_state VARCHAR(50),
    timestamp_dir TEXT,
    execution_statistics JSONB,
    sandbox_info JSONB,
    request_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_tasks_status ON agent_tasks(status);
CREATE INDEX idx_agent_tasks_created_at ON agent_tasks(created_at);
```

## Integration with gRPC Service

The gRPC service in `grpc_app.py` uses this storage layer to persist task data:

1. **Task Creation**: When a task is created via `RunAgentInstruction` or `RunAgentInstructionAsync`, persistent data is stored via `storage.create_task()`

2. **Task Updates**: During execution, status changes and statistics are persisted via `storage.update_task()`

3. **Task Queries**: The `QueryTaskStatus` RPC retrieves task data from storage

4. **Concurrency Control**: Active task counting uses `storage.count_active_tasks()`

## Testing

Run the standalone test suite:

```bash
python3 tests/test_storage_standalone.py
```

Or with pytest (requires full environment):

```bash
pytest tests/test_storage.py -v
```

## Migration from Old System

The refactored `grpc_app.py` splits task data into:

- **Persistent data** (stored via TaskStorage): status, query, execution stats, etc.
- **Runtime-only data** (kept in memory): agent instances, futures, queues

This design maintains backward compatibility while enabling optional persistence.

## Performance Considerations

### MemoryStorage
- ✓ No external dependencies
- ✓ Fast access (in-memory)
- ✓ No network latency
- ✗ Data lost on restart
- ✗ No distributed access

### PostgresStorage
- ✓ Data persists across restarts
- ✓ Supports distributed deployments
- ✓ ACID guarantees
- ✗ Requires PostgreSQL setup
- ✗ Network latency for operations
- ✗ Additional dependency

## Future Enhancements

Potential improvements:

1. **Additional Backends**: Redis, MongoDB, SQLite
2. **Connection Pooling**: Optimize PostgreSQL connections
3. **Caching Layer**: Hybrid memory + database approach
4. **Data Retention Policies**: Automatic cleanup configuration
5. **Backup/Restore**: Tools for data migration
6. **Metrics**: Storage operation monitoring

## Contributing

When adding new storage backends:

1. Extend the `TaskStorage` abstract base class
2. Implement all required methods
3. Add tests in `tests/test_storage.py`
4. Update factory in `factory.py`
5. Document configuration options
