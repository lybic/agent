#!/usr/bin/env python3
"""
Advanced features example for AgentSDispatched with Central Dispatcher.

This example demonstrates advanced dispatcher capabilities including:
- Quality monitoring and adaptive execution
- Visual change detection  
- Cost optimization strategies
- Performance analytics
- Real-time configuration updates
"""

import os
import time
import json
from typing import Dict, List, Optional

from gui_agents.agents import (
    AgentSDispatched,
    DispatchConfig,
    QualityCheckConfig, 
    CostBudget,
    QualityStatus,
    RecommendationType
)
from gui_agents.config import get_profile_config


class AdvancedDispatcherDemo:
    """Advanced demonstration of dispatcher capabilities."""
    
    def __init__(self):
        self.agent: Optional[AgentSDispatched] = None
        self.execution_log: List[Dict] = []
        
    def setup_advanced_agent(self) -> AgentSDispatched:
        """Setup agent with advanced dispatcher features."""
        
        print("Setting up advanced dispatched agent...")
        
        # Advanced dispatcher configuration
        dispatch_config = DispatchConfig(
            enable_quality_monitoring=True,
            enable_cost_tracking=True,
            enable_adaptive_execution=True,
            quality_check_interval=20.0,  # More frequent checks
            cost_alert_threshold=0.7,
            max_consecutive_failures=2,   # Lower failure tolerance
            enable_visual_monitoring=True,  # Enable visual analysis
            log_all_interactions=True,
            debug_mode=True  # Enable detailed logging
        )
        
        # Advanced quality configuration with visual analysis
        quality_config = QualityCheckConfig(
            check_interval=20.0,
            step_interval=3,  # Very frequent step checks
            include_progress_analysis=True,
            include_efficiency_check=True,
            screenshot_analysis=True,    # Enable screenshot analysis
            deep_reasoning=True,         # Enable deep LLM analysis
            use_lightweight_model=False, # Use advanced models
            estimated_cost=0.15          # Higher cost for advanced features
        )
        
        # Flexible cost budget for advanced features
        cost_budget = CostBudget(
            total_limit=15.0,     # Higher budget for advanced features
            per_hour_limit=8.0,
            per_task_limit=3.0,
            quality_check_budget=2.0,  # Dedicated budget for quality
            warning_threshold=0.6,     # Early warning
            stop_threshold=0.85        # Conservative stop point
        )
        
        self.agent = AgentSDispatched(
            platform="darwin",
            screen_size=[1920, 1080],
            enable_dispatcher=True,
            dispatcher_config=dispatch_config,
            quality_config=quality_config,
            cost_budget=cost_budget,
        )
        
        print("✓ Advanced agent configured with:")
        print(f"  - Visual monitoring: {dispatch_config.enable_visual_monitoring}")
        print(f"  - Deep reasoning: {quality_config.deep_reasoning}")
        print(f"  - Screenshot analysis: {quality_config.screenshot_analysis}")
        print(f"  - Quality budget: ${cost_budget.quality_check_budget}")
        
        return self.agent
    
    def simulate_task_with_issues(self):
        """Simulate a task execution that encounters quality issues."""
        
        if not self.agent:
            print("Error: Agent not initialized. Call setup_advanced_agent() first.")
            return
            
        print("\n" + "="*60)
        print("SIMULATING TASK WITH QUALITY ISSUES")
        print("="*60)
        
        # Simulated complex task
        instruction = "Navigate to email application, compose message to team, attach quarterly report, and send"
        
        # Simulate multiple execution steps with varying quality
        scenarios = [
            {"step": 1, "status": "success", "screenshot_change": True, "issues": []},
            {"step": 2, "status": "success", "screenshot_change": True, "issues": []},
            {"step": 3, "status": "error", "screenshot_change": False, "issues": ["UI element not found"]},
            {"step": 4, "status": "error", "screenshot_change": False, "issues": ["Repeated action failure"]},
            {"step": 5, "status": "success", "screenshot_change": True, "issues": ["Slow response time"]},
            {"step": 6, "status": "success", "screenshot_change": True, "issues": []},
        ]
        
        print(f"Task: {instruction}")
        print(f"Simulating {len(scenarios)} execution steps...")
        
        for scenario in scenarios:
            print(f"\n--- Step {scenario['step']} ---")
            
            # Create mock observation
            observation = self._create_mock_observation(scenario)
            
            try:
                # Execute step
                if not self.agent:
                    raise RuntimeError("Agent not initialized")
                info, actions = self.agent.predict(instruction, observation)
                
                # Log execution
                self.execution_log.append({
                    "step": scenario['step'],
                    "timestamp": time.time(),
                    "status": scenario['status'],
                    "info": info,
                    "actions": len(actions),
                    "issues": scenario['issues']
                })
                
                # Report step result
                print(f"Status: {scenario['status']}")
                print(f"Actions generated: {len(actions)}")
                print(f"Issues: {scenario['issues'] or 'None'}")
                
                # Show dispatcher response
                if 'dispatcher_enabled' in info:
                    print(f"Quality checks: {info.get('quality_check_count', 0)}")
                    if info.get('adaptive_mode'):
                        print("⚡ Adaptive mode activated")
                
                # Simulate execution time
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Step failed: {e}")
                self.execution_log.append({
                    "step": scenario['step'],
                    "timestamp": time.time(),
                    "status": "failed",
                    "error": str(e)
                })
        
        print("\n✓ Task simulation completed")
        self._analyze_execution_log()
    
    def demonstrate_adaptive_execution(self):
        """Demonstrate adaptive execution based on quality feedback."""
        
        if not self.agent:
            print("Error: Agent not initialized. Call setup_advanced_agent() first.")
            return
        
        print("\n" + "="*60)
        print("ADAPTIVE EXECUTION DEMONSTRATION")  
        print("="*60)
        
        print("Testing adaptive responses to quality issues...")
        
        # Test different quality scenarios
        quality_scenarios = [
            {
                "name": "High Error Rate",
                "metrics": {"error_rate": 0.8, "consecutive_failures": 3},
                "expected_response": "Conservative mode activation"
            },
            {
                "name": "Repeated Actions",
                "metrics": {"repeated_action_count": 5, "ui_unchanged_steps": 4},
                "expected_response": "Alternative strategy selection"
            },
            {
                "name": "Cost Escalation",
                "metrics": {"cost_spent": 12.0, "efficiency_score": 0.3},
                "expected_response": "Cost optimization measures"
            },
            {
                "name": "Progress Stagnation", 
                "metrics": {"progress_score": -0.3, "step_count": 25},
                "expected_response": "Task re-planning"
            }
        ]
        
        for scenario in quality_scenarios:
            print(f"\n--- {scenario['name']} ---")
            print(f"Simulating: {scenario['metrics']}")
            
            # Simulate quality check that would trigger adaptation
            mock_observation = self._create_mock_observation({
                "status": "concerning",
                "screenshot_change": False,
                "issues": [scenario['name']]
            })
            
            try:
                # Update agent configuration dynamically based on scenario
                if "error_rate" in scenario['metrics']:
                    if not self.agent:
                        raise RuntimeError("Agent not initialized")
                    self.agent.update_dispatcher_config({
                        'quality_config': {
                            'check_interval': 10.0,  # More frequent checks
                            'deep_reasoning': True   # Enable deep analysis
                        }
                    })
                
                # Execute with quality monitoring
                if not self.agent:
                    raise RuntimeError("Agent not initialized")
                info, actions = self.agent.predict("Continue current task", mock_observation)
                
                print(f"Expected: {scenario['expected_response']}")
                print(f"Adaptive mode: {info.get('adaptive_mode', False)}")
                print(f"Quality status: {info.get('subtask_status', 'Unknown')}")
                
            except Exception as e:
                print(f"Scenario failed: {e}")
    
    def demonstrate_cost_optimization(self):
        """Demonstrate cost optimization strategies."""
        
        if not self.agent:
            print("Error: Agent not initialized. Call setup_advanced_agent() first.")
            return
        
        print("\n" + "="*60)
        print("COST OPTIMIZATION DEMONSTRATION")
        print("="*60)
        
        # Get current cost status
        if not self.agent:
            print("Agent not initialized")
            return
        status = self.agent.get_dispatcher_status()
        cost_info = status.get('cost_tracking', {})
        
        print("Current cost status:")
        if cost_info:
            print(f"  - Estimated spend: ${cost_info.get('current', 0):.2f}")
            print(f"  - Budget limit: ${cost_info.get('limit', 0):.2f}")
            print(f"  - Utilization: {cost_info.get('percentage', 0):.1%}")
        
        # Demonstrate cost-aware profile switching
        print("\nDemonstrating automatic profile switching based on budget:")
        
        budget_thresholds = [
            {"threshold": 0.5, "profile": "performance", "reason": "Budget sufficient"},
            {"threshold": 0.7, "profile": "balanced", "reason": "Moderate budget usage"},
            {"threshold": 0.9, "profile": "cost_conscious", "reason": "High budget usage"},
        ]
        
        for config in budget_thresholds:
            print(f"\n--- Budget at {config['threshold']:.0%} ---")
            print(f"Reason: {config['reason']}")
            print(f"Switching to: {config['profile']} profile")
            
            try:
                # Load profile configuration
                profile_config = get_profile_config(config['profile'])
                
                # Update agent configuration
                if not self.agent:
                    raise RuntimeError("Agent not initialized")
                self.agent.update_dispatcher_config({
                    'quality_config': {
                        'check_interval': profile_config['check_interval'],
                        'step_interval': profile_config['step_interval'],
                        'deep_reasoning': profile_config['deep_reasoning'],
                        'screenshot_analysis': profile_config['screenshot_analysis'],
                        'estimated_cost': profile_config['estimated_cost']
                    }
                })
                
                print(f"✓ Switched to {config['profile']} profile")
                print(f"  - Check interval: {profile_config['check_interval']}s")
                print(f"  - Cost per check: ${profile_config['estimated_cost']}")
                
            except Exception as e:
                print(f"Profile switch failed: {e}")
    
    def analyze_performance_metrics(self):
        """Analyze performance metrics and provide insights."""
        
        print("\n" + "="*60)
        print("PERFORMANCE METRICS ANALYSIS")
        print("="*60)
        
        if not self.execution_log:
            print("No execution data available for analysis")
            return
        
        # Calculate metrics from execution log
        total_steps = len(self.execution_log)
        successful_steps = len([step for step in self.execution_log if step.get('status') == 'success'])
        error_steps = len([step for step in self.execution_log if step.get('status') == 'error'])
        
        success_rate = successful_steps / total_steps if total_steps > 0 else 0
        error_rate = error_steps / total_steps if total_steps > 0 else 0
        
        print(f"Execution Summary:")
        print(f"  - Total steps: {total_steps}")
        print(f"  - Success rate: {success_rate:.1%}")
        print(f"  - Error rate: {error_rate:.1%}")
        
        # Quality insights
        quality_issues = []
        for step in self.execution_log:
            if step.get('issues'):
                quality_issues.extend(step['issues'])
        
        if quality_issues:
            print(f"\nQuality Issues Detected:")
            issue_counts = {}
            for issue in quality_issues:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
            
            for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"  - {issue}: {count} occurrences")
        
        # Get dispatcher performance data
        try:
            if not self.agent:
                print("Agent not initialized")
                return
            dispatcher_status = self.agent.get_dispatcher_status()
            performance_data = dispatcher_status.get('performance_metrics', {})
            
            if performance_data:
                print(f"\nDispatcher Performance:")
                print(f"  - Quality checks performed: {performance_data.get('quality_checks', 0)}")
                print(f"  - Adaptive interventions: {performance_data.get('adaptations', 0)}")
                print(f"  - Cost optimization events: {performance_data.get('cost_optimizations', 0)}")
        
        except Exception as e:
            print(f"Could not retrieve dispatcher performance data: {e}")
        
        # Recommendations
        print(f"\nRecommendations:")
        if error_rate > 0.3:
            print("  - Consider enabling more frequent quality checks")
            print("  - Review task complexity and break down into smaller steps")
        if success_rate > 0.8:
            print("  - Current configuration appears effective")
            print("  - Consider optimizing for cost if budget is a concern")
        
    def export_session_data(self, output_file: str = "dispatcher_session_data.json"):
        """Export session data for analysis."""
        
        if not self.agent:
            print("Error: Agent not initialized. Call setup_advanced_agent() first.")
            return
        
        print(f"\nExporting session data to {output_file}...")
        
        try:
            # Collect comprehensive session data
            session_data = {
                "timestamp": time.time(),
                "agent_config": {
                    "dispatcher_enabled": True,
                    "platform": self.agent.platform if self.agent else "unknown",
                    "screen_size": self.agent.screen_size if self.agent else [0, 0]
                },
                "execution_log": self.execution_log,
                "dispatcher_status": self.agent.get_dispatcher_status() if self.agent else {},
                "performance_summary": {
                    "total_steps": len(self.execution_log),
                    "success_rate": len([s for s in self.execution_log if s.get('status') == 'success']) / len(self.execution_log) if self.execution_log else 0
                }
            }
            
            # Export to file
            with open(output_file, 'w') as f:
                json.dump(session_data, f, indent=2, default=str)
            
            print(f"✓ Session data exported successfully")
            print(f"  - File: {output_file}")
            print(f"  - Size: {os.path.getsize(output_file)} bytes")
            
        except Exception as e:
            print(f"✗ Export failed: {e}")
    
    def _create_mock_observation(self, scenario: Dict) -> Dict:
        """Create mock observation for testing."""
        
        # Generate different screenshot data based on change status
        if scenario.get('screenshot_change', True):
            screenshot_data = f"mock_screenshot_{time.time()}_{scenario.get('step', 0)}".encode()
        else:
            screenshot_data = b"mock_screenshot_unchanged"
        
        return {
            "screenshot": screenshot_data,
            "screen_size": [1920, 1080],
            "timestamp": time.time(),
            "mock_scenario": scenario
        }
    
    def _analyze_execution_log(self):
        """Analyze execution log for patterns."""
        
        if not self.execution_log:
            return
        
        print(f"\nExecution Analysis:")
        print(f"  - Steps logged: {len(self.execution_log)}")
        
        # Find patterns
        error_steps = [step for step in self.execution_log if step.get('status') == 'error']
        if error_steps:
            print(f"  - Error steps: {len(error_steps)}")
            print(f"  - First error at step: {error_steps[0]['step']}")
        
        # Quality interventions
        quality_interventions = [step for step in self.execution_log if step.get('info', {}).get('adaptive_mode')]
        if quality_interventions:
            print(f"  - Quality interventions: {len(quality_interventions)}")


