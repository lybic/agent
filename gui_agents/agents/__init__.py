"""
GUI Agents - Advanced UI automation agents with dispatcher capabilities.

This package provides enhanced GUI automation agents with central dispatcher
integration for quality monitoring, cost management, and adaptive execution.
"""

# Core agents
from .agent_normal import UIAgent, AgentSNormal
from .agent_dispatched import AgentSDispatched

# Dispatcher system
from .central_dispatcher import CentralDispatcher
from .enhanced_global_state import EnhancedGlobalState
from .enhanced_reflector import EnhancedReflector

# Type definitions
from .dispatch_types import (
    # Configuration types
    DispatchConfig,
    QualityCheckConfig,
    CostBudget,
    
    # Data types
    ExecutionMetrics,
    QualityReport,
    ProgressReport,
    VisualChangeReport,
    ModuleMessage,
    ExecutionContext,
    QualityCheckContext,
    CostStatus,
    
    # Enums
    QualityStatus,
    QualityTrigger,
    RecommendationType,
    ModulePriority
)

# Core components (existing)
from .manager import Manager
from .worker import Worker
from .reflector import Reflector
from .grounding import Grounding, ACI, FastGrounding
from .global_state import GlobalState

__all__ = [
    # Main agent classes
    "UIAgent",
    "AgentSNormal", 
    "AgentSDispatched",
    
    # Dispatcher system
    "CentralDispatcher",
    "EnhancedGlobalState",
    "EnhancedReflector",
    
    # Configuration classes
    "DispatchConfig",
    "QualityCheckConfig", 
    "CostBudget",
    
    # Data classes
    "ExecutionMetrics",
    "QualityReport",
    "ProgressReport",
    "VisualChangeReport",
    "ModuleMessage",
    "ExecutionContext",
    "QualityCheckContext",
    "CostStatus",
    
    # Enums
    "QualityStatus",
    "QualityTrigger",
    "RecommendationType",
    "ModulePriority",
    
    # Core components
    "Manager",
    "Worker", 
    "Reflector",
    "Grounding",
    "ACI",
    "FastGrounding",
    "GlobalState",
]
