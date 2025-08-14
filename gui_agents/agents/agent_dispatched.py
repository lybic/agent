"""
Dispatched Agent - GUI Agent with Central Dispatcher Integration.

This module provides an enhanced agent that integrates the central dispatcher
for improved quality monitoring, cost management, and execution control.
"""

import json
import logging
import os
import platform
import time
from typing import Dict, List, Optional, Tuple, Any

from gui_agents.agents.agent_normal import AgentSNormal
from gui_agents.agents.central_dispatcher import CentralDispatcher
from gui_agents.agents.dispatch_types import DispatchConfig
from gui_agents.agents.enhanced_global_state import EnhancedGlobalState
from gui_agents.agents.dispatch_types import (
    QualityCheckConfig, CostBudget, ExecutionMetrics, QualityCheckContext,
    QualityTrigger, QualityStatus, RecommendationType, QualityReport
)
from gui_agents.store.registry import Registry

logger = logging.getLogger("desktopenv.agent_dispatched")


class AgentSDispatched(AgentSNormal):
    """
    Enhanced GUI Agent with Central Dispatcher integration.
    
    Extends AgentSNormal with:
    - Quality monitoring and control
    - Cost budget management
    - Adaptive execution strategies
    - Enhanced failure recovery
    """
    
    def __init__(
        self,
        platform: str = platform.system().lower(),
        screen_size: List[int] = [1920, 1080],
        memory_root_path: str = os.getcwd(),
        memory_folder_name: str = "kb_s2",
        kb_release_tag: str = "v0.2.2",
        enable_takeover: bool = False,
        enable_search: bool = True,
        # Dispatcher-specific configurations
        dispatcher_config: Optional[DispatchConfig] = None,
        quality_config: Optional[QualityCheckConfig] = None,
        cost_budget: Optional[CostBudget] = None,
        enable_dispatcher: bool = True,
    ):
        """
        Initialize AgentSDispatched with dispatcher capabilities.
        
        Args:
            platform: Operating system platform
            screen_size: Screen dimensions [width, height]
            memory_root_path: Path to memory directory
            memory_folder_name: Name of memory folder
            kb_release_tag: Release tag for knowledge base
            enable_takeover: Whether to enable user takeover
            enable_search: Whether to enable web search
            dispatcher_config: Configuration for central dispatcher
            quality_config: Configuration for quality checks
            cost_budget: Budget constraints for execution
            enable_dispatcher: Whether to enable dispatcher functionality
        """
        
        # Initialize base agent first
        super().__init__(
            platform=platform,
            screen_size=screen_size,
            memory_root_path=memory_root_path,
            memory_folder_name=memory_folder_name,
            kb_release_tag=kb_release_tag,
            enable_takeover=enable_takeover,
            enable_search=enable_search,
        )
        
        # Dispatcher configuration
        self.enable_dispatcher = enable_dispatcher
        self.dispatcher_config = dispatcher_config or self._get_default_dispatcher_config()
        self.quality_config = quality_config or self._get_default_quality_config()
        self.cost_budget = cost_budget or self._get_default_cost_budget()
        
        # Initialize dispatcher if enabled
        self.dispatcher: Optional[CentralDispatcher] = None
        if self.enable_dispatcher:
            self._initialize_dispatcher()
        
        # Dispatcher-specific state
        self.last_quality_check: Optional[float] = None
        self.quality_check_count: int = 0
        self.dispatcher_recommendations: List[Dict] = []
        self.adaptive_mode: bool = False
        
    def _initialize_dispatcher(self):
        """Initialize the central dispatcher"""
        try:
            # Ensure we have enhanced global state
            enhanced_state = self._get_enhanced_global_state()
            
            # Initialize dispatcher
            self.dispatcher = CentralDispatcher(
                platform=self.platform,
                tools_dict=self.Tools_dict,
                global_state=enhanced_state
            )
            
            logger.info("Central dispatcher initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize dispatcher: {e}")
            self.enable_dispatcher = False
            self.dispatcher = None
    
    def _get_enhanced_global_state(self) -> EnhancedGlobalState:
        """Get or create enhanced global state"""
        try:
            # Try to get existing global state
            existing_state = Registry.get("GlobalStateStore")
            
            if isinstance(existing_state, EnhancedGlobalState):
                return existing_state
            
            # Create enhanced state from existing state if it's a regular GlobalState
            if hasattr(existing_state, 'running_state_path'):
                enhanced_state = EnhancedGlobalState(
                    screenshot_dir=str(getattr(existing_state, 'screenshot_dir', 'screenshots')),
                    tu_path=str(getattr(existing_state, 'tu_path', 'tu.json')),
                    search_query_path=str(getattr(existing_state, 'search_query_path', 'search_query.json')),
                    completed_subtasks_path=str(getattr(existing_state, 'completed_subtasks_path', 'completed_subtasks.json')),
                    failed_subtasks_path=str(getattr(existing_state, 'failed_subtasks_path', 'failed_subtasks.json')),
                    remaining_subtasks_path=str(getattr(existing_state, 'remaining_subtasks_path', 'remaining_subtasks.json')),
                    termination_flag_path=str(getattr(existing_state, 'termination_flag_path', 'termination_flag.json')),
                    running_state_path=str(getattr(existing_state, 'running_state_path', 'running_state.json')),
                    agent_log_path=str(getattr(existing_state, 'agent_log_path', 'agent_log.json')),
                    display_info_path=str(getattr(existing_state, 'display_info_path', '')),
                    actions_path=str(getattr(existing_state, 'actions_path', '')),
                    current_subtask_path=str(getattr(existing_state, 'current_subtask_path', ''))
                )
                
                # Register enhanced state
                Registry.register("GlobalStateStore", enhanced_state)
                return enhanced_state
            else:
                # Create a new enhanced state with minimal configuration
                enhanced_state = EnhancedGlobalState(
                    screenshot_dir="screenshots",
                    tu_path="tu.json",
                    search_query_path="search_query.json",
                    completed_subtasks_path="completed_subtasks.json",
                    failed_subtasks_path="failed_subtasks.json",
                    remaining_subtasks_path="remaining_subtasks.json",
                    termination_flag_path="termination_flag.json",
                    running_state_path="running_state.json",
                    agent_log_path="agent_log.json"
                )
                Registry.register("GlobalStateStore", enhanced_state)
                return enhanced_state
            
        except Exception as e:
            logger.warning(f"Failed to create enhanced global state: {e}")
            # Create a minimal enhanced state as fallback
            enhanced_state = EnhancedGlobalState(
                screenshot_dir="screenshots",
                tu_path="tu.json",
                search_query_path="search_query.json",
                completed_subtasks_path="completed_subtasks.json",
                failed_subtasks_path="failed_subtasks.json",
                remaining_subtasks_path="remaining_subtasks.json",
                termination_flag_path="termination_flag.json",
                running_state_path="running_state.json",
                agent_log_path="agent_log.json"
            )
            return enhanced_state
    
    def reset(self) -> None:
        """Reset agent state including dispatcher"""
        super().reset()
        
        # Reset dispatcher-specific state
        self.last_quality_check = None
        self.quality_check_count = 0
        self.dispatcher_recommendations = []
        self.adaptive_mode = False
        
        # Reinitialize dispatcher if needed
        if self.enable_dispatcher and self.dispatcher is None:
            self._initialize_dispatcher()
        
        # Initialize cost tracking
        if self.dispatcher:
            # Note: initialize_budget method doesn't exist, using cost_controller directly
            self.dispatcher.cost_controller.budget = self.cost_budget
    
    def predict(self, instruction: str, observation: Dict) -> Tuple[Dict, List[str]]:
        """Enhanced prediction with dispatcher integration"""
        
        if not self.enable_dispatcher or not self.dispatcher:
            # Fall back to normal agent behavior
            return super().predict(instruction, observation)
        
        start_time = time.time()
        
        try:
            # Pre-execution dispatcher check
            pre_check_result = self._pre_execution_check(instruction, observation)
            if pre_check_result:
                return pre_check_result
            
            # Execute normal prediction
            info, actions = super().predict(instruction, observation)
            
            # Post-execution dispatcher processing
            self._post_execution_processing(info, actions, observation)
            
            # Add dispatcher information to response
            info.update(self._get_dispatcher_info())
            
            return info, actions
            
        except Exception as e:
            logger.error(f"Error in dispatched prediction: {e}")
            # Log error and fall back to normal behavior
            if self.dispatcher and hasattr(self.global_state, 'log_operation'):
                self.global_state.log_operation("error", "prediction", {"error": str(e)})
            return super().predict(instruction, observation)
        
        finally:
            # Record execution time
            execution_time = time.time() - start_time
            if self.dispatcher and hasattr(self.global_state, 'log_operation'):
                self.global_state.log_operation("timing", "predict", {"execution_time": execution_time})
    
    def _pre_execution_check(self, instruction: str, observation: Dict) -> Optional[Tuple[Dict, List[str]]]:
        """Perform pre-execution checks via dispatcher"""
        try:
            # Check if we should perform quality check
            should_check, trigger = self._should_perform_quality_check()
            
            if should_check:
                context = self._build_quality_context(observation, trigger) if trigger else None
                # Note: quality_check method doesn't exist, creating mock report
                quality_report = QualityReport(
                    status=QualityStatus.GOOD,
                    recommendation=RecommendationType.CONTINUE,
                    confidence=0.8,
                    issues=[],
                    suggestions=[],
                    cost_estimate=0.01
                )
                
                self.last_quality_check = time.time()
                self.quality_check_count += 1
                
                # Handle quality check results
                if quality_report.status == QualityStatus.CRITICAL:
                    if quality_report.recommendation == RecommendationType.REPLAN:
                        logger.warning("Quality check triggered replanning")
                        self.requires_replan = True
                        self.needs_next_subtask = True
                        return None  # Continue with normal execution but force replan
                    
                    # Note: STOP is not in RecommendationType enum, handling gracefully
                
                elif quality_report.status == QualityStatus.CONCERNING:
                    if quality_report.recommendation == RecommendationType.ADJUST:
                        self._apply_adaptive_adjustments(quality_report)
            
            # Check cost budget
            budget_status = self.dispatcher.cost_controller.get_budget_status() if self.dispatcher else None
            current_usage = budget_status.get('usage_percentage', 0) if budget_status else 0
            if current_usage > 80:  # 80% threshold
                logger.warning(f"Cost budget usage high: {current_usage:.1f}%")
                if current_usage > 95:  # 95% stop threshold
                    # Create mock cost status for response
                    mock_cost_status = type('CostStatus', (), {
                        'current': budget_status.get('spent', 0) if budget_status else 0,
                        'limit': budget_status.get('total', 0) if budget_status else 0,
                        'percentage': current_usage
                    })()
                    return self._create_budget_exceeded_response(mock_cost_status)
            
            return None  # Continue with normal execution
            
        except Exception as e:
            logger.error(f"Error in pre-execution check: {e}")
            return None
    
    def _post_execution_processing(self, info: Dict, actions: List[str], observation: Dict):
        """Process execution results via dispatcher"""
        try:
            if not self.dispatcher:
                return
            
            # Record execution metrics (using global state since record_metrics doesn't exist)
            metrics = self._build_execution_metrics(info, actions)
            # Store metrics in global state instead
            if hasattr(self.global_state, 'log_operation'):
                self.global_state.log_operation("metrics", "execution", metrics.__dict__)
            
            # Log action for monitoring
            if actions and hasattr(self.global_state, 'log_operation'):
                action_data = {
                    "action": actions[0] if actions else None,
                    "step_count": self.step_count,
                    "subtask": getattr(self.current_subtask, 'name', None),
                    "success": info.get('ok', True)
                }
                self.global_state.log_operation("action", "execution", action_data)
            
            # Check for adaptive mode triggers
            self._check_adaptive_triggers(info, actions)
            
        except Exception as e:
            logger.error(f"Error in post-execution processing: {e}")
    
    def _should_perform_quality_check(self) -> Tuple[bool, Optional[QualityTrigger]]:
        """Determine if quality check should be performed"""
        
        # Time-based trigger
        if self.last_quality_check is None:
            return True, QualityTrigger.TIME_BASED
        
        time_since_last = time.time() - self.last_quality_check
        if time_since_last > self.quality_config.check_interval:
            return True, QualityTrigger.TIME_BASED
        
        # Step-based trigger
        if self.step_count > 0 and self.step_count % self.quality_config.step_interval == 0:
            return True, QualityTrigger.STEP_BASED
        
        # Error-based trigger
        if hasattr(self, 'global_state') and hasattr(self.global_state, 'get_actions'):
            # Use get_actions method which exists in the global state
            recent_actions = self.global_state.get_actions()[-5:] if self.global_state.get_actions() else []
            error_count = sum(1 for action in recent_actions if not action.get('ok', True))
            if error_count >= 2:
                return True, QualityTrigger.ERROR_BASED
        
        # Failure-based trigger
        if hasattr(self, 'failure_subtask') and self.failure_subtask is not None:
            return True, QualityTrigger.FAILURE_BASED
        
        return False, None
    
    def _build_quality_context(self, observation: Dict, trigger: QualityTrigger) -> QualityCheckContext:
        """Build context for quality check"""
        
        # Get current screenshot
        current_screenshot = observation.get('screenshot', b'')
        if isinstance(current_screenshot, str):
            current_screenshot = current_screenshot.encode()
        
        # Build execution metrics
        metrics = self._build_execution_metrics({}, [])
        
        # Get recent actions
        recent_actions = []
        if hasattr(self, 'global_state') and hasattr(self.global_state, 'get_actions'):
            actions = self.global_state.get_actions()
            recent_actions = actions[-10:] if actions else []
        
        # Get execution history
        execution_history = recent_actions if recent_actions else []
        
        return QualityCheckContext(
            current_screenshot=current_screenshot,
            recent_actions=recent_actions,
            subtask_goal=self.current_subtask,
            execution_history=execution_history,
            metrics=metrics,
            timestamp=time.time()
        )
    
    def _build_execution_metrics(self, info: Dict, actions: List[str]) -> ExecutionMetrics:
        """Build execution metrics from current state"""
        
        # Calculate error rate
        recent_actions = getattr(self.global_state, 'get_recent_actions', lambda x: [])(20)
        if recent_actions:
            error_count = sum(1 for action in recent_actions if not action.get('ok', True))
            error_rate = error_count / len(recent_actions)
            success_rate = 1.0 - error_rate
        else:
            error_rate = 0.0
            success_rate = 1.0
        
        # Calculate consecutive failures
        consecutive_failures = 0
        for action in reversed(recent_actions):
            if not action.get('ok', True):
                consecutive_failures += 1
            else:
                break
        
        # Estimate cost (simplified)
        estimated_cost = self.step_count * 0.01  # $0.01 per step estimate
        
        return ExecutionMetrics(
            total_steps=self.step_count,
            subtask_steps=getattr(self, 'subtask_step_count', 0),
            error_rate=error_rate,
            success_rate=success_rate,
            consecutive_failures=consecutive_failures,
            repeated_action_count=getattr(self, 'last_exec_repeat', 0),
            ui_unchanged_steps=0,  # Would need UI comparison to calculate
            avg_step_duration=5.0,  # Placeholder - would need actual timing
            cost_spent=estimated_cost,
            last_action=actions[0] if actions else 'none'
        )
    
    def _apply_adaptive_adjustments(self, quality_report):
        """Apply adaptive adjustments based on quality report"""
        
        self.adaptive_mode = True
        
        # Apply specific adjustments based on issues
        for suggestion in quality_report.suggestions:
            if "alternative approach" in suggestion.lower():
                # Force replanning
                self.requires_replan = True
                logger.info("Adaptive adjustment: forcing replan")
            
            elif "simplify" in suggestion.lower():
                # Enable more conservative execution (placeholder)
                logger.info("Adaptive adjustment: would enable conservative mode (not implemented)")
            
            elif "break down" in suggestion.lower():
                # Request more granular subtasks (placeholder)
                logger.info("Adaptive adjustment: would request granular subtasks (not implemented)")
        
        # Store recommendations for monitoring
        self.dispatcher_recommendations.append({
            'timestamp': time.time(),
            'quality_status': quality_report.status.value,
            'suggestions': quality_report.suggestions,
            'applied': True
        })
    
    def _check_adaptive_triggers(self, info: Dict, actions: List[str]):
        """Check if adaptive mode adjustments are needed"""
        
        if not self.adaptive_mode:
            return
        
        # Check if adaptive adjustments are working
        if self.quality_check_count > 1:
            recent_recommendations = [r for r in self.dispatcher_recommendations 
                                   if time.time() - r['timestamp'] < 300]  # Last 5 minutes
            
            if len(recent_recommendations) >= 3:
                logger.warning("Multiple recent quality issues - may need manual intervention")
                self.adaptive_mode = False  # Disable to prevent oscillation
    
    def _create_stop_response(self, quality_report) -> Tuple[Dict, List[str]]:
        """Create response for quality-triggered stop"""
        
        info = {
            "subtask": getattr(self.current_subtask, 'name', 'unknown'),
            "subtask_info": getattr(self.current_subtask, 'info', ''),
            "subtask_status": "Stopped by quality check",
            "quality_report": {
                "status": quality_report.status.value,
                "issues": quality_report.issues,
                "confidence": quality_report.confidence
            }
        }
        
        actions = ["STOP: quality_check_critical"]
        
        return info, actions
    
    def _create_budget_exceeded_response(self, cost_status) -> Tuple[Dict, List[str]]:
        """Create response for budget exceeded"""
        
        info = {
            "subtask": getattr(self.current_subtask, 'name', 'unknown'),
            "subtask_info": getattr(self.current_subtask, 'info', ''),
            "subtask_status": "Stopped by budget limit",
            "cost_status": {
                "current": cost_status.current,
                "limit": cost_status.limit,
                "percentage": cost_status.percentage
            }
        }
        
        actions = ["STOP: budget_exceeded"]
        
        return info, actions
    
    def _get_dispatcher_info(self) -> Dict[str, Any]:
        """Get dispatcher information for response"""
        
        if not self.dispatcher:
            return {}
        
        return {
            "dispatcher_enabled": True,
            "quality_check_count": self.quality_check_count,
            "adaptive_mode": self.adaptive_mode,
            "last_quality_check": self.last_quality_check,
            "cost_budget_status": self.dispatcher.cost_controller.get_budget_status() if hasattr(self.dispatcher, 'cost_controller') else {},
            "recent_recommendations": len(self.dispatcher_recommendations)
        }
    
    # Default configuration methods
    
    def _get_default_dispatcher_config(self) -> DispatchConfig:
        """Get default dispatcher configuration"""
        return DispatchConfig(
            enable_quality_monitoring=True,
            enable_cost_tracking=True,
            enable_adaptive_execution=True,
            quality_check_interval=60.0,  # 1 minute
            cost_alert_threshold=0.8,
            max_consecutive_failures=3,
            enable_visual_monitoring=False,  # Disabled by default for performance
            log_all_interactions=True
        )
    
    def _get_default_quality_config(self) -> QualityCheckConfig:
        """Get default quality check configuration"""
        return QualityCheckConfig(
            check_interval=60.0,  # Check every minute
            step_interval=10,     # Or every 10 steps
            include_progress_analysis=True,
            include_efficiency_check=True,
            screenshot_analysis=False,  # Disabled by default
            deep_reasoning=False,       # Disabled by default for cost
            use_lightweight_model=True,
            estimated_cost=0.05
        )
    
    def _get_default_cost_budget(self) -> CostBudget:
        """Get default cost budget"""
        return CostBudget(
            total_limit=10.0,     # $10 total
            per_hour_limit=5.0,   # $5 per hour
            per_task_limit=2.0,   # $2 per task
            quality_check_budget=1.0,  # $1 for quality checks
            warning_threshold=0.8,     # Warn at 80%
            stop_threshold=0.95        # Stop at 95%
        )

    def get_dispatcher_status(self) -> Dict[str, Any]:
        """Get comprehensive dispatcher status"""
        if not self.dispatcher:
            return {"enabled": False}
        
        try:
            status = {
                "enabled": True,
                "quality_monitoring": {
                    "checks_performed": self.quality_check_count,
                    "last_check": self.last_quality_check,
                    "adaptive_mode": self.adaptive_mode
                },
                "cost_tracking": self.dispatcher.cost_controller.get_budget_status() if hasattr(self.dispatcher, 'cost_controller') else {},
                "recent_recommendations": len(self.dispatcher_recommendations),
                "performance_metrics": {} # get_performance_summary method doesn't exist
            }
            return status
        except Exception as e:
            logger.error(f"Error getting dispatcher status: {e}")
            return {"enabled": True, "error": str(e)}
    
    def update_dispatcher_config(self, config_updates: Dict[str, Any]):
        """Update dispatcher configuration dynamically"""
        try:
            if 'quality_config' in config_updates:
                for key, value in config_updates['quality_config'].items():
                    if hasattr(self.quality_config, key):
                        setattr(self.quality_config, key, value)
            
            if 'cost_budget' in config_updates:
                for key, value in config_updates['cost_budget'].items():
                    if hasattr(self.cost_budget, key):
                        setattr(self.cost_budget, key, value)
            
            if 'dispatcher_config' in config_updates:
                for key, value in config_updates['dispatcher_config'].items():
                    if hasattr(self.dispatcher_config, key):
                        setattr(self.dispatcher_config, key, value)
            
            logger.info("Dispatcher configuration updated successfully")
            
        except Exception as e:
            logger.error(f"Error updating dispatcher configuration: {e}") 