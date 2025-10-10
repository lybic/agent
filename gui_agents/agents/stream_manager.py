import asyncio
from typing import Dict, Optional, AsyncGenerator
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class StreamMessage:
    stage: str
    message: str


class StreamManager:
    """
    Manages in-memory async message queues for each task to stream progress.
    This class is async-safe.
    """

    def __init__(self, max_queue_size: int = 100):
        self.task_queues: Dict[str, asyncio.Queue[Optional[StreamMessage]]] = {}
        self.max_queue_size = max_queue_size
        self._lock = asyncio.Lock()

    async def add_message(self, task_id: str, stage: str, message: str):
        """Adds a message to a task's queue. Non-blocking."""
        async with self._lock:
            q = self.task_queues.get(task_id)

        if q:
            msg = StreamMessage(stage=stage, message=message)
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
        """Returns an async generator that yields messages from a task's queue."""
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
        """Creates a new message queue for a task."""
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
                    q.put_nowait(None)
                except asyncio.QueueEmpty:
                    pass


# Global instance to be used across the application
stream_manager = StreamManager()
