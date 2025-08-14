"""
Central Dispatcher - Core coordination system for GUI Agent execution.

This module implements the central dispatcher that orchestrates the interaction
between Manager, Worker, Reflector, and other components with intelligent
decision making, cost control, and quality monitoring.
"""

import logging
import time
import platform
from typing import Dict, List, Optional, Tuple, Any
from abc import ABC, abstractmethod

from gui_agents.agents.dispatch_types import (
    SituationAssessment, ExecutionMetrics, QualityCheckContext, QualityReport,
    QualityCheckConfig, ReplanContext, DecisionType, TriggerReason,
    ReplanStrategy, ExecutionContext, CostBudget, ProgressReport,
    VisualChangeReport, ExecutionResult, ActionCode, ObservationDict,
    RecommendationType, QualityStatus
)
from gui_agents.agents.global_state import GlobalState
from gui_agents.agents.enhanced_global_state import EnhancedGlobalState
from gui_agents.agents.manager import Manager
from gui_agents.agents.worker import Worker
from gui_agents.agents.grounding import Grounding
from gui_agents.agents.reflector import Reflector
from gui_agents.agents.enhanced_reflector import EnhancedReflector
from gui_agents.agents.hardware_interface import HardwareInterface
from gui_agents.utils.common_utils import (
    Node, parse_single_code_from_string, sanitize_code, extract_first_agent_function
)

logger = logging.getLogger("desktopenv.dispatcher")


class ICentralDispatcher(ABC):
    """Interface for Central Dispatcher implementations"""
    
    @abstractmethod
    def execute_task_step(self, instruction: str, observation: ObservationDict) -> Tuple[Dict, List[ActionCode]]:
        """Execute a single task step"""
        pass
    
    @abstractmethod
    def assess_current_situation(self) -> SituationAssessment:
        """Assess the current execution situation"""
        pass
    
    @abstractmethod
    def trigger_quality_check(self, reason: str) -> QualityReport:
        """Trigger a quality check"""
        pass
    
    @abstractmethod
    def trigger_manager_replan(self, reason: str) -> bool:
        """Trigger manager replan"""
        pass


