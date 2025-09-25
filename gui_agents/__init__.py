"""
GUI Agents - A comprehensive GUI automation framework

This package provides both low-level agent components and a high-level service interface
for GUI automation tasks across different platforms and backends.

Main Components:
- AgentService: High-level service interface (recommended for most users)
- AgentS2, AgentSFast: Core agent implementations  
- HardwareInterface: Hardware abstraction layer
- ServiceConfig: Configuration management

Quick Start:
    from gui_agents import AgentService
    
    service = AgentService()
    result = service.execute_task("Take a screenshot")
    print(f"Task completed: {result.status}")
"""

# High-level service interface (recommended)
from .service import (
    AgentService,
    ServiceConfig, 
    TaskRequest,
    TaskResult,
    TaskStatus,
    ExecutionStats,
    AgentServiceError,
    ConfigurationError,
    TaskExecutionError
)

# Core agent classes (for advanced users)
from .agents.agent_s import AgentS2, AgentSFast
from .agents.hardware_interface import HardwareInterface
from .store.registry import Registry
from .agents.global_state import GlobalState

__version__ = "0.2.1"

# Primary exports (what users should typically use)
__all__ = [
    # High-level service interface
    "AgentService",
    "ServiceConfig",
    "TaskRequest", 
    "TaskResult",
    "TaskStatus", 
    "ExecutionStats",
    
    # Exceptions
    "AgentServiceError",
    "ConfigurationError", 
    "TaskExecutionError",
    
    # Core classes (for advanced usage)
    "AgentS2",
    "AgentSFast", 
    "HardwareInterface",
    "Registry",
    "GlobalState",
]
