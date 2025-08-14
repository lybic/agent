"""
Data structure definitions for the Central Dispatcher system.

This module contains all the core data types used by the dispatcher architecture,
including situation assessments, execution metrics, quality reports, and configuration classes.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Literal, Union
from enum import Enum, auto
import time
from PIL import Image

from gui_agents.utils.common_utils import Node


class DecisionType(Enum):
    """Types of decisions the dispatcher can make"""
    CONTINUE = auto()
    QUALITY_CHECK = auto()
    REPLAN = auto()
    USER_INTERVENTION = auto()


class QualityStatus(Enum):
    """Quality check status levels"""
    GOOD = "GOOD"
    CONCERNING = "CONCERNING"
    CRITICAL = "CRITICAL"


class RecommendationType(Enum):
    """Types of recommendations from quality checks"""
    CONTINUE = "CONTINUE"
    ADJUST = "ADJUST"
    REPLAN = "REPLAN"


class ModulePriority(Enum):
    """Priority levels for module operations"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class QualityTrigger(Enum):
    """Quality check trigger types"""
    TIME_BASED = "time_based"
    STEP_BASED = "step_based"
    ERROR_BASED = "error_based" 
    FAILURE_BASED = "failure_based"


class ReplanStrategy(Enum):
    """Different replan strategies based on severity"""
    LIGHT_ADJUSTMENT = "LIGHT_ADJUSTMENT"      # Modify current subtask parameters
    MEDIUM_ADJUSTMENT = "MEDIUM_ADJUSTMENT"    # Reorder subtasks
    HEAVY_ADJUSTMENT = "HEAVY_ADJUSTMENT"      # Complete redecomposition
    ESCALATION = "ESCALATION"                  # Request user help


class TriggerReason(Enum):
    """Reasons for triggering various actions"""
    # Quality check triggers
    PERIODIC = "every_5_steps"
    REPEATED_ACTION = "action_loop"
    EXCESSIVE_STEPS = "too_many_steps"
    NO_PROGRESS = "ui_unchanged"
    WORKER_CONFUSED = "worker_stuck"
    TIME_EXCEEDED = "subtask_timeout"
    
    # Replan triggers
    REFLECTOR_RECOMMENDATION = "quality_check_failed"
    WORKER_CONSECUTIVE_FAIL = "multiple_failures"
    SUBTASK_TIMEOUT = "time_exceeded"
    UNHANDLEABLE_ERROR = "critical_error"
    USER_REQUEST = "manual_trigger"
    CONTEXT_CHANGED = "environment_shift"


@dataclass
class SituationAssessment:
    """Assessment of the current execution situation"""
    needs_replan: bool
    needs_quality_check: bool
    ready_for_execution: bool
    user_intervention_needed: bool
    replan_reason: Optional[str] = None
    check_reason: Optional[str] = None
    intervention_reason: Optional[str] = None
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class ExecutionMetrics:
    """Metrics tracking execution performance and patterns"""
    total_steps: int = 0
    subtask_steps: int = 0
    consecutive_failures: int = 0
    repeated_action_count: int = 0
    ui_unchanged_steps: int = 0
    error_rate: float = 0.0
    avg_step_duration: float = 0.0
    cost_spent: float = 0.0
    success_rate: float = 0.0
    last_action: Optional[str] = None
    steps_since_last_check: int = 0
    subtask_duration: float = 0.0
    no_progress_steps: int = 0
    
    def update_step_metrics(self, success: bool, duration: float, action: str):
        """Update metrics after a step execution"""
        self.total_steps += 1
        self.subtask_steps += 1
        self.steps_since_last_check += 1
        
        if not success:
            self.consecutive_failures += 1
        else:
            self.consecutive_failures = 0
            
        if action == self.last_action:
            self.repeated_action_count += 1
        else:
            self.repeated_action_count = 0
            self.last_action = action
            
        # Update running averages
        self.avg_step_duration = (
            (self.avg_step_duration * (self.total_steps - 1) + duration) / self.total_steps
        )
        
        # Update error rate
        failed_steps = self.total_steps - (self.total_steps * self.success_rate)
        if not success:
            failed_steps += 1
        self.error_rate = failed_steps / self.total_steps
        self.success_rate = 1.0 - self.error_rate


