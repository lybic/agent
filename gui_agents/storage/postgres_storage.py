"""
PostgreSQL storage implementation for task persistence.

This implementation stores task data in a PostgreSQL database.
Data persists across service restarts.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import logging
import json
import asyncio

from .base import TaskStorage, TaskData

logger = logging.getLogger(__name__)

# Import PostgreSQL library conditionally
try:
    import asyncpg
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    asyncpg = None
    logger.warning("`asyncpg` not installed. PostgreSQL storage will not be available.")


class PostgresStorage(TaskStorage):
    """
    PostgreSQL storage implementation.
    
    This implementation stores task data in a PostgreSQL database,
    providing persistence across service restarts.
    """
    
    # SQL schema for tasks table
    CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS agent_tasks (
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
    
    CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON agent_tasks(status);
    CREATE INDEX IF NOT EXISTS idx_agent_tasks_created_at ON agent_tasks(created_at);
    """
    
    def __init__(self, connection_string: str):
        """
        Initialize PostgreSQL storage.
        
        Args:
            connection_string: PostgreSQL connection string
                Format: postgresql://user:password@host:port/database
        """
        if not POSTGRES_AVAILABLE:
            raise ImportError(
                "asyncpg is required for PostgreSQL storage. "
                "Install it with: pip install asyncpg"
            )
        
        self.connection_string = connection_string
        self._pool: Optional[asyncpg.Pool] = None
        self._initialized = False
        self._init_lock = asyncio.Lock()
        logger.info("Initialized PostgresStorage for task persistence")
    
    async def _ensure_initialized(self):
        """Ensure database connection pool is initialized and schema is created."""
        if self._initialized:
            return
        
        async with self._init_lock:
            # Double-check after acquiring lock
            if self._initialized:
                return
            
            if not self._pool:
                try:
                    self._pool = await asyncpg.create_pool(
                        self.connection_string,
                        min_size=2,
                        max_size=10,
                        command_timeout=60
                    )
                    logger.info("PostgreSQL connection pool created")
                except Exception as e:
                    logger.error(f"Failed to create PostgreSQL connection pool: {e}")
                    raise
            
            # Create table if not exists
            try:
                async with self._pool.acquire() as conn:
                    await conn.execute(self.CREATE_TABLE_SQL)
                    logger.info("PostgreSQL schema initialized")
            except Exception as e:
                logger.error(f"Failed to initialize PostgreSQL schema: {e}")
                raise
            
            self._initialized = True
    
    async def close(self):
        """Close the database connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._initialized = False
            logger.info("PostgreSQL connection pool closed")
    
    async def create_task(self, task_data: TaskData) -> bool:
        """
        Create a new task entry in PostgreSQL.
        
        Args:
            task_data: TaskData object containing task information
            
        Returns:
            bool: True if creation was successful
        """
        await self._ensure_initialized()
        
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO agent_tasks (
                        task_id, status, query, max_steps, final_state,
                        timestamp_dir, execution_statistics, sandbox_info,
                        request_data, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    """,
                    task_data.task_id,
                    task_data.status,
                    task_data.query,
                    task_data.max_steps,
                    task_data.final_state,
                    task_data.timestamp_dir,
                    json.dumps(task_data.execution_statistics) if task_data.execution_statistics else None,
                    json.dumps(task_data.sandbox_info) if task_data.sandbox_info else None,
                    json.dumps(task_data.request_data) if task_data.request_data else None,
                    task_data.created_at or datetime.now(),
                    task_data.updated_at or datetime.now()
                )
                logger.debug(f"Created task {task_data.task_id} in PostgreSQL")
                return True
        except asyncpg.UniqueViolationError:
            logger.warning(f"Task {task_data.task_id} already exists in PostgreSQL")
            return False
        except Exception as e:
            logger.error(f"Failed to create task {task_data.task_id} in PostgreSQL: {e}")
            return False
    
    async def get_task(self, task_id: str) -> Optional[TaskData]:
        """
        Retrieve task data by task ID from PostgreSQL.
        
        Args:
            task_id: Unique identifier for the task
            
        Returns:
            TaskData if found, None otherwise
        """
        await self._ensure_initialized()
        
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT task_id, status, query, max_steps, final_state,
                           timestamp_dir, execution_statistics, sandbox_info,
                           request_data, created_at, updated_at
                    FROM agent_tasks WHERE task_id = $1
                    """,
                    task_id
                )
                
                if not row:
                    return None
                
                # Convert row to TaskData
                task_data = TaskData(
                    task_id=row['task_id'],
                    status=row['status'],
                    query=row['query'],
                    max_steps=row['max_steps'],
                    final_state=row['final_state'],
                    timestamp_dir=row['timestamp_dir'],
                    execution_statistics=json.loads(row['execution_statistics']) if row['execution_statistics'] else None,
                    sandbox_info=json.loads(row['sandbox_info']) if row['sandbox_info'] else None,
                    request_data=json.loads(row['request_data']) if row['request_data'] else None,
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
                
                logger.debug(f"Retrieved task {task_id} from PostgreSQL")
                return task_data
        except Exception as e:
            logger.error(f"Failed to retrieve task {task_id} from PostgreSQL: {e}")
            return None
    
    async def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update task data in PostgreSQL.
        
        Args:
            task_id: Unique identifier for the task
            updates: Dictionary of fields to update
            
        Returns:
            bool: True if update was successful
        """
        await self._ensure_initialized()
        
        # Build dynamic UPDATE query based on provided fields
        set_clauses = []
        values = []
        param_idx = 1
        
        allowed_update_fields = {
            'status', 'final_state', 'timestamp_dir',
            'execution_statistics', 'sandbox_info', 'request_data'
        }
        
        for key, value in updates.items():
            if key in allowed_update_fields:
                set_clauses.append(f"{key} = ${param_idx}")
                
                # Serialize dicts to JSON for JSONB columns
                if key in ['execution_statistics', 'sandbox_info', 'request_data'] and value is not None:
                    value = json.dumps(value)
                
                values.append(value)
                param_idx += 1
        
        if not set_clauses:
            logger.warning(f"No valid fields to update for task {task_id}")
            return False
        
        # Always update the updated_at timestamp
        set_clauses.append(f"updated_at = ${param_idx}")
        values.append(datetime.now())
        param_idx += 1
        
        # Add task_id as the last parameter for WHERE clause
        values.append(task_id)
        
        query = f"""
            UPDATE agent_tasks 
            SET {', '.join(set_clauses)}
            WHERE task_id = ${param_idx}
        """
        
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(query, *values)
                
                # Check if any row was updated
                updated_count = int(result.split()[-1]) if result and result.startswith("UPDATE") else 0
                if updated_count == 0:
                    logger.warning(f"Task {task_id} not found for update in PostgreSQL")
                    return False
                
                logger.debug(f"Updated task {task_id} in PostgreSQL")
                return True
        except Exception as e:
            logger.error(f"Failed to update task {task_id} in PostgreSQL: {e}")
            return False
    
    async def delete_task(self, task_id: str) -> bool:
        """
        Delete a task entry from PostgreSQL.
        
        Args:
            task_id: Unique identifier for the task
            
        Returns:
            bool: True if deletion was successful
        """
        await self._ensure_initialized()
        
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM agent_tasks WHERE task_id = $1",
                    task_id
                )
                
                deleted_count = int(result.split()[-1]) if result and result.startswith("DELETE") else 0
                if deleted_count == 0:
                    logger.warning(f"Task {task_id} not found for deletion in PostgreSQL")
                    return False
                
                logger.debug(f"Deleted task {task_id} from PostgreSQL")
                return True
        except Exception as e:
            logger.error(f"Failed to delete task {task_id} from PostgreSQL: {e}")
            return False
    
    async def list_tasks(self, 
                        status: Optional[str] = None,
                        limit: Optional[int] = None,
                        offset: int = 0) -> List[TaskData]:
        """
        List tasks with optional filtering from PostgreSQL.
        
        Args:
            status: Filter by task status (optional)
            limit: Maximum number of tasks to return (optional)
            offset: Number of tasks to skip (for pagination)
            
        Returns:
            List of TaskData objects
        """
        await self._ensure_initialized()
        
        query = """
            SELECT task_id, status, query, max_steps, final_state,
                   timestamp_dir, execution_statistics, sandbox_info,
                   request_data, created_at, updated_at
            FROM agent_tasks
        """
        
        params = []
        param_idx = 1
        
        if status:
            query += f" WHERE status = ${param_idx}"
            params.append(status)
            param_idx += 1
        
        query += " ORDER BY created_at DESC"
        
        if limit:
            query += f" LIMIT ${param_idx}"
            params.append(limit)
            param_idx += 1
        
        if offset > 0:
            query += f" OFFSET ${param_idx}"
            params.append(offset)
        
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                
                tasks = []
                for row in rows:
                    task_data = TaskData(
                        task_id=row['task_id'],
                        status=row['status'],
                        query=row['query'],
                        max_steps=row['max_steps'],
                        final_state=row['final_state'],
                        timestamp_dir=row['timestamp_dir'],
                        execution_statistics=json.loads(row['execution_statistics']) if row['execution_statistics'] else None,
                        sandbox_info=json.loads(row['sandbox_info']) if row['sandbox_info'] else None,
                        request_data=json.loads(row['request_data']) if row['request_data'] else None,
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                    tasks.append(task_data)
                
                logger.debug(f"Listed {len(tasks)} tasks from PostgreSQL")
                return tasks
        except Exception as e:
            logger.error(f"Failed to list tasks from PostgreSQL: {e}")
            return []
    
    async def count_active_tasks(self) -> int:
        """
        Count tasks with status 'pending' or 'running' in PostgreSQL.
        
        Returns:
            Number of active tasks
        """
        await self._ensure_initialized()
        
        try:
            async with self._pool.acquire() as conn:
                count = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM agent_tasks 
                    WHERE status IN ('pending', 'running')
                    """
                )
                logger.debug(f"Counted {count} active tasks in PostgreSQL")
                return count or 0
        except Exception as e:
            logger.error(f"Failed to count active tasks in PostgreSQL: {e}")
            return 0
    
    async def cleanup_old_tasks(self, older_than_days: int) -> int:
        """
        Clean up old task records from PostgreSQL.
        
        Args:
            older_than_days: Delete tasks older than this many days
            
        Returns:
            Number of tasks deleted
        """
        await self._ensure_initialized()
        
        try:
            cutoff_date = datetime.now() - timedelta(days=older_than_days)
            
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM agent_tasks 
                    WHERE created_at < $1 
                    AND status IN ('finished', 'error', 'cancelled')
                    """,
                    cutoff_date
                )
                
                # Parse result to get number of deleted rows
                deleted_count = int(result.split()[-1]) if result else 0
                
                logger.info(f"Cleaned up {deleted_count} old tasks from PostgreSQL")
                return deleted_count
        except Exception as e:
            logger.error(f"Failed to cleanup old tasks from PostgreSQL: {e}")
            return 0
