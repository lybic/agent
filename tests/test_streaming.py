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
        super().__init__()

def test_streaming_in_thread():
    """Test streaming from a separate thread (simulating the agent execution context)."""
    task_id = "test-task-123"
    agent = TestAgent()

    print(f"Testing streaming from thread for task: {task_id}")

    # Register the task first (in main thread)
    async def register_task():
        await stream_manager.register_task(task_id)
        print("Task registered in main thread")

    # Run registration in main event loop
    asyncio.run(register_task())

    # Function to run in separate thread (simulating agent execution)
    def agent_thread():
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
        await stream_manager.unregister_task(task_id)
        print("Task unregistered")

    asyncio.run(cleanup())
    print("Test completed successfully!")

if __name__ == "__main__":
    test_streaming_in_thread()