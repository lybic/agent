#!/usr/bin/env python3
"""
Standalone test script for PostgreSQL storage implementation.
This script tests the PostgreSQL storage layer with mocked database connections.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

# Add the storage directory to path
storage_dir = Path(__file__).parent.parent / "gui_agents" / "storage"
sys.path.insert(0, str(storage_dir.parent))

# Import storage modules
from storage.base import TaskData
from storage.postgres_storage import PostgresStorage


class MockAsyncpgPool:
    """Mock asyncpg connection pool"""
    
    def __init__(self):
        self.closed = False
        self._data = {}
    
    def acquire(self):
        """Return a context manager that yields a mock connection"""
        return MockConnectionContext(MockAsyncpgConnection(self._data))
    
    async def close(self):
        """Mock close method"""
        self.closed = True


class MockConnectionContext:
    """Mock connection context manager"""
    
    def __init__(self, connection):
        self.connection = connection
    
    async def __aenter__(self):
        return self.connection
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class MockAsyncpgConnection:
    """Mock asyncpg connection"""
    
    def __init__(self, data_store):
        self._data = data_store
    
    async def execute(self, query: str, *args):
        """Mock execute method"""
        # Handle CREATE TABLE
        if "CREATE TABLE" in query or "CREATE INDEX" in query:
            return None
        
        # Handle INSERT
        if "INSERT INTO agent_tasks" in query:
            task_id = args[0]
            self._data[task_id] = {
                'task_id': args[0],
                'status': args[1],
                'query': args[2],
                'max_steps': args[3],
                'final_state': args[4] if len(args) > 4 else None,
                'timestamp_dir': args[5] if len(args) > 5 else None,
                'execution_statistics': args[6] if len(args) > 6 else None,
                'sandbox_info': args[7] if len(args) > 7 else None,
                'request_data': args[8] if len(args) > 8 else None,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            return None
        
        # Handle UPDATE
        if "UPDATE agent_tasks" in query:
            # Simple mock - just return success
            return None
        
        # Handle DELETE
        if "DELETE FROM agent_tasks" in query:
            if "WHERE created_at <" in query:
                # Cleanup old tasks
                cutoff_date = args[0]
                deleted = 0
                to_delete = []
                for task_id, task_data in self._data.items():
                    if task_data.get('created_at', datetime.now()) < cutoff_date:
                        if task_data.get('status') in ['finished', 'error', 'cancelled']:
                            to_delete.append(task_id)
                            deleted += 1
                for task_id in to_delete:
                    del self._data[task_id]
                return f"DELETE {deleted}"
            else:
                # Delete specific task
                task_id = args[0] if args else None
                if task_id in self._data:
                    del self._data[task_id]
                    return "DELETE 1"
                return "DELETE 0"
        
        return None
    
    async def fetchrow(self, query: str, *args):
        """Mock fetchrow method"""
        if "SELECT" in query and "WHERE task_id" in query:
            task_id = args[0] if args else None
            return self._data.get(task_id)
        return None
    
    async def fetch(self, query: str, *args):
        """Mock fetch method"""
        if "SELECT" in query:
            tasks = list(self._data.values())
            
            # Handle status filter
            if "WHERE status" in query and args:
                status = args[0]
                tasks = [t for t in tasks if t.get('status') == status]
            
            # Handle LIMIT
            if "LIMIT" in query and args:
                limit = args[-2] if "OFFSET" in query else args[-1]
                offset = args[-1] if "OFFSET" in query else 0
                tasks = tasks[offset:offset+limit]
            
            return tasks
        return []
    
    async def fetchval(self, query: str, *args):
        """Mock fetchval method"""
        if "COUNT(*)" in query:
            if "WHERE status IN" in query:
                # Count active tasks
                count = sum(1 for task in self._data.values()
                           if task.get('status') in ['pending', 'running'])
                return count
        return 0


async def test_postgres_storage_create():
    """Test creating tasks in PostgreSQL storage"""
    print("\nTesting PostgresStorage - create task...")
    
    with patch('storage.postgres_storage.POSTGRES_AVAILABLE', True):
        with patch('storage.postgres_storage.asyncpg') as mock_asyncpg:
            mock_pool = MockAsyncpgPool()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)
            
            storage = PostgresStorage("postgresql://user:pass@localhost/test")
            await storage._ensure_initialized()
            
            task_data = TaskData(
                task_id="test-123",
                status="pending",
                query="Test query",
                max_steps=50
            )
            
            result = await storage.create_task(task_data)
            assert result is True, "Failed to create task"
            
            # Verify task was created
            retrieved = await storage.get_task("test-123")
            assert retrieved is not None, "Task not found after creation"
            assert retrieved.task_id == "test-123"
            assert retrieved.status == "pending"
            
            await storage.close()
    
    print("✓ Create task test passed")


async def test_postgres_storage_update():
    """Test updating tasks in PostgreSQL storage"""
    print("\nTesting PostgresStorage - update task...")
    
    with patch('storage.postgres_storage.POSTGRES_AVAILABLE', True):
        with patch('storage.postgres_storage.asyncpg') as mock_asyncpg:
            mock_pool = MockAsyncpgPool()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)
            
            storage = PostgresStorage("postgresql://user:pass@localhost/test")
            await storage._ensure_initialized()
            
            task_data = TaskData(
                task_id="test-123",
                status="pending",
                query="Test query",
                max_steps=50
            )
            
            await storage.create_task(task_data)
            
            # Update status
            result = await storage.update_task("test-123", {"status": "running"})
            assert result is True, "Failed to update task"
            
            await storage.close()
    
    print("✓ Update task test passed")


async def test_postgres_storage_delete():
    """Test deleting tasks from PostgreSQL storage"""
    print("\nTesting PostgresStorage - delete task...")
    
    with patch('storage.postgres_storage.POSTGRES_AVAILABLE', True):
        with patch('storage.postgres_storage.asyncpg') as mock_asyncpg:
            mock_pool = MockAsyncpgPool()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)
            
            storage = PostgresStorage("postgresql://user:pass@localhost/test")
            await storage._ensure_initialized()
            
            task_data = TaskData(
                task_id="test-123",
                status="pending",
                query="Test query",
                max_steps=50
            )
            
            await storage.create_task(task_data)
            
            # Delete task
            result = await storage.delete_task("test-123")
            assert result is True, "Failed to delete task"
            
            # Verify deletion
            retrieved = await storage.get_task("test-123")
            assert retrieved is None, "Task still exists after deletion"
            
            await storage.close()
    
    print("✓ Delete task test passed")


async def test_postgres_storage_list():
    """Test listing tasks from PostgreSQL storage"""
    print("\nTesting PostgresStorage - list tasks...")
    
    with patch('storage.postgres_storage.POSTGRES_AVAILABLE', True):
        with patch('storage.postgres_storage.asyncpg') as mock_asyncpg:
            mock_pool = MockAsyncpgPool()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)
            
            storage = PostgresStorage("postgresql://user:pass@localhost/test")
            await storage._ensure_initialized()
            
            # Create multiple tasks
            for i in range(5):
                task_data = TaskData(
                    task_id=f"test-{i}",
                    status="pending" if i < 3 else "finished",
                    query=f"Test query {i}",
                    max_steps=50
                )
                await storage.create_task(task_data)
            
            # List all tasks
            all_tasks = await storage.list_tasks()
            assert len(all_tasks) == 5, f"Expected 5 tasks, got {len(all_tasks)}"
            
            # List only pending tasks
            pending_tasks = await storage.list_tasks(status="pending")
            assert len(pending_tasks) == 3, f"Expected 3 pending tasks, got {len(pending_tasks)}"
            
            await storage.close()
    
    print("✓ List tasks test passed")


async def test_postgres_storage_count_active():
    """Test counting active tasks"""
    print("\nTesting PostgresStorage - count active tasks...")
    
    with patch('storage.postgres_storage.POSTGRES_AVAILABLE', True):
        with patch('storage.postgres_storage.asyncpg') as mock_asyncpg:
            mock_pool = MockAsyncpgPool()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)
            
            storage = PostgresStorage("postgresql://user:pass@localhost/test")
            await storage._ensure_initialized()
            
            # Create tasks with different statuses
            statuses = ["pending", "running", "finished", "pending", "error"]
            for i, status in enumerate(statuses):
                task_data = TaskData(
                    task_id=f"test-{i}",
                    status=status,
                    query=f"Test query {i}",
                    max_steps=50
                )
                await storage.create_task(task_data)
            
            # Count active tasks (pending + running)
            count = await storage.count_active_tasks()
            assert count == 3, f"Expected 3 active tasks, got {count}"  # 2 pending + 1 running
            
            await storage.close()
    
    print("✓ Count active tasks test passed")


async def test_postgres_storage_cleanup():
    """Test cleaning up old tasks"""
    print("\nTesting PostgresStorage - cleanup old tasks...")
    
    with patch('storage.postgres_storage.POSTGRES_AVAILABLE', True):
        with patch('storage.postgres_storage.asyncpg') as mock_asyncpg:
            mock_pool = MockAsyncpgPool()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)
            
            storage = PostgresStorage("postgresql://user:pass@localhost/test")
            await storage._ensure_initialized()
            
            # Create some old finished tasks
            for i in range(3):
                task_data = TaskData(
                    task_id=f"test-{i}",
                    status="finished",
                    query=f"Test query {i}",
                    max_steps=50
                )
                await storage.create_task(task_data)
            
            # Manually set old created_at date in mock data
            for task_id in mock_pool._data.keys():
                mock_pool._data[task_id]['created_at'] = datetime(2020, 1, 1)
            
            # Create a recent task
            recent_task = TaskData(
                task_id="recent",
                status="finished",
                query="Recent query",
                max_steps=50
            )
            await storage.create_task(recent_task)
            
            # Cleanup old tasks
            deleted_count = await storage.cleanup_old_tasks(older_than_days=30)
            assert deleted_count == 3, f"Expected 3 deleted tasks, got {deleted_count}"
            
            # Verify recent task still exists
            recent = await storage.get_task("recent")
            assert recent is not None, "Recent task should still exist"
            
            await storage.close()
    
    print("✓ Cleanup old tasks test passed")


async def test_postgres_storage_with_json_fields():
    """Test storing and retrieving tasks with JSON fields"""
    print("\nTesting PostgresStorage - JSON fields...")
    
    with patch('storage.postgres_storage.POSTGRES_AVAILABLE', True):
        with patch('storage.postgres_storage.asyncpg') as mock_asyncpg:
            mock_pool = MockAsyncpgPool()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)
            
            storage = PostgresStorage("postgresql://user:pass@localhost/test")
            await storage._ensure_initialized()
            
            task_data = TaskData(
                task_id="test-123",
                status="finished",
                query="Test query",
                max_steps=50,
                execution_statistics={
                    "steps": 10,
                    "duration_seconds": 120.5,
                    "cost": 0.05
                },
                sandbox_info={
                    "sandbox_id": "sb-123",
                    "provider": "lybic"
                },
                request_data={
                    "user": "test_user",
                    "priority": "high"
                }
            )
            
            result = await storage.create_task(task_data)
            assert result is True, "Failed to create task with JSON fields"
            
            # Note: In real implementation, retrieving would deserialize JSON
            # In this mock, we're just verifying the storage works
            
            await storage.close()
    
    print("✓ JSON fields test passed")


async def test_postgres_storage_initialization():
    """Test PostgresStorage initialization and connection pooling"""
    print("\nTesting PostgresStorage - initialization...")
    
    with patch('storage.postgres_storage.POSTGRES_AVAILABLE', True):
        with patch('storage.postgres_storage.asyncpg') as mock_asyncpg:
            mock_pool = MockAsyncpgPool()
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)
            
            storage = PostgresStorage("postgresql://user:pass@localhost/test")
            assert storage._initialized is False
            
            await storage._ensure_initialized()
            assert storage._initialized is True
            
            # Second call should not create a new pool
            await storage._ensure_initialized()
            mock_asyncpg.create_pool.assert_called_once()
            
            await storage.close()
            assert storage._initialized is False
            assert mock_pool.closed is True
    
    print("✓ Initialization test passed")


async def test_postgres_storage_error_handling():
    """Test error handling in PostgresStorage"""
    print("\nTesting PostgresStorage - error handling...")
    
    with patch('storage.postgres_storage.POSTGRES_AVAILABLE', True):
        with patch('storage.postgres_storage.asyncpg') as mock_asyncpg:
            # Mock a failing connection
            mock_asyncpg.create_pool = AsyncMock(side_effect=Exception("Connection failed"))
            
            storage = PostgresStorage("postgresql://user:pass@localhost/test")
            
            try:
                await storage._ensure_initialized()
                assert False, "Should have raised exception"
            except Exception as e:
                assert "Connection failed" in str(e)
    
    print("✓ Error handling test passed")


async def main():
    """Run all tests"""
    print("="*60)
    print("Running PostgreSQL Storage Layer Tests (with mocked DB)")
    print("="*60)
    
    try:
        await test_postgres_storage_initialization()
        await test_postgres_storage_create()
        await test_postgres_storage_update()
        await test_postgres_storage_delete()
        await test_postgres_storage_list()
        await test_postgres_storage_count_active()
        await test_postgres_storage_cleanup()
        await test_postgres_storage_with_json_fields()
        await test_postgres_storage_error_handling()
        
        print("\n" + "="*60)
        print("✓ All tests passed!")
        print("="*60)
        return 0
    except Exception as e:
        print("\n" + "="*60)
        print(f"✗ Tests failed: {e}")
        print("="*60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
