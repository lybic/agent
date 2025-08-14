"""
Enhanced Global State - Extended state management for Central Dispatcher.

This module extends the existing GlobalState with additional functionality
required by the central dispatcher system, including quality reports,
execution metrics, and module interaction logging.
"""

import json
import os
import time
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import asdict

from gui_agents.agents.global_state import GlobalState, safe_json_dump, safe_json_load, locked
from gui_agents.agents.dispatch_types import (
    QualityReport, ExecutionMetrics, ModuleMessage, ExecutionContext
)
from gui_agents.utils.common_utils import Node

logger = logging.getLogger("desktopenv.enhanced_global_state")


class EnhancedGlobalState(GlobalState):
    """
    Enhanced version of GlobalState with additional functionality for dispatcher system.
    
    Adds support for:
    - Quality reports storage and retrieval
    - Execution metrics tracking
    - Module interaction logging
    - Enhanced execution history
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize enhanced global state with additional file paths"""
        super().__init__(*args, **kwargs)
        
        # Additional file paths for dispatcher functionality
        self.quality_reports_path = Path(os.path.join(self.running_state_path.parent, "quality_reports.json"))
        self.execution_metrics_path = Path(os.path.join(self.running_state_path.parent, "execution_metrics.json"))
        self.module_interactions_path = Path(os.path.join(self.running_state_path.parent, "module_interactions.json"))
        self.execution_context_path = Path(os.path.join(self.running_state_path.parent, "execution_context.json"))
        
        # Initialize additional files
        self._initialize_enhanced_files()
        
    def _initialize_enhanced_files(self):
        """Initialize additional files required by enhanced state"""
        file_paths = [
            self.quality_reports_path,
            self.execution_metrics_path, 
            self.module_interactions_path,
            self.execution_context_path
        ]
        
        for path in file_paths:
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                if path == self.execution_metrics_path or path == self.execution_context_path:
                    # These store single objects, not arrays
                    with open(path, 'w', encoding='utf-8') as f:
                        json.dump({}, f)
                else:
                    # These store arrays
                    with open(path, 'w', encoding='utf-8') as f:
                        json.dump([], f)
                        
    # ====== Quality Reports Management ======
    
    def add_quality_report(self, report: QualityReport) -> None:
        """Add a quality report to storage"""
        try:
            reports = self.get_quality_reports()
            report_dict = report.to_dict() if hasattr(report, 'to_dict') else asdict(report)
            reports.append(report_dict)
            
            # Keep only last 50 reports to prevent unbounded growth
            if len(reports) > 50:
                reports = reports[-50:]
            
            tmp = self.quality_reports_path.with_suffix(".tmp")
            try:
                with locked(tmp, "w") as f:
                    safe_json_dump(reports, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                tmp.replace(self.quality_reports_path)
                
                logger.debug(f"Added quality report with status: {report.status}")
                
            except Exception as e:
                logger.error(f"Failed to save quality report: {e}")
                if tmp.exists():
                    tmp.unlink()
                raise
                
        except Exception as e:
            logger.error(f"Failed to add quality report: {e}")
            
    def get_quality_reports(self, limit: int = 10) -> List[Dict]:
        """Get recent quality reports"""
        try:
            with locked(self.quality_reports_path, "r") as f:
                data = safe_json_load(f)
            
            if isinstance(data, list):
                return data[-limit:] if limit > 0 else data
            else:
                logger.warning("Quality reports file contains invalid data format")
                return []
                
        except Exception as e:
            logger.warning(f"Failed to get quality reports: {e}")
            return []
            
    def get_latest_quality_report(self) -> Optional[Dict]:
        """Get the most recent quality report"""
        reports = self.get_quality_reports(1)
        return reports[0] if reports else None
        
    # ====== Execution Metrics Management ======
    
    def record_execution_metrics(self, metrics: ExecutionMetrics) -> None:
        """Record current execution metrics"""
        try:
            metrics_dict = asdict(metrics)
            metrics_dict['timestamp'] = time.time()
            
            tmp = self.execution_metrics_path.with_suffix(".tmp")
            try:
                with locked(tmp, "w") as f:
                    safe_json_dump(metrics_dict, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                tmp.replace(self.execution_metrics_path)
                
                logger.debug(f"Recorded execution metrics: {metrics.total_steps} steps, {metrics.error_rate:.2f} error rate")
                
            except Exception as e:
                logger.error(f"Failed to save execution metrics: {e}")
                if tmp.exists():
                    tmp.unlink()
                raise
                
        except Exception as e:
            logger.error(f"Failed to record execution metrics: {e}")
            
    def get_execution_metrics(self) -> Optional[ExecutionMetrics]:
        """Get current execution metrics"""
        try:
            with locked(self.execution_metrics_path, "r") as f:
                data = safe_json_load(f)
            
            if isinstance(data, dict) and data:
                # Remove timestamp before creating ExecutionMetrics object
                data.pop('timestamp', None)
                return ExecutionMetrics(**data)
            else:
                return None
                
        except Exception as e:
            logger.warning(f"Failed to get execution metrics: {e}")
            return None
            
    # ====== Module Interaction Logging ======
    
    def log_module_interaction(self, message: ModuleMessage) -> None:
        """Log interaction between modules"""
        try:
            interactions = self.get_module_interactions(100)  # Keep last 100 interactions
            
            interaction_dict = asdict(message) if hasattr(message, '__dict__') else {
                'source': getattr(message, 'source', 'unknown'),
                'target': getattr(message, 'target', 'unknown'), 
                'data': getattr(message, 'data', {}),
                'timestamp': getattr(message, 'timestamp', time.time()),
                'message_id': getattr(message, 'message_id', None)
            }
            
            interactions.append(interaction_dict)
            
            # Keep only last 100 interactions
            if len(interactions) > 100:
                interactions = interactions[-100:]
            
            tmp = self.module_interactions_path.with_suffix(".tmp")
            try:
                with locked(tmp, "w") as f:
                    safe_json_dump(interactions, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                tmp.replace(self.module_interactions_path)
                
            except Exception as e:
                logger.error(f"Failed to save module interaction: {e}")
                if tmp.exists():
                    tmp.unlink()
                raise
                
        except Exception as e:
            logger.error(f"Failed to log module interaction: {e}")
            
    def get_module_interactions(self, limit: int = 50) -> List[Dict]:
        """Get recent module interactions"""
        try:
            with locked(self.module_interactions_path, "r") as f:
                data = safe_json_load(f)
                
            if isinstance(data, list):
                return data[-limit:] if limit > 0 else data
            else:
                return []
                
        except Exception as e:
            logger.warning(f"Failed to get module interactions: {e}")
            return []
            
    # ====== Enhanced Execution History ======
    
    def get_execution_history(self, limit: int = 20) -> List[Dict]:
        """Get execution history combining agent logs and actions"""
        try:
            # Combine agent logs and actions for comprehensive history
            agent_log = self.get_agent_log()
            actions = self.get_actions()
            
            # Merge and sort by timestamp if available
            combined_history = []
            
            # Add agent logs
            for entry in agent_log:
                combined_history.append({
                    'type': 'agent_log',
                    'content': entry.get('content', ''),
                    'log_type': entry.get('type', 'unknown'),
                    'timestamp': entry.get('timestamp', time.time()),
                    'id': entry.get('id')
                })
            
            # Add actions
            for entry in actions:
                combined_history.append({
                    'type': 'action',
                    'content': entry.get('action', ''),
                    'step_id': entry.get('step_id', ''),
                    'ok': entry.get('ok', True),
                    'error': entry.get('error'),
                    'timestamp': entry.get('timestamp', time.time()),
                    'id': entry.get('id')
                })
            
            # Sort by timestamp (most recent last)
            combined_history.sort(key=lambda x: x.get('timestamp', 0))
            
            return combined_history[-limit:] if limit > 0 else combined_history
            
        except Exception as e:
            logger.warning(f"Failed to get execution history: {e}")
            return []
            
    def get_recent_actions(self, limit: int = 5) -> List[Dict]:
        """Get recent actions with enhanced information"""
        try:
            actions = self.get_actions()
            recent_actions = actions[-limit:] if actions else []
            
            # Enhance with additional context
            enhanced_actions = []
            for action in recent_actions:
                enhanced_action = action.copy()
                enhanced_action['retrieved_at'] = time.time()
                enhanced_actions.append(enhanced_action)
                
            return enhanced_actions
            
        except Exception as e:
            logger.warning(f"Failed to get recent actions: {e}")
            return []
            
    # ====== Execution Context Management ======
    
    def save_execution_context(self, context: ExecutionContext) -> None:
        """Save current execution context"""
        try:
            context_dict = {
                'metrics': asdict(context.metrics),
                'current_subtask': context.current_subtask.name if context.current_subtask else None,
                'recent_actions_count': len(context.recent_actions),
                'quality_reports_count': len(context.quality_reports),
                'failed_subtasks_count': len(context.failed_subtasks),
                'cost_budget': asdict(context.cost_budget),
                'timestamp': context.timestamp,
                'is_critical': context.is_critical_situation,
                'needs_attention': context.needs_attention
            }
            
            tmp = self.execution_context_path.with_suffix(".tmp")
            try:
                with locked(tmp, "w") as f:
                    safe_json_dump(context_dict, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                tmp.replace(self.execution_context_path)
                
            except Exception as e:
                logger.error(f"Failed to save execution context: {e}")
                if tmp.exists():
                    tmp.unlink()
                raise
                
        except Exception as e:
            logger.error(f"Failed to save execution context: {e}")
            
    def get_execution_context_summary(self) -> Optional[Dict]:
        """Get summary of current execution context"""
        try:
            with locked(self.execution_context_path, "r") as f:
                data = safe_json_load(f)
                
            return data if isinstance(data, dict) and data else None
            
        except Exception as e:
            logger.warning(f"Failed to get execution context: {e}")
            return None
            
    # ====== Enhanced Failure Tracking ======
    
    def get_failure_patterns(self) -> Dict[str, Any]:
        """Analyze failure patterns from failed subtasks"""
        try:
            failed_subtasks = self.get_failed_subtasks()
            
            if not failed_subtasks:
                return {'total_failures': 0, 'patterns': {}}
            
            patterns = {
                'total_failures': len(failed_subtasks),
                'failure_types': {},
                'most_failed_subtask': None,
                'recent_failures': []
            }
            
            # Count failure types
            for subtask in failed_subtasks:
                error_type = getattr(subtask, 'error_type', 'UNKNOWN')
                patterns['failure_types'][error_type] = patterns['failure_types'].get(error_type, 0) + 1
            
            # Find most failed subtask type
            subtask_failures = {}
            for subtask in failed_subtasks:
                name = subtask.name
                subtask_failures[name] = subtask_failures.get(name, 0) + 1
            
            if subtask_failures:
                patterns['most_failed_subtask'] = max(subtask_failures.items(), key=lambda x: x[1])
            
            # Get recent failures (last 5)
            recent_failed = failed_subtasks[-5:] if len(failed_subtasks) > 5 else failed_subtasks
            patterns['recent_failures'] = [
                {
                    'name': subtask.name,
                    'error_type': getattr(subtask, 'error_type', 'UNKNOWN'),
                    'failure_count': getattr(subtask, 'failure_count', 1)
                }
                for subtask in recent_failed
            ]
            
            return patterns
            
        except Exception as e:
            logger.error(f"Failed to analyze failure patterns: {e}")
            return {'total_failures': 0, 'patterns': {}}
            
    # ====== Performance Analytics ======
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary across all tracked metrics"""
        try:
            metrics = self.get_execution_metrics()
            quality_reports = self.get_quality_reports()
            failure_patterns = self.get_failure_patterns()
            
            summary = {
                'timestamp': time.time(),
                'execution_metrics': {
                    'total_steps': metrics.total_steps if metrics else 0,
                    'error_rate': metrics.error_rate if metrics else 0.0,
                    'success_rate': metrics.success_rate if metrics else 0.0,
                    'avg_step_duration': metrics.avg_step_duration if metrics else 0.0,
                    'cost_spent': metrics.cost_spent if metrics else 0.0
                },
                'quality_summary': {
                    'total_reports': len(quality_reports),
                    'recent_status': quality_reports[-1].get('status', 'UNKNOWN') if quality_reports else 'NONE',
                    'avg_confidence': sum(r.get('confidence', 0) for r in quality_reports) / len(quality_reports) if quality_reports else 0.0
                },
                'failure_summary': failure_patterns,
                'health_indicators': {
                    'is_healthy': (metrics.error_rate < 0.3 if metrics else True) and failure_patterns['total_failures'] < 5,
                    'needs_attention': (metrics.error_rate > 0.5 if metrics else False) or failure_patterns['total_failures'] > 3,
                    'critical_state': (metrics.error_rate > 0.8 if metrics else False) or failure_patterns['total_failures'] > 10
                }
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate performance summary: {e}")
            return {'timestamp': time.time(), 'error': str(e)}
            
    # ====== Cleanup and Maintenance ======
    
    def cleanup_old_data(self, days_to_keep: int = 7):
        """Clean up old data to prevent storage bloat"""
        try:
            cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
            
            # Clean quality reports
            reports = self.get_quality_reports(0)  # Get all
            recent_reports = [r for r in reports if r.get('timestamp', 0) > cutoff_time]
            
            if len(recent_reports) != len(reports):
                tmp = self.quality_reports_path.with_suffix(".tmp")
                with locked(tmp, "w") as f:
                    safe_json_dump(recent_reports, f)
                tmp.replace(self.quality_reports_path)
                logger.info(f"Cleaned {len(reports) - len(recent_reports)} old quality reports")
            
            # Clean module interactions
            interactions = self.get_module_interactions(0)  # Get all
            recent_interactions = [i for i in interactions if i.get('timestamp', 0) > cutoff_time]
            
            if len(recent_interactions) != len(interactions):
                tmp = self.module_interactions_path.with_suffix(".tmp")
                with locked(tmp, "w") as f:
                    safe_json_dump(recent_interactions, f)
                tmp.replace(self.module_interactions_path)
                logger.info(f"Cleaned {len(interactions) - len(recent_interactions)} old module interactions")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            
    def export_session_data(self, output_path: str) -> bool:
        """Export all session data for analysis"""
        try:
            export_data = {
                'export_timestamp': time.time(),
                'execution_metrics': asdict(self.get_execution_metrics()) if self.get_execution_metrics() else {}, # type: ignore
                'quality_reports': self.get_quality_reports(0),
                'module_interactions': self.get_module_interactions(0),
                'execution_history': self.get_execution_history(0),
                'performance_summary': self.get_performance_summary(),
                'failure_patterns': self.get_failure_patterns(),
                'completed_subtasks': [asdict(node) if hasattr(node, '__dict__') else str(node) for node in self.get_completed_subtasks()],
                'failed_subtasks': [asdict(node) if hasattr(node, '__dict__') else str(node) for node in self.get_failed_subtasks()],
                'agent_log': self.get_agent_log()
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Session data exported to: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export session data: {e}")
            return False
    
    # ====== Additional Methods for Central Dispatcher Compatibility ======
    
    def get_screenshot(self) -> Optional[bytes]:
        """Get current screenshot (delegate to parent)"""
        return super().get_screenshot()
    
    def get_latest_failed_subtask(self) -> Optional[Node]:
        """Get the most recent failed subtask"""
        failed = self.get_failed_subtasks()
        return failed[-1] if failed else None
    
    def add_failed_subtask_with_info(self, name: str, info: str, error_type: str, error_message: str) -> None:
        """Add a failed subtask with detailed error information"""
        # Create a subtask node with error details
        from gui_agents.utils.common_utils import Node
        
        failed_subtask = Node(
            name=name,
            info=info,
            error_type=error_type,
            error_message=error_message,
            failure_count=1,
            last_failure_time=str(time.time())
        )
        
        # Add to failed subtasks
        current_failed = self.get_failed_subtasks()
        current_failed.append(failed_subtask)
        self.set_failed_subtasks(current_failed)
        
    def add_completed_subtask(self, subtask: Node) -> None:
        """Add a completed subtask"""
        current_completed = self.get_completed_subtasks()
        current_completed.append(subtask)
        self.set_completed_subtasks(current_completed) 