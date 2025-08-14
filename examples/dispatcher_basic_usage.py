#!/usr/bin/env python3
"""
Basic usage example for AgentSDispatched with Central Dispatcher.

This example demonstrates how to use the enhanced GUI agent with 
dispatcher capabilities for quality monitoring and cost management.
"""

import os
import time
from typing import Dict

# Import the dispatched agent and configuration utilities
from gui_agents.agents import (
    AgentSDispatched, 
    DispatchConfig, 
    QualityCheckConfig, 
    CostBudget
)
from gui_agents.config import load_dispatcher_config, get_profile_config


def create_basic_agent() -> AgentSDispatched:
    """Create a basic dispatched agent with default settings."""
    
    # Create agent with dispatcher enabled
    agent = AgentSDispatched(
        platform="darwin",  # or "linux", "windows"
        screen_size=[1920, 1080],
        enable_dispatcher=True,
        # Use default configurations - they will be created automatically
    )
    
    print("✓ Created AgentSDispatched with default dispatcher settings")
    return agent


def create_configured_agent() -> AgentSDispatched:
    """Create a dispatched agent with custom configuration."""
    
    # Load configuration from files
    try:
        dispatcher_config_data = load_dispatcher_config()
        quality_profile = get_profile_config("balanced")
        
        print(f"✓ Loaded configuration files")
        print(f"  - Dispatcher config: {len(dispatcher_config_data)} sections")
        print(f"  - Quality profile: {quality_profile['name']}")
        
    except Exception as e:
        print(f"⚠ Could not load config files: {e}")
        print("  Using default configurations instead")
        dispatcher_config_data = None
        quality_profile = None
    
    # Create custom configurations
    dispatch_config = DispatchConfig(
        enable_quality_monitoring=True,
        enable_cost_tracking=True,
        enable_adaptive_execution=True,
        quality_check_interval=30.0,  # Check every 30 seconds
        cost_alert_threshold=0.8,
        max_consecutive_failures=3,
        enable_visual_monitoring=False,  # Disabled for performance
        log_all_interactions=True
    )
    
    quality_config = QualityCheckConfig(
        check_interval=30.0,
        step_interval=5,  # Check every 5 steps
        include_progress_analysis=True,
        include_efficiency_check=True,
        screenshot_analysis=False,  # Disabled for cost savings
        deep_reasoning=False,       # Disabled for cost savings
        use_lightweight_model=True,
        estimated_cost=0.02
    )
    
    cost_budget = CostBudget(
        total_limit=5.0,      # $5 total budget
        per_hour_limit=2.0,   # $2 per hour
        per_task_limit=1.0,   # $1 per task
        quality_check_budget=0.5,  # $0.50 for quality checks
        warning_threshold=0.7,     # Warn at 70%
        stop_threshold=0.9         # Stop at 90%
    )
    
    # Create agent with custom configuration
    agent = AgentSDispatched(
        platform="darwin",
        screen_size=[1920, 1080],
        enable_dispatcher=True,
        dispatcher_config=dispatch_config,
        quality_config=quality_config,
        cost_budget=cost_budget,
    )
    
    print("✓ Created AgentSDispatched with custom configuration")
    print(f"  - Quality checks every {quality_config.check_interval}s or {quality_config.step_interval} steps")
    print(f"  - Total budget: ${cost_budget.total_limit}")
    print(f"  - Quality budget: ${cost_budget.quality_check_budget}")
    
    return agent


