"""Custom exceptions for the Agent Service"""


class AgentServiceError(Exception):
    """Base exception for Agent Service errors"""
    pass


class ConfigurationError(AgentServiceError):
    """Raised when there are configuration issues"""
    pass


class TaskExecutionError(AgentServiceError):
    """Raised when task execution fails"""
    
    def __init__(self, message: str, task_id: str | None = None, step: int | None = None):
        super().__init__(message)
        self.task_id = task_id
        self.step = step


class TaskTimeoutError(TaskExecutionError):
    """Raised when task execution times out"""
    pass


class BackendError(AgentServiceError):
    """Raised when backend operations fail"""
    pass


class APIKeyError(ConfigurationError):
    """Raised when API key configuration is invalid"""
    pass 