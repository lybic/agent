"""
In-memory storage implementation for task persistence.

This implementation stores task data in memory (Python dictionary).
Data is lost when the service restarts.
"""
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import logging

from .base import TaskStorage, TaskData

logger = logging.getLogger(__name__)


class MemoryStorage(TaskStorage):
    """
    In-memory storage implementation.
    
    This implementation provides the default lightweight behavior where
    task data is stored in memory and lost upon service restart.
    """
    
    def __init__(self):
        """Initialize in-memory storage with empty dictionary."""
        self._tasks: Dict[str, TaskData] = {}
        self._lock = asyncio.Lock()
        logger.info("Initialized MemoryStorage for task persistence")
    
    async def create_task(self, task_data: TaskData) -> bool:
        """
        Create a new task entry in memory.
        
        Args:
            task_data: TaskData object containing task information
            
        Returns:
            bool: True if creation was successful
        """
        async with self._lock:
            if task_data.task_id in self._tasks:
                logger.warning(f"Task {task_data.task_id} already exists")
                return False
            
            # Set timestamps
            task_data.created_at = datetime.now()
            task_data.updated_at = datetime.now()
            
            self._tasks[task_data.task_id] = task_data
            logger.debug(f"Created task {task_data.task_id} in memory")
            return True
    
    async def get_task(self, task_id: str) -> Optional[TaskData]:
        """
        Retrieve task data by task ID from memory.
        
        Args:
            task_id: Unique identifier for the task
            
        Returns:
            TaskData if found, None otherwise
        """
        async with self._lock:
            task_data = self._tasks.get(task_id)
            if task_data:
                logger.debug(f"Retrieved task {task_id} from memory")
            return task_data
    
    async def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update task data in memory.
        
        Args:
            task_id: Unique identifier for the task
            updates: Dictionary of fields to update
            
        Returns:
            bool: True if update was successful
        """
        async with self._lock:
            task_data = self._tasks.get(task_id)
            if not task_data:
                logger.warning(f"Task {task_id} not found for update")
                return False
            
            # Update fields
            for key, value in updates.items():
                if hasattr(task_data, key):
                    setattr(task_data, key, value)
            
            # Update timestamp
            task_data.updated_at = datetime.now()
            
            logger.debug(f"Updated task {task_id} in memory")
            return True
    
    async def delete_task(self, task_id: str) -> bool:
        """
        Delete a task entry from memory.
        
        Args:
            task_id: Unique identifier for the task
            
        Returns:
            bool: True if deletion was successful
        """
        async with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                logger.debug(f"Deleted task {task_id} from memory")
                return True
            else:
                logger.warning(f"Task {task_id} not found for deletion")
                return False
    
    async def list_tasks(self, 
                        status: Optional[str] = None,
                        limit: Optional[int] = None,
                        offset: int = 0) -> List[TaskData]:
        """
        List tasks with optional filtering from memory.
        
        Args:
            status: Filter by task status (optional)
            limit: Maximum number of tasks to return (optional)
            offset: Number of tasks to skip (for pagination)
            
        Returns:
            List of TaskData objects
        """
        async with self._lock:
            tasks = list(self._tasks.values())
            
            # Filter by status if provided
            if status:
                tasks = [t for t in tasks if t.status == status]
            
            # Sort by created_at descending
            tasks.sort(key=lambda t: t.created_at or datetime.min, reverse=True)
            
            # Apply pagination
            tasks = tasks[offset:]
            if limit:
                tasks = tasks[:limit]
            
            logger.debug(f"Listed {len(tasks)} tasks from memory")
            return tasks
    
    async def count_active_tasks(self) -> int:
        """
        Count tasks with status 'pending' or 'running' in memory.
        
        Returns:
            Number of active tasks
        """
        async with self._lock:
            active_count = sum(
                1 for task in self._tasks.values() 
                if task.status in ['pending', 'running']
            )
            logger.debug(f"Counted {active_count} active tasks in memory")
            return active_count
    
    async def cleanup_old_tasks(self, older_than_days: int) -> int:
        """
        Clean up old task records from memory.
        
        Args:
            older_than_days: Delete tasks older than this many days
            
        Returns:
            Number of tasks deleted
        """
        async with self._lock:
            cutoff_date = datetime.now() - timedelta(days=older_than_days)
            tasks_to_delete = [
                task_id for task_id, task_data in self._tasks.items()
                if task_data.created_at and task_data.created_at < cutoff_date
                and task_data.status in ['finished', 'error', 'cancelled']
            ]
            
            for task_id in tasks_to_delete:
                del self._tasks[task_id]
            
            logger.info(f"Cleaned up {len(tasks_to_delete)} old tasks from memory")
            return len(tasks_to_delete)
