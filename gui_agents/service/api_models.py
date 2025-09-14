"""Data models for the Agent Service API"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Union
from enum import Enum
import uuid
import time


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentMode(Enum):
    """Agent execution mode"""
    NORMAL = "normal"
    FAST = "fast"


class Backend(Enum):
    """Available backends"""
    LYBIC = "lybic"
    PYAUTOGUI = "pyautogui"
    PYAUTOGUI_VMWARE = "pyautogui_vmware"
    ADB = "adb"
    LYBIC_SDK = "lybic_sdk"


@dataclass
class TaskRequest:
    """Request to execute a task"""
    instruction: str
    backend: str = Backend.LYBIC.value
    mode: str = AgentMode.NORMAL.value
    max_steps: int = 50
    enable_takeover: bool = False
    enable_search: bool = True
    timeout: int = 3600  # 1 hour default timeout
    config: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate request parameters"""
        if self.max_steps <= 0:
            raise ValueError("max_steps must be positive")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")


@dataclass
class ExecutionStats:
    """Execution statistics"""
    total_duration: float
    steps_count: int
    tokens_used: Dict[str, int] = field(default_factory=lambda: {
        "input": 0, "output": 0, "total": 0
    })
    cost: Optional[float] = None
    avg_step_duration: Optional[float] = None
    
    def __post_init__(self):
        if self.steps_count > 0:
            self.avg_step_duration = self.total_duration / self.steps_count


@dataclass
class TaskResult:
    """Result of task execution"""
    task_id: str
    status: TaskStatus
    instruction: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_stats: Optional[ExecutionStats] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    @classmethod
    def create_pending(cls, instruction: str) -> 'TaskResult':
        """Create a pending task result"""
        return cls(
            task_id=str(uuid.uuid4()),
            status=TaskStatus.PENDING,
            instruction=instruction
        )
    
    def mark_started(self):
        """Mark task as started"""
        self.status = TaskStatus.RUNNING
        self.started_at = time.time()
    
    def mark_completed(self, result: Optional[Dict[str, Any]] = None, stats: Optional[ExecutionStats] = None):
        """Mark task as completed"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = time.time()
        self.result = result
        self.execution_stats = stats
    
    def mark_failed(self, error: str):
        """Mark task as failed"""
        self.status = TaskStatus.FAILED
        self.completed_at = time.time()
        self.error = error
    
    def mark_cancelled(self):
        """Mark task as cancelled"""
        self.status = TaskStatus.CANCELLED
        self.completed_at = time.time()
    
    @property
    def is_finished(self) -> bool:
        """Check if task is finished (completed, failed, or cancelled)"""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
    
    @property
    def execution_duration(self) -> Optional[float]:
        """Get execution duration if available"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None


@dataclass
class AsyncTaskHandle:
    """Handle for asynchronous task execution"""
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    
    def is_finished(self) -> bool:
        """Check if task is finished"""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED] 