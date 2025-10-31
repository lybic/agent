"""
Tests for storage implementations (memory and postgres).
"""

import pytest
import sys
import os
from datetime import datetime

# Add parent directory to path for direct import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from gui_agents.storage.base import TaskData
from gui_agents.storage.memory_storage import MemoryStorage
from gui_agents.storage.factory import create_storage


class TestTaskData:
    """Test TaskData dataclass"""
    
    def test_task_data_creation(self):
        """Test creating a TaskData instance"""
        task_data = TaskData(
            task_id="test-123",
            status="pending",
            query="Test query",
            max_steps=50
        )
        
        assert task_data.task_id == "test-123"
        assert task_data.status == "pending"
        assert task_data.query == "Test query"
        assert task_data.max_steps == 50
        assert task_data.final_state is None
        assert task_data.execution_statistics is None
    
    def test_task_data_to_dict(self):
        """Test converting TaskData to dictionary"""
        created_at = datetime.now()
        task_data = TaskData(
            task_id="test-123",
            status="pending",
            query="Test query",
            max_steps=50,
            created_at=created_at
        )
        
        data_dict = task_data.to_dict()
        assert data_dict["task_id"] == "test-123"
        assert data_dict["status"] == "pending"
        assert isinstance(data_dict["created_at"], str)  # Should be ISO format
    
    def test_task_data_from_dict(self):
        """Test creating TaskData from dictionary"""
        data_dict = {
            "task_id": "test-123",
            "status": "pending",
            "query": "Test query",
            "max_steps": 50,
            "created_at": "2025-10-30T10:00:00",
            "updated_at": None,
            "final_state": None,
            "timestamp_dir": None,
            "execution_statistics": None,
            "sandbox_info": None,
            "request_data": None
        }
        
        task_data = TaskData.from_dict(data_dict)
        assert task_data.task_id == "test-123"
        assert task_data.status == "pending"
        assert isinstance(task_data.created_at, datetime)


class TestMemoryStorage:
    """Test MemoryStorage implementation"""
    
    @pytest.fixture
    def storage(self):
        """Create a MemoryStorage instance for testing"""
        return MemoryStorage()
    
    @pytest.mark.asyncio
    async def test_create_task(self, storage):
        """Test creating a task in memory storage"""
        task_data = TaskData(
            task_id="test-123",
            status="pending",
            query="Test query",
            max_steps=50
        )
        
        result = await storage.create_task(task_data)
        assert result is True
        
        # Verify task was created
        retrieved = await storage.get_task("test-123")
        assert retrieved is not None
        assert retrieved.task_id == "test-123"
        assert retrieved.created_at is not None
    
    @pytest.mark.asyncio
    async def test_create_duplicate_task(self, storage):
        """Test that creating duplicate task fails"""
        task_data = TaskData(
            task_id="test-123",
            status="pending",
            query="Test query",
            max_steps=50
        )
        
        # Create first time
        await storage.create_task(task_data)
        
        # Try to create again
        result = await storage.create_task(task_data)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, storage):
        """Test getting a task that doesn't exist"""
        result = await storage.get_task("nonexistent")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_update_task(self, storage):
        """Test updating a task"""
        task_data = TaskData(
            task_id="test-123",
            status="pending",
            query="Test query",
            max_steps=50
        )
        
        await storage.create_task(task_data)
        
        # Update status
        result = await storage.update_task("test-123", {"status": "running"})
        assert result is True
        
        # Verify update
        updated = await storage.get_task("test-123")
        assert updated.status == "running"
    
    @pytest.mark.asyncio
    async def test_update_nonexistent_task(self, storage):
        """Test updating a task that doesn't exist"""
        result = await storage.update_task("nonexistent", {"status": "running"})
        assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_task(self, storage):
        """Test deleting a task"""
        task_data = TaskData(
            task_id="test-123",
            status="pending",
            query="Test query",
            max_steps=50
        )
        
        await storage.create_task(task_data)
        
        # Delete task
        result = await storage.delete_task("test-123")
        assert result is True
        
        # Verify deletion
        retrieved = await storage.get_task("test-123")
        assert retrieved is None
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_task(self, storage):
        """Test deleting a task that doesn't exist"""
        result = await storage.delete_task("nonexistent")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_list_tasks(self, storage):
        """Test listing tasks"""
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
        assert len(all_tasks) == 5
        
        # List only pending tasks
        pending_tasks = await storage.list_tasks(status="pending")
        assert len(pending_tasks) == 3
        
        # List with limit
        limited_tasks = await storage.list_tasks(limit=2)
        assert len(limited_tasks) == 2
    
    @pytest.mark.asyncio
    async def test_count_active_tasks(self, storage):
        """Test counting active tasks"""
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
        assert count == 3  # 2 pending + 1 running
    
    @pytest.mark.asyncio
    async def test_cleanup_old_tasks(self, storage):
        """Test cleaning up old tasks"""
        # Create some old finished tasks
        for i in range(3):
            task_data = TaskData(
                task_id=f"test-{i}",
                status="finished",
                query=f"Test query {i}",
                max_steps=50
            )
            await storage.create_task(task_data)
            # Manually set old created_at date
            task = await storage.get_task(f"test-{i}")
            task.created_at = datetime(2020, 1, 1)
        
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
        assert deleted_count == 3
        
        # Verify recent task still exists
        recent = await storage.get_task("recent")
        assert recent is not None
    
    @pytest.mark.asyncio
    async def test_execution_statistics(self, storage):
        """Test storing and retrieving execution statistics"""
        task_data = TaskData(
            task_id="test-123",
            status="pending",
            query="Test query",
            max_steps=50
        )
        
        await storage.create_task(task_data)
        
        # Update with execution statistics
        stats = {
            "steps": 10,
            "duration_seconds": 120.5,
            "input_tokens": 1000,
            "output_tokens": 500,
            "total_tokens": 1500,
            "cost": 0.05,
            "currency_symbol": "￥"
        }
        
        await storage.update_task("test-123", {"execution_statistics": stats})
        
        # Verify statistics
        updated = await storage.get_task("test-123")
        assert updated.execution_statistics == stats


class TestStorageFactory:
    """Test storage factory"""
    
    def test_create_memory_storage(self):
        """Test creating memory storage via factory"""
        storage = create_storage(backend="memory")
        assert isinstance(storage, MemoryStorage)
    
    def test_create_postgres_storage_without_connection_string(self):
        """Test that creating postgres storage without connection string raises error"""
        with pytest.raises(ValueError, match="PostgreSQL connection string is required"):
            create_storage(backend="postgres")
    
    def test_invalid_backend(self):
        """Test that invalid backend raises error"""
        with pytest.raises(ValueError, match="Invalid storage backend"):
            create_storage(backend="invalid")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