class ExecutionStateManager:
    """Manages execution state and metrics tracking"""
    
    def __init__(self, global_state: EnhancedGlobalState):
        self.global_state = global_state
        self.metrics = ExecutionMetrics()
        self.last_screenshot_hash: Optional[str] = None
        self.subtask_start_time: float = time.time()
        
    def assess_current_situation(self) -> SituationAssessment:
        """Assess the current execution situation based on metrics and state"""
        needs_replan = self._check_replan_conditions()
        needs_quality_check = self._check_quality_conditions()
        ready_for_execution = self._check_execution_readiness()
        user_intervention_needed = self._check_intervention_conditions()
        
        assessment = SituationAssessment(
            needs_replan=needs_replan,
            needs_quality_check=needs_quality_check,
            ready_for_execution=ready_for_execution,
            user_intervention_needed=user_intervention_needed
        )
        
        # Set specific reasons
        if needs_replan:
            assessment.replan_reason = self._get_replan_reason()
        if needs_quality_check:
            assessment.check_reason = self._get_quality_check_reason()
        if user_intervention_needed:
            assessment.intervention_reason = self._get_intervention_reason()
            
        return assessment
    
    def _check_replan_conditions(self) -> bool:
        """Check if replan is needed"""
        conditions = [
            self.metrics.consecutive_failures >= 3,
            self.metrics.subtask_duration > 300.0,  # 5 minutes max per subtask
            self.metrics.no_progress_steps >= 8,
            self.metrics.error_rate > 0.8
        ]
        
        # Check latest quality report recommendation
        quality_reports = self.global_state.get_quality_reports(1)
        if quality_reports:
            latest_report = QualityReport.from_dict(quality_reports[0])
            conditions.append(latest_report.recommendation.value == "REPLAN")
            
        return any(conditions)
    
    def _check_quality_conditions(self) -> bool:
        """Check if quality check is needed"""
        conditions = [
            self.metrics.steps_since_last_check >= 5,  # Periodic check
            self.metrics.repeated_action_count >= 3,   # Repeated actions
            self.metrics.ui_unchanged_steps >= 4,      # UI not changing
            self.metrics.error_rate > 0.5,             # High error rate
            self.metrics.subtask_steps > 15            # Too many steps in subtask
        ]
        return any(conditions)
    
    def _check_execution_readiness(self) -> bool:
        """Check if ready for normal execution"""
        # Ready if no other urgent conditions and we have a current subtask
        current_subtask = self.global_state.get_current_subtask()
        remaining_subtasks = self.global_state.get_remaining_subtasks()
        
        return (
            current_subtask is not None or 
            (len(remaining_subtasks) > 0)
        ) and not (self._check_replan_conditions() or self._check_intervention_conditions())
    
    def _check_intervention_conditions(self) -> bool:
        """Check if user intervention is needed"""
        conditions = [
            self.metrics.consecutive_failures >= 5,
            self.metrics.total_steps > 100,  # Too many total steps
            self.metrics.cost_spent > 5.0    # Budget exceeded
        ]
        return any(conditions)
    
    def _get_replan_reason(self) -> str:
        """Get specific reason for replan"""
        if self.metrics.consecutive_failures >= 3:
            return TriggerReason.WORKER_CONSECUTIVE_FAIL.value
        elif self.metrics.subtask_duration > 300.0:
            return TriggerReason.SUBTASK_TIMEOUT.value
        elif self.metrics.no_progress_steps >= 8:
            return TriggerReason.NO_PROGRESS.value
        else:
            return TriggerReason.UNHANDLEABLE_ERROR.value
    
    def _get_quality_check_reason(self) -> str:
        """Get specific reason for quality check"""
        if self.metrics.steps_since_last_check >= 5:
            return TriggerReason.PERIODIC.value
        elif self.metrics.repeated_action_count >= 3:
            return TriggerReason.REPEATED_ACTION.value
        elif self.metrics.ui_unchanged_steps >= 4:
            return TriggerReason.NO_PROGRESS.value
        elif self.metrics.subtask_steps > 15:
            return TriggerReason.EXCESSIVE_STEPS.value
        else:
            return TriggerReason.WORKER_CONFUSED.value
    
    def _get_intervention_reason(self) -> str:
        """Get specific reason for user intervention"""
        if self.metrics.consecutive_failures >= 5:
            return "multiple_consecutive_failures"
        elif self.metrics.total_steps > 100:
            return "excessive_total_steps"
        else:
            return "budget_exceeded"
    
    def update_step_metrics(self, success: bool, duration: float, action: str, screenshot_hash: str = ""):
        """Update metrics after a step execution"""
        self.metrics.update_step_metrics(success, duration, action)
        
        # Update UI change detection
        if screenshot_hash:
            if self.last_screenshot_hash and screenshot_hash == self.last_screenshot_hash:
                self.metrics.ui_unchanged_steps += 1
            else:
                self.metrics.ui_unchanged_steps = 0
            self.last_screenshot_hash = screenshot_hash
        
        # Update subtask duration
        self.metrics.subtask_duration = time.time() - self.subtask_start_time
        
        # Update no progress steps
        if not success or self.metrics.ui_unchanged_steps > 0:
            self.metrics.no_progress_steps += 1
        else:
            self.metrics.no_progress_steps = 0
    
    def reset_for_new_subtask(self):
        """Reset metrics for a new subtask"""
        self.metrics.subtask_steps = 0
        self.metrics.repeated_action_count = 0
        self.metrics.ui_unchanged_steps = 0
        self.metrics.no_progress_steps = 0
        self.subtask_start_time = time.time()
        self.metrics.subtask_duration = 0.0
    
    def reset_quality_check_timer(self):
        """Reset the quality check timer"""
        self.metrics.steps_since_last_check = 0


