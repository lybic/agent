"""
Enhanced Reflector - Advanced quality checking and reflection capabilities.

This module extends the existing Reflector with enhanced quality checking,
visual analysis, and progress monitoring capabilities for the central dispatcher system.
"""

import logging
import time
import hashlib
from typing import Dict, List, Optional, Any, Literal, Callable
from PIL import Image
import io

from gui_agents.agents.reflector import Reflector
from gui_agents.agents.dispatch_types import (
    QualityReport, QualityCheckContext, QualityCheckConfig, ProgressReport,
    VisualChangeReport, QualityStatus, RecommendationType
)
from gui_agents.tools.tools import Tools

logger = logging.getLogger("desktopenv.enhanced_reflector")


class EnhancedReflector(Reflector):
    """
    Enhanced version of Reflector with advanced quality checking capabilities.
    
    Provides:
    - Comprehensive quality checks with configurable depth
    - Lightweight progress monitoring
    - Visual change analysis
    - Cost-optimized reflection strategies
    """
    
    def __init__(
        self,
        tools_dict: dict,
        tool_name: str = "traj_reflector",
        logger_cb: Optional[Callable] = None,
    ):
        """Initialize enhanced reflector"""
        super().__init__(tools_dict, tool_name, logger_cb)
        
        # Additional tools for enhanced functionality
        self.lightweight_vision = None
        if "lightweight_vision" in tools_dict:
            self.lightweight_vision = Tools()
            self.lightweight_vision.register_tool(
                "lightweight_vision",
                tools_dict["lightweight_vision"]["provider"],
                tools_dict["lightweight_vision"]["model"]
            )
        
        # Screenshot comparison cache
        self.screenshot_cache: Dict[str, bytes] = {}
        self.max_cache_size = 10
        
    def comprehensive_check(
        self, 
        context: QualityCheckContext, 
        config: QualityCheckConfig
    ) -> QualityReport:
        """
        Perform comprehensive quality check based on configuration.
        
        Args:
            context: Current execution context
            config: Quality check configuration
            
        Returns:
            QualityReport with findings and recommendations
        """
        start_time = time.time()
        
        try:
            issues = []
            suggestions = []
            confidence = 1.0
            
            # Basic rule-based checks (always performed)
            rule_issues, rule_suggestions = self._perform_rule_based_checks(context)
            issues.extend(rule_issues)
            suggestions.extend(rule_suggestions)
            
            # Visual analysis if enabled
            if config.screenshot_analysis and context.current_screenshot:
                visual_issues, visual_suggestions = self._perform_visual_analysis(
                    context, config.use_lightweight_model
                )
                issues.extend(visual_issues)
                suggestions.extend(visual_suggestions)
            
            # Progress analysis if enabled
            if config.include_progress_analysis:
                progress_issues, progress_suggestions, progress_confidence = self._analyze_progress(context)
                issues.extend(progress_issues)
                suggestions.extend(progress_suggestions)
                confidence = min(confidence, progress_confidence)
            
            # Efficiency check if enabled
            if config.include_efficiency_check:
                efficiency_issues, efficiency_suggestions = self._check_efficiency(context)
                issues.extend(efficiency_issues)
                suggestions.extend(efficiency_suggestions)
            
            # Deep reasoning if enabled and we have the tools
            if config.deep_reasoning and self.is_available():
                deep_issues, deep_suggestions, deep_confidence = self._perform_deep_reasoning(
                    context, issues, suggestions
                )
                issues.extend(deep_issues)
                suggestions.extend(deep_suggestions)
                confidence = min(confidence, deep_confidence)
            
            # Determine overall status and recommendation
            status, recommendation = self._determine_status_and_recommendation(issues, context)
            
            # Calculate actual cost
            actual_cost = self._calculate_actual_cost(config, len(issues))
            
            report = QualityReport(
                status=status,
                recommendation=recommendation,
                confidence=confidence,
                issues=list(set(issues)),  # Remove duplicates
                suggestions=list(set(suggestions)),  # Remove duplicates
                cost_estimate=actual_cost,
                trigger_reason=getattr(context, 'trigger_reason', None),
                context_summary=context.to_dict()
            )
            
            execution_time = time.time() - start_time
            self._log("comprehensive_check", {
                "execution_time": execution_time,
                "issues_found": len(issues),
                "status": status.value,
                "cost": actual_cost
            })
            
            return report
            
        except Exception as e:
            logger.error(f"Error in comprehensive quality check: {e}")
            # Return safe fallback report
            return QualityReport(
                status=QualityStatus.CONCERNING,
                recommendation=RecommendationType.CONTINUE,
                confidence=0.1,
                issues=[f"Quality check failed: {str(e)}"],
                suggestions=["Retry quality check with different configuration"],
                cost_estimate=config.estimated_cost
            )
    
    def lightweight_progress_check(self, recent_actions: List[Dict]) -> ProgressReport:
        """
        Perform lightweight progress check based on recent actions.
        
        Args:
            recent_actions: List of recent action dictionaries
            
        Returns:
            ProgressReport with progress assessment
        """
        try:
            if not recent_actions:
                return ProgressReport(
                    progress_score=0.0,
                    direction="stagnant",
                    confidence=0.8,
                    evidence=["No recent actions to analyze"]
                )
            
            evidence = []
            progress_indicators = []
            
            # Analyze action patterns
            action_types = [action.get('type', 'unknown') for action in recent_actions]
            unique_actions = len(set(action_types))
            total_actions = len(action_types)
            
            # Check for progress indicators
            if 'Done' in action_types:
                progress_indicators.append(0.8)
                evidence.append("Task completion detected")
            elif 'Failed' in action_types:
                progress_indicators.append(-0.5)
                evidence.append("Failure detected")
            elif unique_actions == 1 and total_actions > 2:
                progress_indicators.append(-0.3)
                evidence.append("Repeated same action multiple times")
            elif unique_actions > total_actions * 0.7:
                progress_indicators.append(0.4)
                evidence.append("Diverse action types suggest exploration")
            
            # Check success/failure rates
            success_count = sum(1 for action in recent_actions if action.get('ok', True))
            if total_actions > 0:
                success_rate = success_count / total_actions
                if success_rate > 0.8:
                    progress_indicators.append(0.3)
                    evidence.append(f"High success rate: {success_rate:.1%}")
                elif success_rate < 0.3:
                    progress_indicators.append(-0.4)
                    evidence.append(f"Low success rate: {success_rate:.1%}")
            
            # Calculate overall progress score
            if progress_indicators:
                progress_score = max(-1.0, min(1.0, sum(progress_indicators) / len(progress_indicators)))
            else:
                progress_score = 0.0
                evidence.append("No clear progress indicators")
            
            # Determine direction
            if progress_score > 0.2:
                direction = "forward"
            elif progress_score < -0.2:
                direction = "backward"
            else:
                direction = "stagnant"
            
            # Calculate confidence based on evidence strength
            confidence = min(0.9, 0.3 + (len(evidence) * 0.15))
            
            return ProgressReport(
                progress_score=progress_score,
                direction=direction,
                confidence=confidence,
                evidence=evidence
            )
            
        except Exception as e:
            logger.error(f"Error in lightweight progress check: {e}")
            return ProgressReport(
                progress_score=0.0,
                direction="stagnant",
                confidence=0.1,
                evidence=[f"Error in analysis: {str(e)}"]
            )
    
    def visual_change_analysis(
        self, 
        current_screenshot: bytes, 
        previous_screenshot: Optional[bytes] = None
    ) -> VisualChangeReport:
        """
        Analyze visual changes between screenshots.
        
        Args:
            current_screenshot: Current screenshot as bytes
            previous_screenshot: Previous screenshot as bytes (optional)
            
        Returns:
            VisualChangeReport with change analysis
        """
        try:
            if not previous_screenshot:
                # Use cached screenshot if available
                previous_screenshot = self._get_cached_screenshot()
            
            if not previous_screenshot:
                # No comparison possible
                self._cache_screenshot(current_screenshot)
                return VisualChangeReport(
                    change_detected=False,
                    change_score=0.0,
                    change_areas=[],
                    similarity_score=1.0,
                    analysis_method="no_comparison_available"
                )
            
            # Calculate similarity using simple hash comparison
            current_hash = hashlib.md5(current_screenshot).hexdigest()
            previous_hash = hashlib.md5(previous_screenshot).hexdigest()
            
            change_detected = current_hash != previous_hash
            
            if change_detected:
                # For now, use a simple change score based on hash difference
                # In a full implementation, this would use image comparison
                change_score = 0.5  # Default moderate change
                similarity_score = 0.5
                change_areas = [{"area": "unknown", "confidence": 0.5}]
            else:
                change_score = 0.0
                similarity_score = 1.0
                change_areas = []
            
            # Cache current screenshot for future comparisons
            self._cache_screenshot(current_screenshot)
            
            return VisualChangeReport(
                change_detected=change_detected,
                change_score=change_score,
                change_areas=change_areas,
                similarity_score=similarity_score,
                analysis_method="hash_comparison"
            )
            
        except Exception as e:
            logger.error(f"Error in visual change analysis: {e}")
            return VisualChangeReport(
                change_detected=False,
                change_score=0.0,
                change_areas=[],
                similarity_score=0.0,
                analysis_method="error",
                timestamp=time.time()
            )
    
    # Private helper methods
    
    def _perform_rule_based_checks(self, context: QualityCheckContext) -> tuple[List[str], List[str]]:
        """Perform basic rule-based quality checks"""
        issues = []
        suggestions = []
        
        metrics = context.metrics
        
        # Check for repeated actions
        if metrics.repeated_action_count >= 3:
            issues.append(f"Action '{metrics.last_action}' repeated {metrics.repeated_action_count} times")
            suggestions.append("Try alternative approach or break down the current step")
        
        # Check for UI stagnation
        if metrics.ui_unchanged_steps >= 4:
            issues.append(f"UI unchanged for {metrics.ui_unchanged_steps} steps")
            suggestions.append("Verify actions are having intended effect on the interface")
        
        # Check error rate
        if metrics.error_rate > 0.6:
            issues.append(f"High error rate: {metrics.error_rate:.1%}")
            suggestions.append("Consider simplifying the current approach")
        
        # Check step efficiency
        if metrics.subtask_steps > 20:
            issues.append(f"Many steps ({metrics.subtask_steps}) for current subtask")
            suggestions.append("Consider breaking subtask into smaller parts")
        
        # Check consecutive failures
        if metrics.consecutive_failures >= 3:
            issues.append(f"{metrics.consecutive_failures} consecutive failures")
            suggestions.append("Reassess current strategy or request assistance")
        
        return issues, suggestions
    
    def _perform_visual_analysis(
        self, 
        context: QualityCheckContext, 
        use_lightweight: bool
    ) -> tuple[List[str], List[str]]:
        """Perform visual analysis of current state"""
        issues = []
        suggestions = []
        
        try:
            # Perform visual change analysis
            if context.current_screenshot is not None:
                visual_report = self.visual_change_analysis(context.current_screenshot)
                
                if not visual_report.change_detected and context.metrics.total_steps > 0:
                    issues.append("No visual changes detected despite actions")
                    suggestions.append("Verify actions are targeting correct UI elements")
                elif visual_report.change_score > 0.8:
                    # Significant changes detected
                    suggestions.append("Significant UI changes detected - verify intended progress")
            else:
                # No screenshot available
                issues.append("Visual analysis unavailable - no screenshot")
            
            # Additional visual checks would go here in full implementation
            # For example: error dialog detection, progress indicator analysis, etc.
            
        except Exception as e:
            logger.warning(f"Visual analysis failed: {e}")
            issues.append("Visual analysis unavailable")
        
        return issues, suggestions
    
    def _analyze_progress(self, context: QualityCheckContext) -> tuple[List[str], List[str], float]:
        """Analyze execution progress"""
        issues = []
        suggestions = []
        confidence = 0.8
        
        # Use lightweight progress check
        progress_report = self.lightweight_progress_check(context.recent_actions)
        
        if progress_report.direction == "backward":
            issues.append("Execution appears to be moving backward")
            suggestions.append("Review recent actions and consider alternative approach")
        elif progress_report.direction == "stagnant" and context.metrics.total_steps > 5:
            issues.append("No clear progress detected")
            suggestions.append("Reassess current strategy or try different actions")
        
        confidence = progress_report.confidence
        
        return issues, suggestions, confidence
    
    def _check_efficiency(self, context: QualityCheckContext) -> tuple[List[str], List[str]]:
        """Check execution efficiency"""
        issues = []
        suggestions = []
        
        metrics = context.metrics
        
        # Check time efficiency
        if metrics.avg_step_duration > 10.0:
            issues.append(f"Average step duration is high: {metrics.avg_step_duration:.1f}s")
            suggestions.append("Consider optimizing action planning or execution")
        
        # Check cost efficiency
        if metrics.cost_spent > 2.0 and metrics.total_steps < 20:
            issues.append("High cost relative to progress made")
            suggestions.append("Consider using more cost-effective approaches")
        
        return issues, suggestions
    
    def _perform_deep_reasoning(
        self, 
        context: QualityCheckContext, 
        existing_issues: List[str], 
        existing_suggestions: List[str]
    ) -> tuple[List[str], List[str], float]:
        """Perform deep reasoning analysis using LLM"""
        issues = []
        suggestions = []
        confidence = 0.7
        
        try:
            if not self.is_available():
                return issues, suggestions, confidence
            
            # Construct analysis prompt
            analysis_prompt = self._build_deep_analysis_prompt(
                context, existing_issues, existing_suggestions
            )
            
            # Call reflector for deep analysis
            analysis_result = self.reflect_agent_log(
                context.recent_actions, 
                "QUALITY_CHECK_DEEP_ANALYSIS"
            )
            
            # Parse analysis result (simplified implementation)
            if "concern" in analysis_result.lower() or "issue" in analysis_result.lower():
                issues.append("Deep analysis identified potential concerns")
                suggestions.append("Review detailed analysis output for specific recommendations")
            
            # In full implementation, this would parse structured output
            # and extract specific issues and suggestions
            
        except Exception as e:
            logger.warning(f"Deep reasoning analysis failed: {e}")
            confidence = 0.3
        
        return issues, suggestions, confidence
    
    def _determine_status_and_recommendation(
        self, 
        issues: List[str], 
        context: QualityCheckContext
    ) -> tuple[QualityStatus, RecommendationType]:
        """Determine overall status and recommendation"""
        
        critical_indicators = [
            context.metrics.consecutive_failures >= 3,
            context.metrics.error_rate > 0.8,
            "consecutive failures" in " ".join(issues).lower(),
            "high error rate" in " ".join(issues).lower()
        ]
        
        concerning_indicators = [
            len(issues) >= 3,
            context.metrics.error_rate > 0.5,
            context.metrics.repeated_action_count >= 3,
            "repeated" in " ".join(issues).lower(),
            "unchanged" in " ".join(issues).lower()
        ]
        
        if any(critical_indicators):
            status = QualityStatus.CRITICAL
            recommendation = RecommendationType.REPLAN
        elif any(concerning_indicators):
            status = QualityStatus.CONCERNING
            recommendation = RecommendationType.ADJUST
        else:
            status = QualityStatus.GOOD
            recommendation = RecommendationType.CONTINUE
        
        return status, recommendation
    
    def _calculate_actual_cost(self, config: QualityCheckConfig, issues_count: int) -> float:
        """Calculate actual cost based on configuration and analysis complexity"""
        base_cost = config.estimated_cost
        
        # Adjust cost based on actual work done
        if config.deep_reasoning and self.is_available():
            base_cost += 0.05  # Additional cost for LLM call
        
        if config.include_efficiency_check:
            base_cost += 0.01  # Small additional cost
        
        # Complexity adjustment based on issues found
        complexity_multiplier = 1.0 + (issues_count * 0.1)
        
        return min(base_cost * complexity_multiplier, base_cost * 2.0)  # Cap at 2x base cost
    
    def _build_deep_analysis_prompt(
        self, 
        context: QualityCheckContext, 
        existing_issues: List[str], 
        existing_suggestions: List[str]
    ) -> str:
        """Build prompt for deep analysis"""
        prompt = f"""
        Analyze the current execution context for quality issues:
        
        Current metrics:
        - Total steps: {context.metrics.total_steps}
        - Error rate: {context.metrics.error_rate:.1%}
        - Consecutive failures: {context.metrics.consecutive_failures}
        - Repeated actions: {context.metrics.repeated_action_count}
        
        Already identified issues: {existing_issues}
        Already suggested actions: {existing_suggestions}
        
        Recent actions: {context.recent_actions[-3:]}
        
        Provide additional insights on:
        1. Root causes of current issues
        2. Hidden patterns in execution
        3. Strategic recommendations for improvement
        """
        return prompt
    
    def _cache_screenshot(self, screenshot: bytes):
        """Cache screenshot for future comparison"""
        try:
            timestamp = str(int(time.time()))
            self.screenshot_cache[timestamp] = screenshot
            
            # Maintain cache size
            if len(self.screenshot_cache) > self.max_cache_size:
                oldest_key = min(self.screenshot_cache.keys())
                del self.screenshot_cache[oldest_key]
                
        except Exception as e:
            logger.warning(f"Failed to cache screenshot: {e}")
    
    def _get_cached_screenshot(self) -> Optional[bytes]:
        """Get most recent cached screenshot"""
        try:
            if not self.screenshot_cache:
                return None
            
            latest_key = max(self.screenshot_cache.keys())
            return self.screenshot_cache[latest_key]
            
        except Exception as e:
            logger.warning(f"Failed to get cached screenshot: {e}")
            return None 