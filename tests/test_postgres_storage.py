"""
Tests for PostgreSQL storage implementation with mocked database connections.
"""

import pytest
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Any, Dict

# Add parent directory to path for direct import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from gui_agents.storage.base import TaskData
from gui_agents.storage.postgres_storage import PostgresStorage


class MockAsyncpgPool:
    """Mock asyncpg connection pool"""
    
    def __init__(self):
        self.closed = False
        self._connections = []
    
    def acquire(self):
        """Return a context manager that yields a mock connection"""
        return MockConnectionContext(MockAsyncpgConnection())
    
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
    
    def __init__(self):
        self.executed_queries = []
        self._data = {}
    
    async def execute(self, query: str, *args):
        """Mock execute method"""
        self.executed_queries.append((query, args))
        
        # Return DELETE result format
        if query.strip().startswith("DELETE"):
            return "DELETE 3"
        return None
    
    async def fetchrow(self, query: str, *args):
        """Mock fetchrow method"""
        self.executed_queries.append((query, args))
        
        # Mock data for testing
        if "SELECT" in query and "WHERE task_id" in query:
            task_id = args[0] if args else None
            if task_id in self._data:
                return self._data[task_id]
        return None
    
    async def fetch(self, query: str, *args):
        """Mock fetch method"""
        self.executed_queries.append((query, args))
        
        # Return list of rows
        if "SELECT" in query:
            return list(self._data.values())
        return []
    
    async def fetchval(self, query: str, *args):
        """Mock fetchval method"""
        self.executed_queries.append((query, args))
        
        # Count active tasks
        if "COUNT(*)" in query:
            count = sum(1 for row in self._data.values() 
                       if row.get('status') in ['pending', 'running'])
            return count
        return 0
    
    def set_data(self, task_id: str, data: Dict[str, Any]):
        """Set mock data for a task"""
        self._data[task_id] = data
    
    def clear_data(self):
        """Clear all mock data"""
        self._data.clear()