@dataclass
class QualityCheckContext:
    """Context information for quality checks"""
    recent_actions: List[Dict[str, Any]]
    current_screenshot: Optional[bytes]
    subtask_goal: Optional[Node]
    execution_history: List[Dict[str, Any]]
    metrics: ExecutionMetrics
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "recent_actions": self.recent_actions,
            "subtask_goal": self.subtask_goal.name if self.subtask_goal else None,
            "execution_history_count": len(self.execution_history),
            "metrics": {
                "total_steps": self.metrics.total_steps,
                "error_rate": self.metrics.error_rate,
                "repeated_action_count": self.metrics.repeated_action_count
            },
            "timestamp": self.timestamp
        }


@dataclass
class QualityReport:
    """Report generated by quality checks"""
    status: QualityStatus
    recommendation: RecommendationType
    confidence: float
    issues: List[str]
    suggestions: List[str]
    cost_estimate: float
    timestamp: float = field(default_factory=time.time)
    trigger_reason: Optional[str] = None
    context_summary: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "status": self.status.value,
            "recommendation": self.recommendation.value,
            "confidence": self.confidence,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "cost_estimate": self.cost_estimate,
            "timestamp": self.timestamp,
            "trigger_reason": self.trigger_reason,
            "context_summary": self.context_summary
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QualityReport':
        """Create from dictionary"""
        return cls(
            status=QualityStatus(data["status"]),
            recommendation=RecommendationType(data["recommendation"]),
            confidence=data["confidence"],
            issues=data["issues"],
            suggestions=data["suggestions"],
            cost_estimate=data["cost_estimate"],
            timestamp=data["timestamp"],
            trigger_reason=data.get("trigger_reason"),
            context_summary=data.get("context_summary")
        )


@dataclass
class QualityCheckConfig:
    """Configuration for quality checks"""
    check_interval: float = 30.0  # seconds
    step_interval: int = 5  # steps
    use_lightweight_model: bool = True
    screenshot_analysis: bool = True
    deep_reasoning: bool = False
    estimated_cost: float = 0.02
    max_analysis_time: float = 30.0
    include_visual_comparison: bool = True
    include_progress_analysis: bool = True
    include_efficiency_check: bool = False
    
    @classmethod
    def for_trigger(cls, trigger_reason: str) -> 'QualityCheckConfig':
        """Create appropriate config based on trigger reason"""
        if trigger_reason == TriggerReason.PERIODIC.value:
            return cls(
                use_lightweight_model=True,
                screenshot_analysis=True,
                deep_reasoning=False,
                estimated_cost=0.02
            )
        elif trigger_reason in [TriggerReason.REPEATED_ACTION.value, TriggerReason.NO_PROGRESS.value]:
            return cls(
                use_lightweight_model=True,
                screenshot_analysis=True,
                deep_reasoning=True,
                estimated_cost=0.05,
                include_efficiency_check=True
            )
        elif trigger_reason in [TriggerReason.WORKER_CONFUSED.value, TriggerReason.TIME_EXCEEDED.value]:
            return cls(
                use_lightweight_model=False,
                screenshot_analysis=True,
                deep_reasoning=True,
                estimated_cost=0.15,
                include_efficiency_check=True
            )
        else:
            return cls()  # Default configuration


@dataclass
class ReplanContext:
    """Context information for replan operations"""
    failure_reason: str
    failed_subtasks: List[Node]
    completed_subtasks: List[Node]
    remaining_subtasks: List[Node]
    execution_history: List[Dict[str, Any]]
    quality_reports: List[QualityReport]
    current_metrics: ExecutionMetrics
    timestamp: float = field(default_factory=time.time)
    
    def get_failure_summary(self) -> str:
        """Get a summary of recent failures"""
        recent_failures = self.failed_subtasks[-3:] if len(self.failed_subtasks) > 3 else self.failed_subtasks
        return f"Recent failures: {[f.name for f in recent_failures]}"
    
    def get_quality_summary(self) -> str:
        """Get a summary of recent quality reports"""
        if not self.quality_reports:
            return "No quality reports available"
        
        recent_reports = self.quality_reports[-3:]
        issues = []
        for report in recent_reports:
            issues.extend(report.issues)
        
        return f"Recent quality issues: {list(set(issues))}"


@dataclass
class TriggerEvent:
    """Event representing a triggered condition"""
    type: str
    priority: int
    reason: str
    confidence: float
    timestamp: float = field(default_factory=time.time)
    context: Optional[Dict[str, Any]] = None


