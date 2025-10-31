#!/usr/bin/env python3
"""
Test script for task cancellation functionality in gRPC Agent service.
"""

import asyncio
import logging
import time
import uuid
import grpc
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
os.environ["PYTHONPATH"] = str(project_root)

from gui_agents.proto import agent_pb2, agent_pb2_grpc
from gui_agents.proto.pb.agent_pb2 import LLMConfig, StageModelConfig, CommonConfig, Authorization, InstanceMode, Sandbox, SandboxOS

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TaskCancellationTest:
    """Test class for task cancellation functionality"""

    def __init__(self, grpc_address='localhost:50051'):
        self.grpc_address = grpc_address
        self.channel = None
        self.stub = None

    async def connect(self):
        """Connect to gRPC server"""
        try:
            self.channel = grpc.aio.insecure_channel(self.grpc_address)
            grpc.grpc.channel_ready_future(self.channel).result(timeout=10)
            self.stub = agent_pb2_grpc.AgentStub(self.channel)
            logger.info(f"Connected to gRPC server at {self.grpc_address}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to gRPC server: {e}")
            return False

    async def disconnect(self):
        """Disconnect from gRPC server"""
        if self.channel:
            await self.channel.close()
            logger.info("Disconnected from gRPC server")

    def create_test_request(self, instruction="Open a calculator and wait for 30 seconds"):
        """Create a test request for agent instruction"""
        # Create a simple authorization for testing
        auth = Authorization(
            orgID="test-org",
            apiKey="test-key"
        )

        # Create a common config
        common_config = CommonConfig(
            id="test-task",
            backend="lybic",
            mode=InstanceMode.FAST,
            steps=10,
            authorizationInfo=auth
        )

        # Create a simple sandbox config
        sandbox = Sandbox(
            id="",
            name="test-sandbox",
            description="Test sandbox for cancellation",
            shapeName="beijing-2c-4g-cpu",
            os=SandboxOS.LINUX
        )

        # Create the request
        request = agent_pb2.RunAgentInstructionRequest(
            instruction=instruction,
            sandbox=sandbox,
            runningConfig=common_config
        )

        return request

    async def test_cancel_task_sync(self):
        """Test cancelling a task started synchronously"""
        logger.info("=== Testing Synchronous Task Cancellation ===")

        try:
            # Start a task synchronously
            request = self.create_test_request("Open calculator and wait 60 seconds")
            logger.info("Starting task synchronously...")

            task_id = None

            # Start the task and stream responses
            async for response in self.stub.RunAgentInstruction(request):
                if not task_id:
                    task_id = response.taskId
                    logger.info(f"Task started with ID: {task_id}")

                logger.info(f"Task update: {response.stage} - {response.message}")

                # Cancel after receiving a few messages
                if response.stage == "starting":
                    logger.info("Cancelling task...")
                    cancel_request = agent_pb2.CancelTaskRequest(taskId=task_id)
                    cancel_response = await self.stub.CancelTask(cancel_request)
                    logger.info(f"Cancel response: {cancel_response.success} - {cancel_response.message}")
                    break

            # Query task status to confirm cancellation
            if task_id:
                await asyncio.sleep(2)  # Give it time to process
                status_request = agent_pb2.QueryTaskStatusRequest(taskId=task_id)
                status_response = await self.stub.QueryTaskStatus(status_request)
                logger.info(f"Final task status: {status_response.status} - {status_response.message}")

            return True

        except Exception as e:
            logger.error(f"Error in synchronous task cancellation test: {e}")
            return False

    async def test_cancel_task_async(self):
        """Test cancelling a task started asynchronously"""
        logger.info("=== Testing Asynchronous Task Cancellation ===")

        try:
            # Start a task asynchronously
            request = self.create_test_request("Open notepad and wait 60 seconds")
            logger.info("Starting task asynchronously...")

            async_response = await self.stub.RunAgentInstructionAsync(request)
            task_id = async_response.taskId
            logger.info(f"Task started with ID: {task_id}")

            # Wait a moment then cancel
            await asyncio.sleep(2)
            logger.info("Cancelling task...")

            cancel_request = agent_pb2.CancelTaskRequest(taskId=task_id)
            cancel_response = await self.stub.CancelTask(cancel_request)
            logger.info(f"Cancel response: {cancel_response.success} - {cancel_response.message}")

            # Query task status to confirm cancellation
            await asyncio.sleep(2)
            status_request = agent_pb2.QueryTaskStatusRequest(taskId=task_id)
            status_response = await self.stub.QueryTaskStatus(status_request)
            logger.info(f"Final task status: {status_response.status} - {status_response.message}")

            return True

        except Exception as e:
            logger.error(f"Error in asynchronous task cancellation test: {e}")
            return False

    async def test_cancel_nonexistent_task(self):
        """Test cancelling a task that doesn't exist"""
        logger.info("=== Testing Non-existent Task Cancellation ===")

        try:
            fake_task_id = str(uuid.uuid4())
            logger.info(f"Attempting to cancel non-existent task: {fake_task_id}")

            cancel_request = agent_pb2.CancelTaskRequest(taskId=fake_task_id)
            cancel_response = await self.stub.CancelTask(cancel_request)
            logger.info(f"Cancel response: {cancel_response.success} - {cancel_response.message}")

            if not cancel_response.success and "not found" in cancel_response.message.lower():
                logger.info("✓ Correctly handled non-existent task")
                return True
            else:
                logger.error("✗ Did not handle non-existent task correctly")
                return False

        except Exception as e:
            logger.error(f"Error in non-existent task cancellation test: {e}")
            return False

    async def test_cancel_completed_task(self):
        """Test cancelling a task that has already completed"""
        logger.info("=== Testing Completed Task Cancellation ===")

        try:
            # Start a simple task that completes quickly
            request = self.create_test_request("Just say hello and finish")
            logger.info("Starting simple task...")

            task_id = None

            # Let the task complete
            async for response in self.stub.RunAgentInstruction(request):
                if not task_id:
                    task_id = response.taskId
                    logger.info(f"Task started with ID: {task_id}")

                logger.info(f"Task update: {response.stage} - {response.message}")

            # Wait for task to complete
            await asyncio.sleep(2)

            # Try to cancel the completed task
            if task_id:
                logger.info("Attempting to cancel completed task...")
                cancel_request = agent_pb2.CancelTaskRequest(taskId=task_id)
                cancel_response = await self.stub.CancelTask(cancel_request)
                logger.info(f"Cancel response: {cancel_response.success} - {cancel_response.message}")

                if not cancel_response.success and ("finished" in cancel_response.message.lower() or "completed" in cancel_response.message.lower()):
                    logger.info("✓ Correctly handled completed task")
                    return True
                else:
                    logger.error("✗ Did not handle completed task correctly")
                    return False

            return False

        except Exception as e:
            logger.error(f"Error in completed task cancellation test: {e}")
            return False

    async def run_all_tests(self):
        """Run all cancellation tests"""
        logger.info("Starting task cancellation tests...")

        if not await self.connect():
            logger.error("Failed to connect to gRPC server. Make sure the server is running.")
            return False

        try:
            results = []

            # Run all tests
            results.append(await self.test_cancel_nonexistent_task())
            await asyncio.sleep(1)

            results.append(await self.test_cancel_task_async())
            await asyncio.sleep(1)

            results.append(await self.test_cancel_task_sync())
            await asyncio.sleep(1)

            results.append(await self.test_cancel_completed_task())

            # Summary
            passed = sum(results)
            total = len(results)
            logger.info(f"\n=== Test Summary ===")
            logger.info(f"Passed: {passed}/{total}")

            if passed == total:
                logger.info("✓ All tests passed!")
                return True
            else:
                logger.error(f"✗ {total - passed} tests failed")
                return False

        finally:
            await self.disconnect()

async def main():
    """Main function to run the tests"""
    test = TaskCancellationTest()
    success = await test.run_all_tests()

    if success:
        logger.info("Task cancellation functionality test completed successfully!")
        exit(0)
    else:
        logger.error("Task cancellation functionality test failed!")
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())