class TestPostgresStorage:
    """Test PostgresStorage implementation with mocked database"""
    
    @pytest.fixture
    def mock_pool(self):
        """Create a mock connection pool"""
        return MockAsyncpgPool()
    
    @pytest.fixture
    async def storage(self, mock_pool):
        """Create a PostgresStorage instance with mocked pool"""
        with patch('gui_agents.storage.postgres_storage.POSTGRES_AVAILABLE', True):
            with patch('gui_agents.storage.postgres_storage.asyncpg') as mock_asyncpg:
                mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)
                
                storage = PostgresStorage("postgresql://user:pass@localhost/test")
                await storage._ensure_initialized()
                
                yield storage
                
                await storage.close()
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test PostgresStorage initialization"""
        with patch('gui_agents.storage.postgres_storage.POSTGRES_AVAILABLE', True):
            with patch('gui_agents.storage.postgres_storage.asyncpg') as mock_asyncpg:
                mock_pool = AsyncMock()
                mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)
                
                storage = PostgresStorage("postgresql://user:pass@localhost/test")
                assert storage.connection_string == "postgresql://user:pass@localhost/test"
                assert storage._initialized is False
    
    @pytest.mark.asyncio
    async def test_initialization_without_asyncpg(self):
        """Test that initialization fails without asyncpg"""
        with patch('gui_agents.storage.postgres_storage.POSTGRES_AVAILABLE', False):
            with pytest.raises(ImportError, match="asyncpg is required"):
                PostgresStorage("postgresql://user:pass@localhost/test")
    
    @pytest.mark.asyncio
    async def test_ensure_initialized(self):
        """Test that _ensure_initialized creates pool and schema"""
        with patch('gui_agents.storage.postgres_storage.POSTGRES_AVAILABLE', True):
            with patch('gui_agents.storage.postgres_storage.asyncpg') as mock_asyncpg:
                mock_pool = MockAsyncpgPool()
                mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)
                
                storage = PostgresStorage("postgresql://user:pass@localhost/test")
                assert storage._initialized is False
                
                await storage._ensure_initialized()
                
                assert storage._initialized is True
                assert storage._pool is not None
                mock_asyncpg.create_pool.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_task(self, storage):
        """Test creating a task in PostgreSQL storage"""
        task_data = TaskData(
            task_id="test-123",
            status="pending",
            query="Test query",
            max_steps=50
        )
        
        # Mock the connection to track execute calls
        mock_conn = MockAsyncpgConnection()
        with patch.object(storage._pool, 'acquire', return_value=MockConnectionContext(mock_conn)):
            result = await storage.create_task(task_data)
            assert result is True
            
            # Verify INSERT query was executed
            assert len(mock_conn.executed_queries) == 1
            query, args = mock_conn.executed_queries[0]
            assert "INSERT INTO agent_tasks" in query
            assert args[0] == "test-123"
            assert args[1] == "pending"
            assert args[2] == "Test query"
            assert args[3] == 50
    
    @pytest.mark.asyncio
    async def test_create_task_with_full_data(self, storage):
        """Test creating a task with all fields populated"""
        task_data = TaskData(
            task_id="test-123",
            status="finished",
            query="Test query",
            max_steps=50,
            final_state="success",
            timestamp_dir="/tmp/timestamps",
            execution_statistics={"steps": 10, "cost": 0.05},
            sandbox_info={"sandbox_id": "sb-123"},
            request_data={"user": "test"}
        )
        
        mock_conn = MockAsyncpgConnection()
        with patch.object(storage._pool, 'acquire', return_value=MockConnectionContext(mock_conn)):
            result = await storage.create_task(task_data)
            assert result is True
            
            # Verify all fields were included
            query, args = mock_conn.executed_queries[0]
            assert "INSERT INTO agent_tasks" in query
            assert args[4] == "success"
            assert args[5] == "/tmp/timestamps"
    
    @pytest.mark.asyncio
    async def test_create_task_error(self, storage):
        """Test error handling when creating a task fails"""
        task_data = TaskData(
            task_id="test-123",
            status="pending",
            query="Test query",
            max_steps=50
        )
        
        # Mock connection that raises exception
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("Database error"))
        
        with patch.object(storage._pool, 'acquire', return_value=MockConnectionContext(mock_conn)):
            result = await storage.create_task(task_data)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_task(self, storage):
        """Test retrieving a task from PostgreSQL storage"""
        # Mock data to return
        mock_data = {
            'task_id': 'test-123',
            'status': 'pending',
            'query': 'Test query',
            'max_steps': 50,
            'final_state': None,
            'timestamp_dir': None,
            'execution_statistics': None,
            'sandbox_info': None,
            'request_data': None,
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        mock_conn = MockAsyncpgConnection()
        mock_conn.set_data('test-123', mock_data)
        
        with patch.object(storage._pool, 'acquire', return_value=MockConnectionContext(mock_conn)):
            result = await storage.get_task("test-123")
            
            assert result is not None
            assert result.task_id == "test-123"
            assert result.status == "pending"
            assert result.query == "Test query"
            assert result.max_steps == 50
            
            # Verify SELECT query was executed
            assert len(mock_conn.executed_queries) == 1
            query, args = mock_conn.executed_queries[0]
            assert "SELECT" in query
            assert "WHERE task_id" in query
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, storage):
        """Test getting a task that doesn't exist"""
        mock_conn = MockAsyncpgConnection()
        
        with patch.object(storage._pool, 'acquire', return_value=MockConnectionContext(mock_conn)):
            result = await storage.get_task("nonexistent")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_task_with_json_fields(self, storage):
        """Test retrieving a task with JSON fields"""
        import json
        
        mock_data = {
            'task_id': 'test-123',
            'status': 'finished',
            'query': 'Test query',
            'max_steps': 50,
            'final_state': 'success',
            'timestamp_dir': '/tmp/test',
            'execution_statistics': json.dumps({"steps": 10, "cost": 0.05}),
            'sandbox_info': json.dumps({"sandbox_id": "sb-123"}),
            'request_data': json.dumps({"user": "test"}),
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        mock_conn = MockAsyncpgConnection()
        mock_conn.set_data('test-123', mock_data)
        
        with patch.object(storage._pool, 'acquire', return_value=MockConnectionContext(mock_conn)):
            result = await storage.get_task("test-123")
            
            assert result is not None
            assert result.execution_statistics == {"steps": 10, "cost": 0.05}
            assert result.sandbox_info == {"sandbox_id": "sb-123"}
            assert result.request_data == {"user": "test"}
    
    @pytest.mark.asyncio
    async def test_update_task(self, storage):
        """Test updating a task"""
        mock_conn = MockAsyncpgConnection()
        
        with patch.object(storage._pool, 'acquire', return_value=MockConnectionContext(mock_conn)):
            updates = {"status": "running", "final_state": "in_progress"}
            result = await storage.update_task("test-123", updates)
            
            assert result is True
            
            # Verify UPDATE query was executed
            assert len(mock_conn.executed_queries) == 1
            query, args = mock_conn.executed_queries[0]
            assert "UPDATE agent_tasks" in query
            assert "SET" in query
            assert "WHERE task_id" in query
    
    @pytest.mark.asyncio
    async def test_update_task_with_json_fields(self, storage):
        """Test updating a task with JSON fields"""
        mock_conn = MockAsyncpgConnection()
        
        with patch.object(storage._pool, 'acquire', return_value=MockConnectionContext(mock_conn)):
            updates = {
                "status": "finished",
                "execution_statistics": {"steps": 15, "cost": 0.08},
                "sandbox_info": {"sandbox_id": "sb-456"}
            }
            result = await storage.update_task("test-123", updates)
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_update_nonexistent_task(self, storage):
        """Test updating a task that doesn't exist returns True (PostgreSQL behavior)"""
        mock_conn = MockAsyncpgConnection()
        
        with patch.object(storage._pool, 'acquire', return_value=MockConnectionContext(mock_conn)):
            result = await storage.update_task("nonexistent", {"status": "running"})
            # PostgreSQL storage returns True even if no rows updated
            assert result is True
    
    @pytest.mark.asyncio
    async def test_update_task_error(self, storage):
        """Test error handling when updating a task fails"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("Database error"))
        
        with patch.object(storage._pool, 'acquire', return_value=MockConnectionContext(mock_conn)):
            result = await storage.update_task("test-123", {"status": "running"})
            assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_task(self, storage):
        """Test deleting a task"""
        mock_conn = MockAsyncpgConnection()
        
        with patch.object(storage._pool, 'acquire', return_value=MockConnectionContext(mock_conn)):
            result = await storage.delete_task("test-123")
            
            assert result is True
            
            # Verify DELETE query was executed
            assert len(mock_conn.executed_queries) == 1
            query, args = mock_conn.executed_queries[0]
            assert "DELETE FROM agent_tasks" in query
            assert "WHERE task_id" in query
    
    @pytest.mark.asyncio
    async def test_delete_task_error(self, storage):
        """Test error handling when deleting a task fails"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("Database error"))
        
        with patch.object(storage._pool, 'acquire', return_value=MockConnectionContext(mock_conn)):
            result = await storage.delete_task("test-123")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_list_tasks(self, storage):
        """Test listing all tasks"""
        # Mock data
        mock_tasks = [
            {
                'task_id': 'test-1',
                'status': 'pending',
                'query': 'Query 1',
                'max_steps': 50,
                'final_state': None,
                'timestamp_dir': None,
                'execution_statistics': None,
                'sandbox_info': None,
                'request_data': None,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            },
            {
                'task_id': 'test-2',
                'status': 'finished',
                'query': 'Query 2',
                'max_steps': 50,
                'final_state': 'success',
                'timestamp_dir': None,
                'execution_statistics': None,
                'sandbox_info': None,
                'request_data': None,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
        ]
        
        mock_conn = MockAsyncpgConnection()
        for task in mock_tasks:
            mock_conn.set_data(task['task_id'], task)
        
        with patch.object(storage._pool, 'acquire', return_value=MockConnectionContext(mock_conn)):
            result = await storage.list_tasks()
            
            assert len(result) == 2
            assert result[0].task_id in ['test-1', 'test-2']
            
            # Verify SELECT query was executed
            assert len(mock_conn.executed_queries) == 1
            query, args = mock_conn.executed_queries[0]
            assert "SELECT" in query
            assert "ORDER BY created_at DESC" in query
    
    @pytest.mark.asyncio
    async def test_list_tasks_with_status_filter(self, storage):
        """Test listing tasks with status filter"""
        mock_conn = MockAsyncpgConnection()
        
        with patch.object(storage._pool, 'acquire', return_value=MockConnectionContext(mock_conn)):
            result = await storage.list_tasks(status="pending")
            
            # Verify WHERE clause was added
            query, args = mock_conn.executed_queries[0]
            assert "WHERE status" in query
            assert "pending" in args
    
    @pytest.mark.asyncio
    async def test_list_tasks_with_limit_offset(self, storage):
        """Test listing tasks with limit and offset"""
        mock_conn = MockAsyncpgConnection()
        
        with patch.object(storage._pool, 'acquire', return_value=MockConnectionContext(mock_conn)):
            result = await storage.list_tasks(limit=10, offset=5)
            
            # Verify LIMIT and OFFSET were added
            query, args = mock_conn.executed_queries[0]
            assert "LIMIT" in query
            assert "OFFSET" in query
            assert 10 in args
            assert 5 in args
    
    @pytest.mark.asyncio
    async def test_list_tasks_error(self, storage):
        """Test error handling when listing tasks fails"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=Exception("Database error"))
        
        with patch.object(storage._pool, 'acquire', return_value=MockConnectionContext(mock_conn)):
            result = await storage.list_tasks()
            assert result == []
    
    @pytest.mark.asyncio
    async def test_count_active_tasks(self, storage):
        """Test counting active tasks"""
        # Mock data with mixed statuses
        mock_tasks = [
            {'task_id': 'test-1', 'status': 'pending'},
            {'task_id': 'test-2', 'status': 'running'},
            {'task_id': 'test-3', 'status': 'finished'},
            {'task_id': 'test-4', 'status': 'pending'},
        ]
        
        mock_conn = MockAsyncpgConnection()
        for task in mock_tasks:
            mock_conn.set_data(task['task_id'], task)
        
        with patch.object(storage._pool, 'acquire', return_value=MockConnectionContext(mock_conn)):
            count = await storage.count_active_tasks()
            
            assert count == 3  # 2 pending + 1 running
            
            # Verify COUNT query was executed
            query, args = mock_conn.executed_queries[0]
            assert "COUNT(*)" in query
            assert "WHERE status IN" in query
    
    @pytest.mark.asyncio
    async def test_count_active_tasks_error(self, storage):
        """Test error handling when counting active tasks fails"""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=Exception("Database error"))
        
        with patch.object(storage._pool, 'acquire', return_value=MockConnectionContext(mock_conn)):
            count = await storage.count_active_tasks()
            assert count == 0
    
    @pytest.mark.asyncio
    async def test_cleanup_old_tasks(self, storage):
        """Test cleaning up old tasks"""
        mock_conn = MockAsyncpgConnection()
        
        with patch.object(storage._pool, 'acquire', return_value=MockConnectionContext(mock_conn)):
            deleted_count = await storage.cleanup_old_tasks(older_than_days=30)
            
            # Mock connection returns "DELETE 3"
            assert deleted_count == 3
            
            # Verify DELETE query with date filter was executed
            query, args = mock_conn.executed_queries[0]
            assert "DELETE FROM agent_tasks" in query
            assert "WHERE created_at <" in query
            assert "AND status IN" in query
            
            # Verify date calculation
            assert len(args) == 1
            assert isinstance(args[0], datetime)
    
    @pytest.mark.asyncio
    async def test_cleanup_old_tasks_error(self, storage):
        """Test error handling when cleanup fails"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("Database error"))
        
        with patch.object(storage._pool, 'acquire', return_value=MockConnectionContext(mock_conn)):
            deleted_count = await storage.cleanup_old_tasks(older_than_days=30)
            assert deleted_count == 0
    
    @pytest.mark.asyncio
    async def test_close_connection_pool(self, storage):
        """Test closing the connection pool"""
        await storage.close()
        
        assert storage._pool.closed is True
        assert storage._initialized is False
    
    @pytest.mark.asyncio
    async def test_concurrent_initialization(self):
        """Test that concurrent initialization only creates one pool"""
        with patch('gui_agents.storage.postgres_storage.POSTGRES_AVAILABLE', True):
            with patch('gui_agents.storage.postgres_storage.asyncpg') as mock_asyncpg:
                mock_pool = MockAsyncpgPool()
                mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)
                
                storage = PostgresStorage("postgresql://user:pass@localhost/test")
                
                # Call _ensure_initialized multiple times concurrently
                await asyncio.gather(
                    storage._ensure_initialized(),
                    storage._ensure_initialized(),
                    storage._ensure_initialized()
                )
                
                # Pool should only be created once
                mock_asyncpg.create_pool.assert_called_once()
                assert storage._initialized is True


# Import asyncio for concurrent test
import asyncio


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
