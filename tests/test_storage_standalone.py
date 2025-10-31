#!/usr/bin/env python3
"""
Standalone test script for storage implementations.
This script tests the storage layer without importing the full gui_agents package.
"""

import asyncio
import sys
from pathlib import Path

# Add the storage directory to path
storage_dir = Path(__file__).parent.parent / "gui_agents" / "storage"
sys.path.insert(0, str(storage_dir.parent))

# Import storage modules
from storage.base import TaskData
from storage.memory_storage import MemoryStorage


async def test_task_data():
    """Test TaskData creation and serialization"""
    print("Testing TaskData...")
    
    task_data = TaskData(
        task_id="test-123",
        status="pending",
        query="Test query",
        max_steps=50
    )
    
    assert task_data.task_id == "test-123"
    assert task_data.status == "pending"
    
    # Test to_dict
    data_dict = task_data.to_dict()
    assert data_dict["task_id"] == "test-123"
    
    # Test from_dict
    restored = TaskData.from_dict(data_dict)
    assert restored.task_id == "test-123"
    
    print("✓ TaskData tests passed")


async def test_memory_storage_create():
    """Test creating tasks in memory storage"""
    print("\nTesting MemoryStorage - create task...")
    
    storage = MemoryStorage()
    
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
    assert retrieved.created_at is not None
    
    print("✓ Create task test passed")


async def test_memory_storage_update():
    """Test updating tasks in memory storage"""
    print("\nTesting MemoryStorage - update task...")
    
    storage = MemoryStorage()
    
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
    
    # Verify update
    updated = await storage.get_task("test-123")
    assert updated.status == "running", "Status not updated"
    
    print("✓ Update task test passed")


async def test_memory_storage_delete():
    """Test deleting tasks from memory storage"""
    print("\nTesting MemoryStorage - delete task...")
    
    storage = MemoryStorage()
    
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
    
    print("✓ Delete task test passed")


async def test_memory_storage_list():
    """Test listing tasks from memory storage"""
    print("\nTesting MemoryStorage - list tasks...")
    
    storage = MemoryStorage()
    
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
    
    print("✓ List tasks test passed")


async def test_memory_storage_count_active():
    """Test counting active tasks"""
    print("\nTesting MemoryStorage - count active tasks...")
    
    storage = MemoryStorage()
    
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
    
    print("✓ Count active tasks test passed")


async def test_memory_storage_execution_statistics():
    """Test storing and retrieving execution statistics"""
    print("\nTesting MemoryStorage - execution statistics...")
    
    storage = MemoryStorage()
    
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
    assert updated.execution_statistics == stats, "Execution statistics not stored correctly"
    
    print("✓ Execution statistics test passed")


async def main():
    """Run all tests"""
    print("="*60)
    print("Running Storage Layer Tests")
    print("="*60)
    
    try:
        await test_task_data()
        await test_memory_storage_create()
        await test_memory_storage_update()
        await test_memory_storage_delete()
        await test_memory_storage_list()
        await test_memory_storage_count_active()
        await test_memory_storage_execution_statistics()
        
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