def main():
    """Main advanced example function."""
    
    print("GUI Agent Central Dispatcher - Advanced Features Demo")
    print("="*58)
    
    # Initialize demo
    demo = AdvancedDispatcherDemo()
    
    # Setup advanced agent
    agent = demo.setup_advanced_agent()
    
    # Run advanced demonstrations
    print("\n🚀 Starting advanced feature demonstrations...")
    
    # 1. Task with quality issues
    demo.simulate_task_with_issues()
    
    # 2. Adaptive execution
    demo.demonstrate_adaptive_execution()
    
    # 3. Cost optimization
    demo.demonstrate_cost_optimization()
    
    # 4. Performance analysis
    demo.analyze_performance_metrics()
    
    # 5. Export session data
    demo.export_session_data()
    
    print("\n" + "="*58)
    print("Advanced demo completed!")
    print("\n🎯 Key takeaways:")
    print("- Quality monitoring provides early issue detection")
    print("- Adaptive execution responds automatically to problems")
    print("- Cost optimization balances performance with budget")
    print("- Performance analytics enable continuous improvement")
    print("- Session data export supports detailed analysis")
    
    print("\n🔧 For production use:")
    print("- Configure quality profiles based on task criticality")
    print("- Set appropriate cost budgets and thresholds")
    print("- Enable visual monitoring for complex UI interactions")
    print("- Review and tune adaptive execution parameters")
    print("- Monitor exported session data for optimization opportunities")


if __name__ == "__main__":
    main() 