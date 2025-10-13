"""
Stream manager for per-task progress messaging.

This module provides a global `stream_manager` singleton that manages
async message queues for task-based streaming. The singleton is async-safe
and should have its event loop configured via `set_loop()` during application
startup.
"""
import asyncio
from google.protobuf.timestamp_pb2 import Timestamp
from typing import Dict, Optional, AsyncGenerator
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class StreamMessage:
    stage: str
    message: str
    timestamp: Timestamp


class StreamManager:
    """
    Manages in-memory async message queues for each task to stream progress.
    This class is async-safe.
    """

    def __init__(self, max_queue_size: int = 100):
        """
        Initialize a StreamManager that manages per-task in-memory async message queues.
        
        Parameters:
            max_queue_size (int): Maximum number of messages to keep per task queue; when a queue is full the oldest message will be dropped to make room for new messages.
        """
        self.task_queues: Dict[str, asyncio.Queue[Optional[StreamMessage]]] = {}
        self.max_queue_size = max_queue_size
        self._lock = asyncio.Lock()
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """
        Store the event loop used to schedule coroutines from non-async threads.
        
        Parameters:
            loop (asyncio.AbstractEventLoop): Event loop passed to asyncio.run_coroutine_threadsafe for thread-safe coroutine execution.
        """
        self.loop = loop

    def add_message_threadsafe(self, task_id: str, stage: str, message: str):
        """
        Enqueue a progress message for a task from a non-async thread in a thread-safe manner.
        
        If the manager's event loop has not been set, an error is logged and the message is not scheduled.
        
        Parameters:
            task_id (str): Identifier of the task to receive the message.
            stage (str): Stage label for the progress update.
            message (str): Text of the progress message.
        """
        if not self.loop:
            logger.error("StreamManager event loop not set. Cannot send message from thread.")
            return

        asyncio.run_coroutine_threadsafe(
            self.add_message(task_id, stage, message),
            self.loop
        )

    async def add_message(self, task_id: str, stage: str, message: str):
        """
        Enqueues a progress message for the given task; if the task's queue is full, drops the oldest message to make room.
        
        Parameters:
            task_id (str): Identifier of the task whose queue will receive the message.
            stage (str): Short stage name or label for the message.
            message (str): Human-readable progress message.
        """
        async with self._lock:
            q = self.task_queues.get(task_id)

        if q:
            timestamp = Timestamp()
            timestamp.GetCurrentTime()
            msg = StreamMessage(stage=stage, message=message, timestamp=timestamp)
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                logger.warning(f"Message queue for task {task_id} is full. Dropping oldest message.")
                # Drop the oldest message to make space for the new one
                q.get_nowait()
                q.put_nowait(msg)

        else:
            logger.warning(f"No message queue found for task {task_id}. Message not added.")

    async def get_message_stream(self, task_id: str) -> AsyncGenerator[StreamMessage, None]:
        """
        Provide an async generator that yields progress messages for the given task.
        
        If the task has no existing queue, one is created and registered. The generator yields StreamMessage objects produced for the task and terminates when a sentinel `None` is received, signaling end of stream.
        
        Parameters:
            task_id (str): Identifier of the task whose message stream to consume.
        
        Returns:
            AsyncGenerator[StreamMessage, None]: An async generator yielding `StreamMessage` instances for the task; iteration ends when a sentinel `None` is encountered.
        """
        async with self._lock:
            if task_id not in self.task_queues:
                self.task_queues[task_id] = asyncio.Queue(maxsize=self.max_queue_size)
                logger.info(f"Registered message queue for task {task_id} in get_message_stream.")
            q = self.task_queues[task_id]

        while True:
            message = await q.get()
            if message is None:  # Sentinel value indicates end of stream
                logger.info(f"End of stream for task {task_id}")
                break
            yield message

    async def register_task(self, task_id: str):
        """
        Create a per-task message queue if one does not already exist.
        
        This is idempotent: if a queue for the given task_id already exists, the call has no effect. The created queue uses the manager's configured max_queue_size and the operation is safe to call concurrently.
        
        Parameters:
            task_id (str): Unique identifier of the task to register a message queue for.
        """
        async with self._lock:
            if task_id not in self.task_queues:
                self.task_queues[task_id] = asyncio.Queue(maxsize=self.max_queue_size)
                logger.info(f"Registered message queue for task {task_id}")

    async def unregister_task(self, task_id: str):
        """Removes a task's message queue and signals end of stream."""
        q = None
        async with self._lock:
            if task_id in self.task_queues:
                q = self.task_queues.pop(task_id)
                logger.info(f"Unregistered message queue for task {task_id}")
        if q:
            try:
                # Put a sentinel value to unblock any consumers
                q.put_nowait(None)
            except asyncio.QueueFull:
                # If full, make space for sentinel
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                # Retry put after making space or if queue became empty
                try:
                    q.put_nowait(None)
                except asyncio.QueueFull:
                    logger.error(f"Could not send sentinel for task {task_id}: queue still full after retry")


# Global instance to be used across the application
stream_manager = StreamManager()