class DecisionTrigger:
    """Handles decision trigger logic and rule evaluation"""
    
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.trigger_history: List[Dict] = []
        
    def evaluate_triggers(self, context: ExecutionContext) -> List[str]:
        """Evaluate all trigger conditions and return triggered events"""
        triggered_events = []
        
        # Check consecutive failures
        if context.metrics.consecutive_failures >= 3:
            triggered_events.append(TriggerReason.WORKER_CONSECUTIVE_FAIL.value)
        
        # Check repeated actions
        if context.metrics.repeated_action_count >= 3:
            triggered_events.append(TriggerReason.REPEATED_ACTION.value)
        
        # Check excessive steps
        if context.metrics.subtask_steps > 15:
            triggered_events.append(TriggerReason.EXCESSIVE_STEPS.value)
        
        # Check time exceeded
        if context.metrics.subtask_duration > 300.0:
            triggered_events.append(TriggerReason.TIME_EXCEEDED.value)
        
        # Check periodic quality check
        if context.metrics.steps_since_last_check >= 5:
            triggered_events.append(TriggerReason.PERIODIC.value)
        
        # Check UI unchanged
        if context.metrics.ui_unchanged_steps >= 4:
            triggered_events.append(TriggerReason.NO_PROGRESS.value)
        
        # Record trigger history
        if triggered_events:
            self.trigger_history.append({
                "timestamp": time.time(),
                "events": triggered_events,
                "context": {
                    "total_steps": context.metrics.total_steps,
                    "error_rate": context.metrics.error_rate
                }
            })
        
        return triggered_events


class InformationCoordinator:
    """Coordinates information flow between modules"""
    
    def __init__(self, global_state: EnhancedGlobalState):
        self.global_state = global_state
        self.message_log: List[Dict] = []
        
    def coordinate_module_interaction(self, source: str, target: str, data: Dict) -> Any:
        """Coordinate interaction between modules"""
        interaction = {
            "timestamp": time.time(),
            "source": source,
            "target": target,
            "data_type": type(data).__name__,
            "success": True
        }
        
        try:
            # Log the interaction
            self.global_state.log_operation(
                module="coordinator",
                operation=f"{source}_to_{target}",
                data={"interaction": f"{source} -> {target}"}
            )
            
            self.message_log.append(interaction)
            return True
            
        except Exception as e:
            interaction["success"] = False
            interaction["error"] = str(e)
            self.message_log.append(interaction)
            logger.error(f"Module interaction failed: {source} -> {target}: {e}")
            return False
    
    def broadcast_state_change(self, change_type: str, data: Dict):
        """Broadcast state changes to interested modules"""
        notification = {
            "change_type": change_type,
            "data": data,
            "timestamp": time.time()
        }
        
        self.global_state.log_operation(
            module="coordinator",
            operation="state_change_broadcast",
            data=notification
        )


class CostController:
    """Controls and monitors cost of operations"""
    
    def __init__(self, daily_budget: float = 10.0):
        self.budget = CostBudget(total_limit=daily_budget)
        self.operation_costs: Dict[str, float] = {
            "periodic_check": 0.02,
            "light_quality_check": 0.05,
            "deep_quality_check": 0.15,
            "light_replan": 0.10,
            "medium_replan": 0.25,
            "heavy_replan": 0.50
        }
        
    def can_afford_operation(self, operation_type: str, estimated_cost: Optional[float] = None) -> bool:
        """Check if we can afford an operation"""
        cost = estimated_cost or self.operation_costs.get(operation_type, 0.01)
        return self.budget.can_afford(cost)
    
    def record_operation_cost(self, operation_type: str, actual_cost: float):
        """Record the actual cost of an operation"""
        self.budget.spend(actual_cost)
        logger.info(f"Operation '{operation_type}' cost: ${actual_cost:.4f}, remaining budget: ${self.budget.total_limit - self.budget.current_spent:.4f}")
    
    def optimize_quality_check_config(self, trigger_reason: str) -> QualityCheckConfig:
        """Optimize quality check configuration based on trigger and budget"""
        base_config = QualityCheckConfig()
        
        # Adjust based on budget constraints
        if not self.can_afford_operation("deep_quality_check", base_config.estimated_cost):
            # Fallback to lighter configuration
            base_config.use_lightweight_model = True
            base_config.deep_reasoning = False
            base_config.estimated_cost = 0.02
            logger.warning("Falling back to lightweight quality check due to budget constraints")
        
        return base_config
    
    def get_budget_status(self) -> Dict[str, float]:
        """Get current budget status"""
        return {
            "daily_budget": self.budget.total_limit,
            "current_spent": self.budget.current_spent,
            "remaining": self.budget.total_limit - self.budget.current_spent,
            "usage_percentage": (self.budget.current_spent / self.budget.total_limit) * 100
        }


