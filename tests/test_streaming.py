#!/usr/bin/env python3
"""
Test script to verify that streaming messages are correctly sent in multi-threaded environments.
"""
import asyncio
import threading
import time
from gui_agents.agents.stream_manager import stream_manager
from gui_agents.agents.agent_s import UIAgent

# Create a test agent that inherits from UIAgent
class TestAgent(UIAgent):
    def __init__(self):
        """
        Initialize a TestAgent instance.
        
        Performs the base-class initialization for the UIAgent.
        """
        super().__init__()

def test_streaming_in_thread():
    """
    Verify streaming of messages sent from a separate thread into a task's message stream.
    
    Registers a task, starts a daemon thread that emits a predefined sequence of stream messages for that task, consumes messages from the task's stream until seven messages are received, waits for the sender thread to finish, and then unregisters the task. Prints progress messages during registration, sending, consumption, and cleanup.
    """
    task_id = "test-task-123"
    agent = TestAgent()

    print(f"Testing streaming from thread for task: {task_id}")

    # Register the task first (in main thread)
    async def register_task():
        """
        Register the current task identifier with the stream manager and confirm registration.
        
        Registers the task identified by the surrounding scope's `task_id` with `stream_manager` and prints a confirmation message when registration completes.
        """
        await stream_manager.register_task(task_id)
        print("Task registered in main thread")

    # Run registration in main event loop
    asyncio.run(register_task())

    # Function to run in separate thread (simulating agent execution)
    def agent_thread():
        """
        Simulates an agent execution running in a background thread by sending a predefined sequence of streaming messages for a task.
        
        Sends a series of stage/message pairs to the agent's stream for the current task and pauses briefly before starting and between each message to emulate timed streaming from a separate thread.
        """
        print("Agent thread started")
        time.sleep(0.1)  # Small delay to ensure main loop is running

        # Test sending messages from the thread
        messages = [
            ("planning", "开始规划任务..."),
            ("subtask", "开始执行子任务: 打开浏览器"),
            ("thinking", "正在生成执行动作..."),
            ("action_plan", "生成执行计划: 打开Chrome浏览器"),
            ("action", "执行动作: CLICK"),
            ("subtask_complete", "✅ 子任务完成: 打开浏览器"),
            ("completion", "🎉 任务完成！"),
        ]

        for stage, message in messages:
            print(f"Sending message: {stage} - {message}")
            agent._send_stream_message(task_id, stage, message)
            time.sleep(0.2)  # Small delay between messages

    # Function to consume messages in main thread
    async def consume_messages():
        """
        Consume messages from the stream_manager for the task_id defined in the enclosing scope until seven messages have been received.
        
        Reads messages from stream_manager.get_message_stream(task_id), prints each message's stage and content, and stops after receiving seven messages.
        """
        print("Starting message consumer")
        message_count = 0
        async for msg in stream_manager.get_message_stream(task_id):
            print(f"Received message: {msg.stage} - {msg.message}")
            message_count += 1
            if message_count >= 7:  # Expected number of messages
                break
        print("Message consumer finished")

    # Start the agent thread
    agent_thread = threading.Thread(target=agent_thread)
    agent_thread.daemon = True
    agent_thread.start()

    # Consume messages in main event loop
    asyncio.run(consume_messages())

    # Wait for thread to complete
    agent_thread.join(timeout=2)

    # Clean up
    async def cleanup():
        """
        Unregister the current test task from the stream manager and print a confirmation.
        
        Performs task unregistration for the task identified by `task_id` in the enclosing scope and prints "Task unregistered" when complete.
        """
        await stream_manager.unregister_task(task_id)
        print("Task unregistered")

    asyncio.run(cleanup())
    print("Test completed successfully!")

if __name__ == "__main__":
    test_streaming_in_thread()