def run_basic_task(agent: AgentSDispatched):
    """Run a basic task with the dispatched agent."""
    
    print("\n" + "="*50)
    print("RUNNING BASIC TASK")
    print("="*50)
    
    # Example task instruction
    instruction = "Open calculator app and calculate 123 + 456"
    
    # Mock observation (in real usage, this would come from screenshot)
    observation = {
        "screenshot": b"mock_screenshot_data",
        "screen_size": [1920, 1080],
        "timestamp": time.time()
    }
    
    print(f"Task: {instruction}")
    print("Starting execution with dispatcher monitoring...")
    
    try:
        # Reset agent state
        agent.reset()
        
        # Execute prediction
        info, actions = agent.predict(instruction, observation)
        
        print("\n✓ Execution completed successfully")
        print(f"  - Actions: {len(actions)}")
        print(f"  - Subtask: {info.get('subtask', 'Unknown')}")
        print(f"  - Status: {info.get('subtask_status', 'Unknown')}")
        
        # Show dispatcher information
        if 'dispatcher_enabled' in info and info['dispatcher_enabled']:
            print(f"  - Quality checks performed: {info.get('quality_check_count', 0)}")
            print(f"  - Adaptive mode: {info.get('adaptive_mode', False)}")
            
        # Get detailed dispatcher status
        dispatcher_status = agent.get_dispatcher_status()
        if dispatcher_status.get('enabled'):
            print("\nDispatcher Status:")
            quality_info = dispatcher_status.get('quality_monitoring', {})
            print(f"  - Quality checks: {quality_info.get('checks_performed', 0)}")
            print(f"  - Adaptive mode: {quality_info.get('adaptive_mode', False)}")
            
            cost_info = dispatcher_status.get('cost_tracking', {})
            if cost_info:
                print(f"  - Cost tracking: Active")
        
        return True
        
    except Exception as e:
        print(f"✗ Execution failed: {e}")
        return False


def demonstrate_quality_profiles():
    """Demonstrate different quality monitoring profiles."""
    
    print("\n" + "="*50)
    print("QUALITY PROFILES DEMONSTRATION")
    print("="*50)
    
    profiles = ["balanced", "performance", "conservative", "cost_conscious"]
    
    for profile_name in profiles:
        try:
            print(f"\n--- {profile_name.upper()} PROFILE ---")
            
            # Load profile configuration
            profile_config = get_profile_config(profile_name)
            print(f"Description: {profile_config['description']}")
            print(f"Check interval: {profile_config['check_interval']}s")
            print(f"Step interval: {profile_config['step_interval']} steps")
            print(f"Estimated cost: ${profile_config['estimated_cost']}")
            print(f"Screenshot analysis: {profile_config['screenshot_analysis']}")
            print(f"Deep reasoning: {profile_config['deep_reasoning']}")
            
        except Exception as e:
            print(f"Could not load profile '{profile_name}': {e}")


def demonstrate_cost_management(agent: AgentSDispatched):
    """Demonstrate cost management features."""
    
    print("\n" + "="*50)
    print("COST MANAGEMENT DEMONSTRATION")
    print("="*50)
    
    try:
        # Get initial cost status
        status = agent.get_dispatcher_status()
        cost_info = status.get('cost_tracking', {})
        
        if cost_info:
            print("Current cost status:")
            print(f"  - Current spend: ${cost_info.get('current', 0)}")
            print(f"  - Total limit: ${cost_info.get('limit', 0)}")
            print(f"  - Percentage used: {cost_info.get('percentage', 0):.1%}")
            print(f"  - Warning threshold: {cost_info.get('warning_threshold', 0):.1%}")
        
        # Demonstrate config updates
        print("\nUpdating cost budget configuration...")
        agent.update_dispatcher_config({
            'cost_budget': {
                'total_limit': 3.0,  # Reduce to $3
                'warning_threshold': 0.6  # Warn at 60%
            }
        })
        print("✓ Cost configuration updated")
        
    except Exception as e:
        print(f"✗ Cost management demonstration failed: {e}")


def main():
    """Main example function."""
    
    print("GUI Agent Central Dispatcher - Basic Usage Example")
    print("="*55)
    
    # Example 1: Basic agent with defaults
    print("\n1. Creating basic agent with default settings...")
    basic_agent = create_basic_agent()
    
    # Example 2: Agent with custom configuration  
    print("\n2. Creating agent with custom configuration...")
    configured_agent = create_configured_agent()
    
    # Example 3: Run a basic task
    success = run_basic_task(configured_agent)
    
    # Example 4: Demonstrate quality profiles
    demonstrate_quality_profiles()
    
    # Example 5: Demonstrate cost management
    if success:
        demonstrate_cost_management(configured_agent)
    
    print("\n" + "="*55)
    print("Example completed!")
    
    if success:
        print("✓ All demonstrations ran successfully")
        print("\nNext steps:")
        print("- Try different quality profiles")
        print("- Experiment with cost budgets")
        print("- Enable visual monitoring for advanced features")
        print("- Check the generated log files for detailed monitoring data")
    else:
        print("⚠ Some demonstrations encountered issues")
        print("- Check your environment setup")
        print("- Verify tool configurations in tools_config.json")
        print("- Review any error messages above")


if __name__ == "__main__":
    main() 