class CentralDispatcher(ICentralDispatcher):
    """
    Central coordination system for GUI Agent execution.
    
    Orchestrates the interaction between Manager, Worker, Reflector, and other
    components with intelligent decision making and cost control.
    """
    
    def __init__(
        self,
        platform: str = platform.system().lower(),
        tools_dict: Optional[Dict] = None,
        global_state: Optional[EnhancedGlobalState] = None,
        **kwargs
    ):
        """Initialize the Central Dispatcher with all required components"""
        self.platform = platform
        self.tools_dict = tools_dict or {}
        
        # Initialize components (will be set up in setup_components)
        self.global_state = global_state
        self.manager: Optional[Manager] = None
        self.worker: Optional[Worker] = None
        self.grounding: Optional[Grounding] = None
        self.reflector: Optional[Reflector] = None
        self.enhanced_reflector: Optional[EnhancedReflector] = None
        self.hardware_interface: Optional[HardwareInterface] = None
        
        # Core management modules
        self.state_manager: Optional[ExecutionStateManager] = None
        self.decision_trigger: Optional[DecisionTrigger] = None
        self.info_coordinator: Optional[InformationCoordinator] = None
        self.cost_controller = CostController()
        
        # Execution state
        self.current_instruction = ""
        self.is_initialized = False
        
        # Setup components if global_state is provided
        if self.global_state:
            self.setup_components(**kwargs)
    
    def setup_components(self, **kwargs):
        """Setup all components after initialization"""
        if self.is_initialized:
            return
            
        # Ensure we have an EnhancedGlobalState
        if not isinstance(self.global_state, EnhancedGlobalState):
            raise RuntimeError("CentralDispatcher requires an EnhancedGlobalState instance")
            
        # Initialize core management modules
        self.state_manager = ExecutionStateManager(self.global_state)
        self.decision_trigger = DecisionTrigger(self)
        self.info_coordinator = InformationCoordinator(self.global_state)
        
        # Initialize agent components (these would be injected in real implementation)
        # For now, we'll create placeholders that would be set by the calling code
        logger.info("Central Dispatcher components initialized")
        self.is_initialized = True
    
    def set_components(
        self,
        manager: Manager,
        worker: Worker,
        grounding: Grounding,
        reflector: Reflector,
        hardware_interface: HardwareInterface,
        enhanced_reflector: Optional[EnhancedReflector] = None
    ):
        """Set the agent components after initialization"""
        self.manager = manager
        self.worker = worker
        self.grounding = grounding
        self.reflector = reflector
        self.hardware_interface = hardware_interface
        
        # Set enhanced reflector or create from tools_dict
        if enhanced_reflector:
            self.enhanced_reflector = enhanced_reflector
        elif self.tools_dict:
            # Create enhanced reflector from tools_dict if available
            try:
                self.enhanced_reflector = EnhancedReflector(self.tools_dict)
                logger.info("Created EnhancedReflector from tools_dict")
            except Exception as e:
                logger.warning(f"Failed to create EnhancedReflector: {e}")
                self.enhanced_reflector = None
        else:
            self.enhanced_reflector = None
            
        logger.info("Agent components set successfully")
    
    def execute_task_step(self, instruction: str, observation: ObservationDict) -> Tuple[Dict, List[ActionCode]]:
        """
        Execute a single task step with intelligent decision making.
        
        This is the main entry point that replaces the predict method in AgentSNormal.
        """
        if not self.is_initialized or not self.global_state:
            raise RuntimeError("Dispatcher not properly initialized")
        
        start_time = time.time()
        
        try:
            # Initialize or update instruction
            if instruction != self.current_instruction:
                self._initialize_new_task(instruction)
            
            # Update observation
            self._update_observation(observation)
            
            # Assess current situation
            situation = self.assess_current_situation()
            
            # Decision dispatch based on situation
            if situation.needs_replan:
                result = self._handle_replan(situation)
            elif situation.needs_quality_check:
                result = self._handle_quality_check(situation)
            elif situation.ready_for_execution:
                result = self._handle_normal_execution(situation)
            else:
                result = self._handle_user_intervention(situation)
            
            # Record execution time
            execution_time = time.time() - start_time
            self.global_state.log_operation(
                module="dispatcher",
                operation="execute_task_step",
                data={"duration": execution_time, "situation": situation.check_reason or situation.replan_reason or "normal"}
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in execute_task_step: {e}")
            # Return safe fallback
            return {}, [{"type": "Wait", "duration": 1000}]
    
    def assess_current_situation(self) -> SituationAssessment:
        """Assess the current execution situation"""
        if not self.state_manager:
            raise RuntimeError("State manager not initialized")
        return self.state_manager.assess_current_situation()
    
    def trigger_quality_check(self, reason: str) -> QualityReport:
        """Trigger a quality check with cost optimization"""
        if not all([self.cost_controller, self.state_manager, self.global_state]):
            raise RuntimeError("Required components not initialized")
        
        # Get optimized configuration
        check_config = self.cost_controller.optimize_quality_check_config(reason)
        
        # Create enhanced context with trigger reason
        context = QualityCheckContext(
            recent_actions=self.global_state.get_recent_actions(5) if self.global_state else [],
            current_screenshot=self.global_state.get_screenshot() if self.global_state else None,
            subtask_goal=self.global_state.get_current_subtask() if self.global_state else None,
            execution_history=self.global_state.get_execution_history(10) if self.global_state else [],
            metrics=self.state_manager.metrics if self.state_manager else ExecutionMetrics()
        )
        
        # Add trigger reason to context for EnhancedReflector
        if hasattr(context, 'trigger_reason'):
            context.trigger_reason = reason # type: ignore
        
        # Perform quality check using EnhancedReflector
        quality_report = self._perform_quality_check(context, check_config)
        
        # Record cost and reset timer
        self.cost_controller.record_operation_cost("quality_check", quality_report.cost_estimate)
        self.state_manager.reset_quality_check_timer() if self.state_manager else None
        
        # Store report
        self.global_state.add_quality_report(quality_report) if self.global_state else None
        
        return quality_report
    
    def trigger_manager_replan(self, reason: str) -> bool:
        """Trigger manager replan with appropriate strategy"""
        if not all([self.manager, self.cost_controller, self.state_manager, self.global_state]):
            raise RuntimeError("Required components not initialized")
        
        try:
            # Build replan context
            context = ReplanContext(
                failure_reason=reason,
                failed_subtasks=self.global_state.get_failed_subtasks() if self.global_state else [],
                completed_subtasks=self.global_state.get_completed_subtasks() if self.global_state else [],
                remaining_subtasks=self.global_state.get_remaining_subtasks() if self.global_state else [],
                execution_history=self.global_state.get_execution_history() if self.global_state else [],
                quality_reports=[QualityReport.from_dict(r) for r in self.global_state.get_quality_reports()] if self.global_state else [],
                current_metrics=self.state_manager.metrics if self.state_manager else ExecutionMetrics()
            )
            
            # Determine replan strategy
            strategy = self._determine_replan_strategy(reason)
            
            # Execute replan based on strategy
            if strategy == ReplanStrategy.HEAVY_ADJUSTMENT:
                # Use existing manager method for complete replan
                manager_info, new_plan = self.manager.get_action_queue( # type: ignore
                    Tu=self.current_instruction,
                    observation=self.global_state.get_obs_for_manager() if self.global_state else {},
                    running_state=self.global_state.get_running_state() if self.global_state else "",
                    failed_subtask=self.global_state.get_latest_failed_subtask() if self.global_state else None,
                    completed_subtasks_list=self.global_state.get_completed_subtasks() if self.global_state else [],
                    remaining_subtasks_list=self.global_state.get_remaining_subtasks() if self.global_state else []
                ) 
                
                # Record cost
                estimated_cost = 0.50  # Heavy replan cost
                self.cost_controller.record_operation_cost("heavy_replan", estimated_cost)
            else:
                # For light/medium adjustments, we'd implement those methods
                # For now, fallback to heavy replan
                logger.warning(f"Strategy {strategy} not fully implemented, using heavy replan")
                return self.trigger_manager_replan(reason)
            
            # Update state with new plan
            self.global_state.set_remaining_subtasks(new_plan) if self.global_state else None
            self._reset_execution_state()
            
            logger.info(f"Replan completed with strategy {strategy}, new plan has {len(new_plan)} subtasks")
            return True
            
        except Exception as e:
            logger.error(f"Replan failed: {e}")
            return False
    
    # Private helper methods
    
    def _initialize_new_task(self, instruction: str):
        """Initialize state for a new task"""
        self.current_instruction = instruction
        if self.global_state:
            self.global_state.set_Tu(instruction)
        
        # Reset metrics for new task
        if self.state_manager:
            self.state_manager.metrics = ExecutionMetrics()
            self.state_manager.reset_for_new_subtask()
        
        logger.info(f"Initialized new task: {instruction[:100]}...")
    
    def _update_observation(self, observation: ObservationDict):
        """Update observation data"""
        # Update screenshot if provided
        if "screenshot" in observation and observation["screenshot"]:
            # In real implementation, this would update the global state
            pass
    
    def _handle_normal_execution(self, situation: SituationAssessment) -> Tuple[Dict, List[ActionCode]]:
        """Handle normal worker execution"""
        if not all([self.worker, self.grounding, self.global_state, self.state_manager]):
            raise RuntimeError("Required components not initialized")
        
        # Check if we need to get next subtask
        current_subtask = self.global_state.get_current_subtask() if self.global_state else None
        if not current_subtask:
            remaining_subtasks = self.global_state.get_remaining_subtasks() if self.global_state else []
            if remaining_subtasks:
                # Get next subtask
                current_subtask = remaining_subtasks.pop(0)
                self.global_state.set_current_subtask(current_subtask) if self.global_state else None
                self.global_state.set_remaining_subtasks(remaining_subtasks) if self.global_state else None
                self.state_manager.reset_for_new_subtask() if self.state_manager else None
            else:
                # No more subtasks, task complete
                return {}, [{"type": "Done"}]
        
        # Generate worker action
        worker_info = self.worker.generate_next_action( # type: ignore
            Tu=self.current_instruction,
            search_query=self.global_state.get_search_query() if self.global_state else "",
            subtask=current_subtask.name,
            subtask_info=current_subtask.info,
            future_tasks=self.global_state.get_remaining_subtasks() if self.global_state else [],
            done_task=self.global_state.get_completed_subtasks() if self.global_state else [],
            obs=self.global_state.get_obs_for_manager() if self.global_state else {}
        )
        
        # Ground the action
        try:
            self.grounding.assign_coordinates(worker_info["executor_plan"], self.global_state.get_obs_for_grounding()) if self.grounding and self.global_state else None
            plan_code = parse_single_code_from_string(worker_info["executor_plan"].split("Grounded Action")[-1])
            plan_code = sanitize_code(plan_code)
            plan_code = extract_first_agent_function(plan_code)
            if plan_code:
                exec_code = eval(plan_code)
            else:
                raise ValueError("No valid agent function found")
        except Exception as e:
            logger.error(f"Grounding error: {e}")
            exec_code = {"type": "Wait", "duration": 1000}
        
        # Update metrics
        success = "fail" not in exec_code.get("type", "").lower()
        action_str = exec_code.get("type", "unknown")
        self.state_manager.update_step_metrics(success, 1.0, action_str) if self.state_manager else None
        
        # Handle action results
        if "done" in exec_code.get("type", "").lower():
            # Subtask completed
            self.global_state.add_completed_subtask(current_subtask) if self.global_state else None
            self.global_state.set_current_subtask(None) if self.global_state else None
            self.state_manager.reset_for_new_subtask() if self.state_manager else None
            
        elif "fail" in exec_code.get("type", "").lower():
            # Subtask failed
            self.global_state.add_failed_subtask_with_info( # type: ignore
                name=current_subtask.name,
                info=current_subtask.info,
                error_type="WORKER_FAIL",
                error_message="Worker returned fail action"
            )
            
        return worker_info, [exec_code]
    
    def _handle_quality_check(self, situation: SituationAssessment) -> Tuple[Dict, List[ActionCode]]:
        """Handle quality check and respond to results"""
        quality_report = self.trigger_quality_check(situation.check_reason or "unknown")
        
        # Process quality report
        if quality_report.recommendation == RecommendationType.REPLAN:
            # Escalate to replan
            situation.needs_replan = True
            situation.replan_reason = f"quality_check_{quality_report.status.value}"
            return self._handle_replan(situation)
        elif quality_report.recommendation == RecommendationType.ADJUST:
            # Make light adjustment (for now, continue normal execution)
            logger.info("Quality check suggests adjustment, continuing with monitoring")
            situation.ready_for_execution = True
            return self._handle_normal_execution(situation)
        else:
            # Continue normal execution
            situation.ready_for_execution = True
            return self._handle_normal_execution(situation)
    
    def _handle_replan(self, situation: SituationAssessment) -> Tuple[Dict, List[ActionCode]]:
        """Handle replan request"""
        success = self.trigger_manager_replan(situation.replan_reason or "unknown")
        
        if success:
            # Continue with new plan
            situation.ready_for_execution = True
            return self._handle_normal_execution(situation)
        else:
            # Replan failed, request user intervention
            return self._handle_user_intervention(situation)
    
    def _handle_user_intervention(self, situation: SituationAssessment) -> Tuple[Dict, List[ActionCode]]:
        """Handle user intervention request"""
        reason = situation.intervention_reason or "unknown_reason"
        logger.warning(f"Requesting user intervention: {reason}")
        
        return {
            "intervention_requested": True,
            "reason": reason,
            "budget_status": self.cost_controller.get_budget_status()
        }, [{"type": "UserTakeover", "message": f"User intervention needed: {reason}"}]
    
    def _perform_quality_check(self, context: QualityCheckContext, config: QualityCheckConfig) -> QualityReport:
        """Perform quality check using EnhancedReflector or fallback implementation"""
        
        # Try to use EnhancedReflector if available
        if self.enhanced_reflector:
            try:
                logger.info("Performing quality check using EnhancedReflector")
                return self.enhanced_reflector.comprehensive_check(context, config)
            except Exception as e:
                logger.error(f"EnhancedReflector quality check failed: {e}")
                # Fall through to basic implementation
        
        # Fallback to basic rule-based implementation
        logger.info("Using fallback rule-based quality check")
        issues = []
        suggestions = []
        
        # Basic rule-based checks
        if context.metrics.repeated_action_count >= 3:
            issues.append("Repeated actions detected")
            suggestions.append("Try alternative approach to current subtask")
        
        if context.metrics.ui_unchanged_steps >= 4:
            issues.append("UI appears unchanged for multiple steps")
            suggestions.append("Verify if actions are having intended effect")
        
        if context.metrics.error_rate > 0.5:
            issues.append("High error rate detected")
            suggestions.append("Consider breaking down current subtask")
        
        # Determine status and recommendation
        if len(issues) >= 3 or context.metrics.consecutive_failures >= 3:
            status = QualityStatus.CRITICAL
            recommendation = RecommendationType.REPLAN
        elif len(issues) >= 1:
            status = QualityStatus.CONCERNING
            recommendation = RecommendationType.ADJUST
        else:
            status = QualityStatus.GOOD
            recommendation = RecommendationType.CONTINUE
        
        return QualityReport(
            status=status,
            recommendation=recommendation,
            confidence=0.8,
            issues=issues,
            suggestions=suggestions,
            cost_estimate=config.estimated_cost,
            trigger_reason=getattr(context, 'trigger_reason', None)
        )
    
    def perform_progress_check(self, recent_actions: List[Dict]) -> ProgressReport:
        """Perform progress check using EnhancedReflector or basic analysis"""
        if self.enhanced_reflector:
            try:
                return self.enhanced_reflector.lightweight_progress_check(recent_actions)
            except Exception as e:
                logger.error(f"EnhancedReflector progress check failed: {e}")
        
        # Fallback to basic progress analysis
        if not recent_actions:
            return ProgressReport(
                progress_score=0.0,
                direction="stagnant",
                confidence=0.5,
                evidence=["No recent actions available"]
            )
        
        # Basic analysis
        success_count = sum(1 for action in recent_actions if action.get('success', True))
        total_actions = len(recent_actions)
        success_rate = success_count / total_actions if total_actions > 0 else 0.0
        
        if success_rate > 0.7:
            return ProgressReport(
                progress_score=0.5,
                direction="forward",
                confidence=0.6,
                evidence=[f"Good success rate: {success_rate:.1%}"]
            )
        elif success_rate < 0.3:
            return ProgressReport(
                progress_score=-0.3,
                direction="backward",
                confidence=0.6,
                evidence=[f"Low success rate: {success_rate:.1%}"]
            )
        else:
            return ProgressReport(
                progress_score=0.0,
                direction="stagnant",
                confidence=0.5,
                evidence=[f"Moderate success rate: {success_rate:.1%}"]
            )
    
    def analyze_visual_changes(self, current_screenshot: bytes, previous_screenshot: Optional[bytes] = None) -> VisualChangeReport:
        """Analyze visual changes using EnhancedReflector"""
        if self.enhanced_reflector:
            try:
                return self.enhanced_reflector.visual_change_analysis(current_screenshot, previous_screenshot)
            except Exception as e:
                logger.error(f"EnhancedReflector visual analysis failed: {e}")
        
        # Fallback to basic visual analysis
        import hashlib
        current_hash = hashlib.md5(current_screenshot).hexdigest()
        
        if previous_screenshot:
            previous_hash = hashlib.md5(previous_screenshot).hexdigest()
            change_detected = current_hash != previous_hash
            change_score = 0.5 if change_detected else 0.0
            similarity_score = 0.5 if change_detected else 1.0
        else:
            change_detected = False
            change_score = 0.0
            similarity_score = 1.0
        
        return VisualChangeReport(
            change_detected=change_detected,
            change_score=change_score,
            change_areas=[],
            similarity_score=similarity_score,
            analysis_method="basic_hash_comparison"
        )
    
    def _determine_replan_strategy(self, reason: str) -> ReplanStrategy:
        """Determine appropriate replan strategy based on reason"""
        if reason in [TriggerReason.WORKER_CONSECUTIVE_FAIL.value, TriggerReason.UNHANDLEABLE_ERROR.value]:
            return ReplanStrategy.HEAVY_ADJUSTMENT
        elif reason in [TriggerReason.SUBTASK_TIMEOUT.value, TriggerReason.NO_PROGRESS.value]:
            return ReplanStrategy.MEDIUM_ADJUSTMENT
        else:
            return ReplanStrategy.LIGHT_ADJUSTMENT
    
    def _reset_execution_state(self):
        """Reset execution state after replan"""
        if self.state_manager:
            self.state_manager.reset_for_new_subtask()
            # Reset some counters but keep total step count
            self.state_manager.metrics.consecutive_failures = 0
            self.state_manager.metrics.repeated_action_count = 0
            self.state_manager.metrics.no_progress_steps = 0 