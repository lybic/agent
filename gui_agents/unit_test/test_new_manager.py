#!/usr/bin/env python3
"""
Test script for NewManager module
Tests all functionality step by step without traditional unit test framework
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from gui_agents.agents3.new_manager import NewManager, PlanningScenario, PlanningResult
from gui_agents.agents3.new_global_state import NewGlobalState
from gui_agents.agents3.enums import TaskStatus, SubtaskStatus, ManagerStatus

class MockTools:
    """Mock Tools class for testing"""
    def __init__(self):
        self.registered_tools = {}
    
    def register_tool(self, name, provider, model):
        self.registered_tools[name] = {"provider": provider, "model": model}
        print(f"  ✓ Registered tool: {name} ({provider}/{model})")
    
    def execute_tool(self, tool_name, params):
        """Mock tool execution with realistic responses"""
        if tool_name == "subtask_planner":
            # Return mock planning result
            mock_subtasks = [
                {
                    "title": "Open Application",
                    "description": "Launch the target application and wait for it to load completely",
                    "assignee_role": "operator"
                },
                {
                    "title": "Navigate to Settings",
                    "description": "Click on settings menu and navigate to the configuration page",
                    "assignee_role": "operator"
                },
                {
                    "title": "Analyze Current State",
                    "description": "Analyze the current screen state and identify next steps",
                    "assignee_role": "analyst"
                }
            ]
            return json.dumps(mock_subtasks), 150, "$0.002"
        
        elif tool_name == "websearch":
            query = params.get("query", "")
            return f"Mock web search results for: {query}. Found relevant information about the topic.", 50, "$0.001"
        
        elif tool_name in ["supplement_collector", "narrative_summarization", "context_fusion"]:
            mock_strategy = {
                "needed_info": "Additional context about the task requirements",
                "collection_strategy": {
                    "use_rag": True,
                    "rag_keywords": ["application", "settings", "configuration"],
                    "use_websearch": True,
                    "search_queries": ["how to configure application settings"],
                    "priority": "rag_first"
                },
                "collected_data": ""
            }
            return json.dumps(mock_strategy), 100, "$0.0015"
        
        elif tool_name == "embedding":
            return "mock_embedding_vector", 25, "$0.0001"
        
        return "mock_result", 10, "$0.0001"

class MockKnowledgeBase:
    """Mock KnowledgeBase for testing"""
    def __init__(self, embedding_engine, local_kb_path, platform, Tools_dict):
        self.embedding_engine = embedding_engine
        self.local_kb_path = local_kb_path
        self.platform = platform
        self.Tools_dict = Tools_dict
        print(f"  ✓ Mock KnowledgeBase initialized")
    
    def retrieve_narrative_experience(self, keyword):
        """Mock narrative experience retrieval"""
        mock_task = f"Similar task for keyword: {keyword}"
        mock_experience = f"Retrieved experience: Previous successful execution involving {keyword} showed that careful step-by-step approach works best."
        return mock_task, mock_experience, 75, "$0.001"

def create_test_environment():
    """Create temporary test environment"""
    print("🔧 Setting up test environment...")
    
    # Create temporary directories
    temp_dir = tempfile.mkdtemp(prefix="manager_test_")
    screenshot_dir = os.path.join(temp_dir, "screenshots")
    state_dir = os.path.join(temp_dir, "state")
    
    os.makedirs(screenshot_dir, exist_ok=True)
    os.makedirs(state_dir, exist_ok=True)
    
    print(f"  ✓ Created temp directory: {temp_dir}")
    print(f"  ✓ Screenshot dir: {screenshot_dir}")
    print(f"  ✓ State dir: {state_dir}")
    
    return temp_dir, screenshot_dir, state_dir

def create_mock_tools_dict():
    """Create mock tools dictionary"""
    print("🔧 Creating mock tools configuration...")
    
    tools_dict = {
        "subtask_planner": {
            "provider": "mock_provider",
            "model": "mock_planner_model"
        },
        "websearch": {
            "provider": "mock_provider", 
            "model": "mock_search_model"
        },
        "supplement_collector": {
            "provider": "mock_provider",
            "model": "mock_supplement_model"
        },
        "embedding": {
            "provider": "mock_provider",
            "model": "mock_embedding_model"
        },
        "query_formulator": {
            "provider": "mock_provider",
            "model": "mock_query_model"
        },
        "context_fusion": {
            "provider": "mock_provider",
            "model": "mock_fusion_model"
        }
    }
    
    print(f"  ✓ Created tools dict with {len(tools_dict)} tools")
    return tools_dict

def test_manager_initialization(tools_dict, global_state):
    """Test 1: Manager Initialization"""
    print("\n📋 Test 1: Manager Initialization")
    print("-" * 50)
    
    try:
        # Patch the Tools and KnowledgeBase classes
        import gui_agents.agents3.new_manager as manager_module
        original_tools = manager_module.Tools
        original_kb = manager_module.KnowledgeBase
        
        manager_module.Tools = MockTools
        manager_module.KnowledgeBase = MockKnowledgeBase
        
        # Initialize manager
        manager = NewManager(
            tools_dict=tools_dict,
            global_state=global_state,
            local_kb_path="/tmp/mock_kb",
            platform="linux",
            enable_search=True,
            max_replan_attempts=3,
            max_supplement_attempts=2
        )
        
        # Restore original classes
        manager_module.Tools = original_tools
        manager_module.KnowledgeBase = original_kb
        
        # Verify initialization
        assert manager.status == ManagerStatus.IDLE
        assert manager.replan_attempts == 0
        assert manager.supplement_attempts == 0
        assert len(manager.planning_history) == 0
        
        print("  ✅ Manager initialized successfully")
        print(f"  ✓ Status: {manager.status.value}")
        print(f"  ✓ Platform: {manager.platform}")
        print(f"  ✓ Search enabled: {manager.enable_search}")
        print(f"  ✓ Max replan attempts: {manager.max_replan_attempts}")
        print(f"  ✓ Max supplement attempts: {manager.max_supplement_attempts}")
        
        return manager
        
    except Exception as e:
        print(f"  ❌ Initialization failed: {e}")
        raise

def test_initial_planning(manager, global_state):
    """Test 2: Initial Planning"""
    print("\n📋 Test 2: Initial Planning")
    print("-" * 50)
    
    try:
        # Set task objective
        global_state.set_task_objective("Configure application settings and enable advanced features")
        
        # Execute initial planning
        result = manager.plan_task("initial_plan")
        
        # Verify planning result
        assert result.success == True
        assert result.scenario == "initial_plan"
        assert len(result.subtasks) > 0
        assert result.supplement == ""
        
        print("  ✅ Initial planning completed successfully")
        print(f"  ✓ Success: {result.success}")
        print(f"  ✓ Scenario: {result.scenario}")
        print(f"  ✓ Subtasks created: {len(result.subtasks)}")
        print(f"  ✓ Reason: {result.reason}")
        
        # Verify global state updates
        task = global_state.get_task()
        subtasks = global_state.get_subtasks()
        
        assert task.get("status") == TaskStatus.PENDING.value
        assert task.get("current_subtask_id") is not None
        assert len(subtasks) == len(result.subtasks)
        
        print("  ✓ Global state updated correctly")
        print(f"  ✓ Task status: {task.get('status')}")
        print(f"  ✓ Current subtask ID: {task.get('current_subtask_id')}")
        print(f"  ✓ Subtasks in state: {len(subtasks)}")
        
        # Print subtask details
        print("  📝 Created subtasks:")
        for i, subtask in enumerate(result.subtasks):
            print(f"    {i+1}. {subtask['title']} ({subtask['assignee_role']})")
            print(f"       {subtask['description'][:80]}...")
        
        return result
        
    except Exception as e:
        print(f"  ❌ Initial planning failed: {e}")
        raise

def test_replanning(manager, global_state):
    """Test 3: Replanning"""
    print("\n📋 Test 3: Replanning")
    print("-" * 50)
    
    try:
        # Simulate a failed subtask
        current_subtask_id = global_state.get_task().get("current_subtask_id")
        if current_subtask_id:
            global_state.update_subtask_status(
                current_subtask_id, 
                SubtaskStatus.REJECTED, 
                "Mock failure: Application did not respond as expected"
            )
            print(f"  ✓ Simulated failure for subtask: {current_subtask_id}")
        
        # Execute replanning
        result = manager.plan_task("replan")
        
        # Verify replanning result
        assert result.success == True
        assert result.scenario == "replan"
        assert len(result.subtasks) > 0
        
        print("  ✅ Replanning completed successfully")
        print(f"  ✓ Success: {result.success}")
        print(f"  ✓ Scenario: {result.scenario}")
        print(f"  ✓ New subtasks created: {len(result.subtasks)}")
        print(f"  ✓ Replan attempts: {manager.replan_attempts}")
        print(f"  ✓ Reason: {result.reason}")
        
        # Verify planning history
        assert len(manager.planning_history) >= 2
        print(f"  ✓ Planning history entries: {len(manager.planning_history)}")
        
        return result
        
    except Exception as e:
        print(f"  ❌ Replanning failed: {e}")
        raise

def test_supplement_collection(manager, global_state):
    """Test 4: Supplement Collection"""
    print("\n📋 Test 4: Supplement Collection")
    print("-" * 50)
    
    try:
        # Get initial supplement content
        initial_supplement = global_state.get_supplement()
        print(f"  ✓ Initial supplement length: {len(initial_supplement)} chars")
        
        # Execute supplement collection
        result = manager.plan_task("supplement")
        
        # Verify supplement result
        assert result.success == True
        assert result.scenario == "supplement"
        assert len(result.subtasks) == 0  # Supplement doesn't create subtasks
        assert result.supplement != ""
        
        print("  ✅ Supplement collection completed successfully")
        print(f"  ✓ Success: {result.success}")
        print(f"  ✓ Scenario: {result.scenario}")
        print(f"  ✓ Supplement attempts: {manager.supplement_attempts}")
        print(f"  ✓ Collected data length: {len(result.supplement)} chars")
        print(f"  ✓ Reason: {result.reason}")
        
        # Verify supplement content was updated
        updated_supplement = global_state.get_supplement()
        assert len(updated_supplement) > len(initial_supplement)
        
        print(f"  ✓ Supplement content updated: {len(updated_supplement)} chars")
        print("  📝 Supplement preview:")
        print(f"    {result.supplement[:200]}...")
        
        return result
        
    except Exception as e:
        print(f"  ❌ Supplement collection failed: {e}")
        raise

def test_scenario_normalization(manager):
    """Test 5: Scenario Normalization"""
    print("\n📋 Test 5: Scenario Normalization")
    print("-" * 50)
    
    try:
        # Test various string inputs
        test_cases = [
            ("initial_plan", PlanningScenario.INITIAL_PLAN),
            ("INITIAL_PLAN", PlanningScenario.INITIAL_PLAN),
            ("initial", PlanningScenario.INITIAL_PLAN),
            ("plan", PlanningScenario.INITIAL_PLAN),
            ("first_time", PlanningScenario.INITIAL_PLAN),
            ("replan", PlanningScenario.REPLAN),
            ("REPLAN", PlanningScenario.REPLAN),
            ("re-plan", PlanningScenario.REPLAN),
            ("supplement", PlanningScenario.SUPPLEMENT),
            ("SUPPLEMENT", PlanningScenario.SUPPLEMENT),
            ("supp", PlanningScenario.SUPPLEMENT),
            ("unknown", PlanningScenario.INITIAL_PLAN),  # Default fallback
        ]
        
        for input_str, expected in test_cases:
            result = manager._normalize_scenario(input_str)
            assert result == expected
            print(f"  ✓ '{input_str}' -> {result.value}")
        
        # Test enum input
        result = manager._normalize_scenario(PlanningScenario.REPLAN)
        assert result == PlanningScenario.REPLAN
        print(f"  ✓ Enum input preserved: {result.value}")
        
        print("  ✅ All scenario normalization tests passed")
        
    except Exception as e:
        print(f"  ❌ Scenario normalization failed: {e}")
        raise

def test_planning_status(manager):
    """Test 6: Planning Status"""
    print("\n📋 Test 6: Planning Status")
    print("-" * 50)
    
    try:
        # Get planning status
        status = manager.get_planning_status()
        
        # Verify status structure
        required_keys = [
            "status", "replan_attempts", "supplement_attempts",
            "planning_history_count", "max_replan_attempts", "max_supplement_attempts"
        ]
        
        for key in required_keys:
            assert key in status
            print(f"  ✓ {key}: {status[key]}")
        
        # Test capability checks
        can_replan = manager.can_replan()
        can_supplement = manager.can_supplement()
        
        print(f"  ✓ Can replan: {can_replan}")
        print(f"  ✓ Can supplement: {can_supplement}")
        
        print("  ✅ Planning status test passed")
        
    except Exception as e:
        print(f"  ❌ Planning status test failed: {e}")
        raise

def test_state_reset(manager, global_state):
    """Test 7: State Reset"""
    print("\n📋 Test 7: State Reset")
    print("-" * 50)
    
    try:
        # Record current state
        old_replan_attempts = manager.replan_attempts
        old_supplement_attempts = manager.supplement_attempts
        old_history_count = len(manager.planning_history)
        
        print(f"  📊 Before reset:")
        print(f"    Replan attempts: {old_replan_attempts}")
        print(f"    Supplement attempts: {old_supplement_attempts}")
        print(f"    Planning history: {old_history_count}")
        
        # Reset state
        manager.reset_planning_state()
        
        # Verify reset
        assert manager.replan_attempts == 0
        assert manager.supplement_attempts == 0
        assert len(manager.planning_history) == 0
        assert manager.status == ManagerStatus.IDLE
        
        print(f"  📊 After reset:")
        print(f"    Replan attempts: {manager.replan_attempts}")
        print(f"    Supplement attempts: {manager.supplement_attempts}")
        print(f"    Planning history: {len(manager.planning_history)}")
        print(f"    Status: {manager.status.value}")
        
        # Verify event was logged
        events = global_state.get_events()
        reset_events = [e for e in events if e.get("action") == "planning_reset"]
        assert len(reset_events) > 0
        
        print(f"  ✓ Reset event logged: {len(reset_events)} events")
        print("  ✅ State reset test passed")
        
    except Exception as e:
        print(f"  ❌ State reset test failed: {e}")
        raise

def test_file_persistence(global_state, state_dir):
    """Test 8: File Persistence"""
    print("\n📋 Test 8: File Persistence")
    print("-" * 50)
    
    try:
        # Check that files were created and contain data
        files_to_check = [
            ("task.json", "task information"),
            ("subtasks.json", "subtasks list"),
            ("supplement.md", "supplement content"),
            ("events.json", "events log")
        ]
        
        for filename, description in files_to_check:
            filepath = os.path.join(state_dir, filename)
            assert os.path.exists(filepath), f"File {filename} does not exist"
            
            file_size = os.path.getsize(filepath)
            print(f"  ✓ {filename}: {file_size} bytes ({description})")
            
            # Read and verify content
            if filename.endswith('.json'):
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        print(f"    Contains {len(data)} items")
                    elif isinstance(data, dict):
                        print(f"    Contains {len(data)} keys")
            elif filename.endswith('.md'):
                with open(filepath, 'r') as f:
                    content = f.read()
                    lines = content.count('\n')
                    print(f"    Contains {lines} lines")
        
        print("  ✅ File persistence test passed")
        
    except Exception as e:
        print(f"  ❌ File persistence test failed: {e}")
        raise

def cleanup_test_environment(temp_dir):
    """Clean up test environment"""
    print(f"\n🧹 Cleaning up test environment...")
    try:
        shutil.rmtree(temp_dir)
        print(f"  ✓ Removed temp directory: {temp_dir}")
    except Exception as e:
        print(f"  ⚠️  Failed to cleanup: {e}")

def main():
    """Main test execution"""
    print("🚀 Starting NewManager Module Tests")
    print("=" * 60)
    
    temp_dir = None
    try:
        # Setup test environment
        temp_dir, screenshot_dir, state_dir = create_test_environment()
        tools_dict = create_mock_tools_dict()
        
        # Initialize global state
        global_state = NewGlobalState(
            screenshot_dir=screenshot_dir,
            state_dir=state_dir,
            task_id="test-task-001"
        )
        
        print(f"  ✓ Global state initialized with task_id: {global_state.task_id}")
        
        # Run tests
        manager = test_manager_initialization(tools_dict, global_state)
        test_initial_planning(manager, global_state)
        test_replanning(manager, global_state)
        test_supplement_collection(manager, global_state)
        test_scenario_normalization(manager)
        test_planning_status(manager)
        test_state_reset(manager, global_state)
        test_file_persistence(global_state, state_dir)
        
        # Final summary
        print("\n🎉 All Tests Completed Successfully!")
        print("=" * 60)
        print("📊 Test Summary:")
        print(f"  ✅ Manager initialization: PASSED")
        print(f"  ✅ Initial planning: PASSED")
        print(f"  ✅ Replanning: PASSED")
        print(f"  ✅ Supplement collection: PASSED")
        print(f"  ✅ Scenario normalization: PASSED")
        print(f"  ✅ Planning status: PASSED")
        print(f"  ✅ State reset: PASSED")
        print(f"  ✅ File persistence: PASSED")
        
        print(f"\n📁 Test files created in: {state_dir}")
        print("   You can inspect the generated files to verify the results.")
        
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        if temp_dir:
            cleanup_test_environment(temp_dir)
    
    return 0

if __name__ == "__main__":
    exit(main()) 