@dataclass
class ModuleMessage:
    """Message for inter-module communication"""
    source: str
    target: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    message_id: Optional[str] = None


@dataclass
class StateChangeNotification:
    """Notification of state changes"""
    change_type: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    affected_modules: List[str] = field(default_factory=list)


@dataclass
class ProgressReport:
    """Report on execution progress"""
    progress_score: float  # 0.0 to 1.0
    direction: Literal["forward", "backward", "stagnant"]
    confidence: float
    evidence: List[str]
    timestamp: float = field(default_factory=time.time)


@dataclass
class VisualChangeReport:
    """Report on visual changes in the UI"""
    change_detected: bool
    change_score: float  # 0.0 to 1.0
    change_areas: List[Dict[str, Any]]  # Regions where changes occurred
    similarity_score: float
    analysis_method: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class CostBudget:
    """Cost budget configuration"""
    total_limit: float = 10.0
    per_hour_limit: float = 5.0
    per_task_limit: float = 2.0
    quality_check_budget: float = 1.0
    warning_threshold: float = 0.8
    stop_threshold: float = 0.95
    current_spent: float = 0.0
    
    def can_afford(self, operation_cost: float) -> bool:
        """Check if we can afford an operation"""
        return (self.current_spent + operation_cost) <= self.total_limit
    
    def spend(self, amount: float) -> None:
        """Record spending"""
        self.current_spent += amount

    def get_usage_percentage(self) -> float:
        """Get current usage as percentage of total limit"""
        return self.current_spent / self.total_limit if self.total_limit > 0 else 0.0


@dataclass
class CostStatus:
    """Current cost tracking status"""
    current: float
    limit: float
    percentage: float
    warning_threshold: float
    over_budget: bool
    time_remaining: Optional[float] = None
    
    @classmethod
    def from_budget(cls, budget: CostBudget) -> 'CostStatus':
        """Create status from budget"""
        percentage = budget.get_usage_percentage()
        return cls(
            current=budget.current_spent,
            limit=budget.total_limit,
            percentage=percentage,
            warning_threshold=budget.warning_threshold,
            over_budget=percentage >= budget.stop_threshold
        )


@dataclass
class DispatchConfig:
    """Configuration for the central dispatcher"""
    enable_quality_monitoring: bool = True
    enable_cost_tracking: bool = True
    enable_adaptive_execution: bool = True
    quality_check_interval: float = 30.0  # seconds
    step_interval: int = 5  # steps
    cost_alert_threshold: float = 0.8
    max_consecutive_failures: int = 3
    enable_visual_monitoring: bool = False
    log_all_interactions: bool = False
    debug_mode: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "enable_quality_monitoring": self.enable_quality_monitoring,
            "enable_cost_tracking": self.enable_cost_tracking,
            "enable_adaptive_execution": self.enable_adaptive_execution,
            "quality_check_interval": self.quality_check_interval,
            "step_interval": self.step_interval,
            "cost_alert_threshold": self.cost_alert_threshold,
            "max_consecutive_failures": self.max_consecutive_failures,
            "enable_visual_monitoring": self.enable_visual_monitoring,
            "log_all_interactions": self.log_all_interactions,
            "debug_mode": self.debug_mode
        }


@dataclass
class ExecutionContext:
    """Complete execution context for decision making"""
    metrics: ExecutionMetrics
    current_subtask: Optional[Node]
    recent_actions: List[Dict[str, Any]]
    quality_reports: List[QualityReport]
    failed_subtasks: List[Node]
    cost_budget: CostBudget
    timestamp: float = field(default_factory=time.time)
    
    @property
    def is_critical_situation(self) -> bool:
        """Check if we're in a critical situation"""
        return (
            self.metrics.consecutive_failures >= 3 or
            self.metrics.error_rate > 0.7 or
            len([r for r in self.quality_reports[-3:] if r.status == QualityStatus.CRITICAL]) >= 2
        )
    
    @property
    def needs_attention(self) -> bool:
        """Check if situation needs attention"""
        return (
            self.metrics.repeated_action_count >= 3 or
            self.metrics.ui_unchanged_steps >= 5 or
            self.metrics.error_rate > 0.5
        )


# Type aliases for better readability
ExecutionResult = Dict[str, Any]
ActionCode = Dict[str, Any]
ObservationDict = Dict[str, Any] 