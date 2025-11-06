#!/usr/bin/env python3
"""
Test memory leak fixes in grpc_app.py, specifically for self.tasks dictionary.

This test verifies that tasks are properly cleaned up from self.tasks in various scenarios:
1. Normal task completion
2. Task cancellation
3. Early initialization failure
4. Exception during task execution
"""

import asyncio
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from gui_agents.grpc_app import AgentServicer
from gui_agents.proto import agent_pb2


class TestGrpcMemoryLeak:
    """Test cases for memory leak fixes in grpc_app.py"""

    @pytest.fixture
    def servicer(self):
        """Create a servicer instance for testing"""
        with patch('gui_agents.grpc_app.create_storage') as mock_storage:
            # Mock storage
            storage_mock = AsyncMock()
            storage_mock.count_active_tasks = AsyncMock(return_value=0)
            storage_mock.create_task = AsyncMock()
            storage_mock.update_task = AsyncMock()
            storage_mock.get_task = AsyncMock()
            mock_storage.return_value = storage_mock
            
            servicer = AgentServicer(max_concurrent_task_num=5, log_dir="test_runtime")
            servicer.storage = storage_mock
            yield servicer

    @pytest.fixture
    def mock_request(self):
        """Create a mock request for testing"""
        request = MagicMock()
        request.instruction = "Test instruction"
        request.HasField = MagicMock(return_value=True)
        
        # Mock runningConfig
        running_config = MagicMock()
        running_config.steps = 10
        running_config.mode = agent_pb2.InstanceMode.FAST
        running_config.backend = "lybic"
        
        # Mock authorizationInfo
        auth_info = MagicMock()
        auth_info.orgID = "test-org"
        auth_info.apiKey = "test-key"
        auth_info.apiEndpoint = "https://api.test.com"
        running_config.authorizationInfo = auth_info
        running_config.HasField = MagicMock(side_effect=lambda x: x == "authorizationInfo")
        
        request.runningConfig = running_config
        
        # Mock sandbox
        sandbox = MagicMock()
        sandbox.id = ""
        sandbox.shapeName = "test-shape"
        sandbox.os = agent_pb2.SandboxOS.LINUX
        request.sandbox = sandbox
        
        return request

    @pytest.mark.asyncio
    async def test_task_cleanup_on_normal_completion(self, servicer):
        """Test that tasks are cleaned up after normal completion"""
        task_id = str(uuid.uuid4())
        
        # Add a task to self.tasks
        servicer.tasks[task_id] = {
            "agent": MagicMock(),
            "queue": asyncio.Queue(),
            "future": None,
            "query": "test query",
            "max_steps": 10,
        }
        servicer.task_created_times[task_id] = asyncio.get_event_loop().time()
        servicer.task_start_times[task_id] = asyncio.get_event_loop().time()
        
        # Mock stream manager
        with patch('gui_agents.grpc_app.stream_manager') as mock_stream_manager:
            mock_stream_manager.register_task = AsyncMock()
            mock_stream_manager.add_message = AsyncMock()
            mock_stream_manager.unregister_task = AsyncMock()
            
            # Mock the agent execution
            with patch('gui_agents.grpc_app.asyncio.to_thread', new=AsyncMock()):
                with patch('gui_agents.grpc_app.HardwareInterface'):
                    with patch('gui_agents.grpc_app.Registry'):
                        # Mock agent
                        agent = MagicMock()
                        agent.reset = MagicMock()
                        servicer.tasks[task_id]["agent"] = agent
                        
                        # Run the task
                        backend_kwargs = {"platform": "Ubuntu", "precreate_sid": ""}
                        await servicer._run_task(task_id, backend_kwargs)
        
        # Verify cleanup
        assert task_id not in servicer.tasks, "Task should be removed from self.tasks"
        assert task_id not in servicer.task_created_times, "Task should be removed from task_created_times"
        assert task_id not in servicer.task_start_times, "Task should be removed from task_start_times"

    @pytest.mark.asyncio
    async def test_task_cleanup_on_exception(self, servicer):
        """Test that tasks are cleaned up even when an exception occurs"""
        task_id = str(uuid.uuid4())
        
        # Add a task to self.tasks
        servicer.tasks[task_id] = {
            "agent": MagicMock(),
            "queue": asyncio.Queue(),
            "future": None,
            "query": "test query",
            "max_steps": 10,
        }
        servicer.task_created_times[task_id] = asyncio.get_event_loop().time()
        servicer.task_start_times[task_id] = asyncio.get_event_loop().time()
        
        # Mock stream manager
        with patch('gui_agents.grpc_app.stream_manager') as mock_stream_manager:
            mock_stream_manager.register_task = AsyncMock()
            mock_stream_manager.add_message = AsyncMock()
            mock_stream_manager.unregister_task = AsyncMock()
            
            # Mock the agent execution to raise an exception
            with patch('gui_agents.grpc_app.asyncio.to_thread', new=AsyncMock(side_effect=Exception("Test exception"))):
                with patch('gui_agents.grpc_app.HardwareInterface'):
                    with patch('gui_agents.grpc_app.Registry'):
                        # Mock agent
                        agent = MagicMock()
                        agent.reset = MagicMock()
                        servicer.tasks[task_id]["agent"] = agent
                        
                        # Run the task (should handle the exception)
                        backend_kwargs = {"platform": "Ubuntu", "precreate_sid": ""}
                        await servicer._run_task(task_id, backend_kwargs)
        
        # Verify cleanup even after exception
        assert task_id not in servicer.tasks, "Task should be removed from self.tasks even after exception"
        assert task_id not in servicer.task_created_times, "Task should be removed from task_created_times"
        assert task_id not in servicer.task_start_times, "Task should be removed from task_start_times"

    @pytest.mark.asyncio
    async def test_task_cleanup_on_cancellation(self, servicer):
        """Test that tasks are cleaned up when cancelled"""
        task_id = str(uuid.uuid4())
        
        # Add a task to self.tasks
        servicer.tasks[task_id] = {
            "agent": MagicMock(),
            "queue": asyncio.Queue(),
            "future": None,
            "query": "test query",
            "max_steps": 10,
        }
        servicer.task_created_times[task_id] = asyncio.get_event_loop().time()
        servicer.task_start_times[task_id] = asyncio.get_event_loop().time()
        
        # Mock stream manager
        with patch('gui_agents.grpc_app.stream_manager') as mock_stream_manager:
            mock_stream_manager.register_task = AsyncMock()
            mock_stream_manager.add_message = AsyncMock()
            mock_stream_manager.unregister_task = AsyncMock()
            
            # Mock the agent execution to be cancelled
            async def cancel_soon():
                await asyncio.sleep(0.001)
                raise asyncio.CancelledError()
            
            with patch('gui_agents.grpc_app.asyncio.to_thread', new=AsyncMock(side_effect=cancel_soon)):
                with patch('gui_agents.grpc_app.HardwareInterface'):
                    with patch('gui_agents.grpc_app.Registry'):
                        # Mock agent
                        agent = MagicMock()
                        agent.reset = MagicMock()
                        servicer.tasks[task_id]["agent"] = agent
                        
                        # Run the task (should be cancelled)
                        backend_kwargs = {"platform": "Ubuntu", "precreate_sid": ""}
                        await servicer._run_task(task_id, backend_kwargs)
        
        # Verify cleanup after cancellation
        assert task_id not in servicer.tasks, "Task should be removed from self.tasks after cancellation"
        assert task_id not in servicer.task_created_times, "Task should be removed from task_created_times"
        assert task_id not in servicer.task_start_times, "Task should be removed from task_start_times"

    @pytest.mark.asyncio
    async def test_task_cleanup_on_initialization_failure(self, servicer, mock_request):
        """Test that tasks are cleaned up when initialization fails in RunAgentInstructionAsync"""
        # Mock _make_agent to raise an exception
        with patch.object(servicer, '_make_agent', new=AsyncMock(side_effect=Exception("Agent creation failed"))):
            with patch.object(servicer, '_make_backend_kwargs', new=AsyncMock(return_value={"platform": "Ubuntu", "precreate_sid": "", "sandbox": MagicMock()})):
                context = MagicMock()
                
                # Try to start a task (should fail during initialization)
                result = await servicer.RunAgentInstructionAsync(mock_request, context)
                
                # Should return empty response on error
                assert result.taskId == "" or not result.taskId
                
        # Verify no tasks are left in self.tasks
        assert len(servicer.tasks) == 0, "No tasks should remain in self.tasks after initialization failure"
        assert len(servicer.task_created_times) == 0, "No tasks should remain in task_created_times"

    @pytest.mark.asyncio
    async def test_concurrent_task_cleanup(self, servicer):
        """Test that multiple tasks are properly cleaned up when running concurrently"""
        task_ids = [str(uuid.uuid4()) for _ in range(3)]
        
        for task_id in task_ids:
            servicer.tasks[task_id] = {
                "agent": MagicMock(),
                "queue": asyncio.Queue(),
                "future": None,
                "query": "test query",
                "max_steps": 10,
            }
            servicer.task_created_times[task_id] = asyncio.get_event_loop().time()
            servicer.task_start_times[task_id] = asyncio.get_event_loop().time()
        
        # Mock stream manager
        with patch('gui_agents.grpc_app.stream_manager') as mock_stream_manager:
            mock_stream_manager.register_task = AsyncMock()
            mock_stream_manager.add_message = AsyncMock()
            mock_stream_manager.unregister_task = AsyncMock()
            
            with patch('gui_agents.grpc_app.asyncio.to_thread', new=AsyncMock()):
                with patch('gui_agents.grpc_app.HardwareInterface'):
                    with patch('gui_agents.grpc_app.Registry'):
                        # Run tasks concurrently
                        tasks = []
                        for task_id in task_ids:
                            agent = MagicMock()
                            agent.reset = MagicMock()
                            servicer.tasks[task_id]["agent"] = agent
                            
                            backend_kwargs = {"platform": "Ubuntu", "precreate_sid": ""}
                            tasks.append(servicer._run_task(task_id, backend_kwargs))
                        
                        await asyncio.gather(*tasks)
        
        # Verify all tasks are cleaned up
        for task_id in task_ids:
            assert task_id not in servicer.tasks, f"Task {task_id} should be removed from self.tasks"
            assert task_id not in servicer.task_created_times, f"Task {task_id} should be removed from task_created_times"
            assert task_id not in servicer.task_start_times, f"Task {task_id} should be removed from task_start_times"

    @pytest.mark.asyncio
    async def test_locking_consistency(self, servicer):
        """Test that lock is properly held during cleanup operations"""
        task_id = str(uuid.uuid4())
        
        # Add a task to self.tasks
        servicer.tasks[task_id] = {
            "agent": MagicMock(),
            "queue": asyncio.Queue(),
            "future": None,
            "query": "test query",
            "max_steps": 10,
        }
        servicer.task_created_times[task_id] = asyncio.get_event_loop().time()
        servicer.task_start_times[task_id] = asyncio.get_event_loop().time()
        
        lock_held_during_cleanup = False
        
        # Mock stream manager
        with patch('gui_agents.grpc_app.stream_manager') as mock_stream_manager:
            mock_stream_manager.register_task = AsyncMock()
            mock_stream_manager.add_message = AsyncMock()
            
            async def check_lock_on_unregister(tid):
                nonlocal lock_held_during_cleanup
                # Check if lock is NOT held (it should be released by this point)
                lock_held_during_cleanup = servicer.task_lock.locked()
            
            mock_stream_manager.unregister_task = AsyncMock(side_effect=check_lock_on_unregister)
            
            with patch('gui_agents.grpc_app.asyncio.to_thread', new=AsyncMock()):
                with patch('gui_agents.grpc_app.HardwareInterface'):
                    with patch('gui_agents.grpc_app.Registry'):
                        agent = MagicMock()
                        agent.reset = MagicMock()
                        servicer.tasks[task_id]["agent"] = agent
                        
                        backend_kwargs = {"platform": "Ubuntu", "precreate_sid": ""}
                        await servicer._run_task(task_id, backend_kwargs)
        
        # Lock should not be held when unregister_task is called
        assert not lock_held_during_cleanup, "Lock should be released before calling unregister_task"
        
        # Verify cleanup
        assert task_id not in servicer.tasks, "Task should be removed from self.tasks"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
