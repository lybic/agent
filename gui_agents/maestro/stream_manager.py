import queue
import threading
from typing import Dict, Optional, Generator
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class StreamMessage:
    stage: str
    message: str

class StreamManager:
    """
    Manages in-memory message queues for each task to stream progress.
    This class is thread-safe.

    todo: P3 using an external message queue
    """
    def __init__(self, max_queue_size: int = 100):
        self.task_queues: Dict[str, queue.Queue[Optional[StreamMessage]]] = {}
        self.max_queue_size = max_queue_size
        self._lock = threading.Lock()

    def add_message(self, task_id: str, stage: str, message: str):
        """Adds a message to a task's queue. Non-blocking."""
        with self._lock:
            q = self.task_queues.get(task_id)

        if q:
            msg = StreamMessage(stage=stage, message=message)
            try:
                q.put_nowait(msg)
            except queue.Full:
                logger.warning(f"Message queue for task {task_id} is full. Dropping oldest message.")
                try:
                    # Drop the oldest message to make space for the new one
                    q.get_nowait()
                    q.put_nowait(msg)
                except queue.Empty:
                    pass  # Should not happen if queue was full
        else:
            logger.warning(f"No message queue found for task {task_id}. Message not added.")

    def get_message_stream(self, task_id: str) -> Generator[StreamMessage, None, None]:
        """Returns a generator that yields messages from a task's queue. Blocks until a message is available."""
        with self._lock:
            if task_id not in self.task_queues:
                self.task_queues[task_id] = queue.Queue(maxsize=self.max_queue_size)
                logger.info(f"Registered message queue for task {task_id} in get_message_stream.")
            q = self.task_queues[task_id]
        
        while True:
            message = q.get(block=True)
            if message is None:  # Sentinel value indicates end of stream
                logger.info(f"End of stream for task {task_id}")
                break
            yield message

    def register_task(self, task_id: str):
        """Creates a new message queue for a task."""
        with self._lock:
            if task_id not in self.task_queues:
                self.task_queues[task_id] = queue.Queue(maxsize=self.max_queue_size)
                logger.info(f"Registered message queue for task {task_id}")

    def unregister_task(self, task_id: str):
        """Removes a task's message queue and signals end of stream."""
        q = None
        with self._lock:
            if task_id in self.task_queues:
                q = self.task_queues.pop(task_id)
                logger.info(f"Unregistered message queue for task {task_id}")
        
        if q:
            try:
                # Put a sentinel value to unblock any consumers
                q.put_nowait(None)
            except queue.Full:
                # If full, make space for sentinel
                try:
                    q.get_nowait()
                    q.put_nowait(None)
                except queue.Empty:
                    pass

# Global instance to be used across the application
stream_manager = StreamManager()
