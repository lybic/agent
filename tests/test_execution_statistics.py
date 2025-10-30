#!/usr/bin/env python3
"""
Test script to verify execution statistics collection in gRPC service.
"""

import json
import tempfile
import os
from pathlib import Path
import importlib.util


def test_analyze_display_json():
    """
    Test that analyze_display_json correctly parses a display.json file
    and returns the expected statistics.
    """
    print("=" * 80)
    print("Testing analyze_display_json function")
    print("=" * 80)
    
    # Import directly from the module file to avoid dependency issues
    # Use relative path from test file location
    test_dir = Path(__file__).parent
    repo_root = test_dir.parent
    analyze_module_path = repo_root / 'gui_agents' / 'utils' / 'analyze_display.py'
    
    spec = importlib.util.spec_from_file_location(
        'analyze_display', 
        str(analyze_module_path)
    )
    analyze_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analyze_module)
    analyze_display_json = analyze_module.analyze_display_json
    
    # Create a temporary display.json file with test data
    test_data = {
        "operations": {
            "agent": [
                {
                    "operation": "fast_action_execution",
                    "tokens": [1000, 200, 1200],
                    "cost": "0.005￥"
                },
                {
                    "operation": "fast_action_execution",
                    "tokens": [500, 100, 600],
                    "cost": "0.003￥"
                }
            ],
            "other": [
                {
                    "operation": "total_execution_time_fast",
                    "duration": 45
                }
            ]
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_data, f)
        temp_file = f.name
    
    try:
        result = analyze_display_json(temp_file)
        
        print(f"Result: {json.dumps(result, indent=2)}")
        
        # Verify the results
        assert result["fast_action_count"] == 2, f"Expected 2 steps, got {result['fast_action_count']}"
        assert result["total_duration"] == 45, f"Expected 45 seconds, got {result['total_duration']}"
        assert result["total_input_tokens"] == 1500, f"Expected 1500 input tokens, got {result['total_input_tokens']}"
        assert result["total_output_tokens"] == 300, f"Expected 300 output tokens, got {result['total_output_tokens']}"
        assert result["total_tokens"] == 1800, f"Expected 1800 total tokens, got {result['total_tokens']}"
        assert abs(result["total_cost"] - 0.008) < 0.001, f"Expected ~0.008 cost, got {result['total_cost']}"
        
        print("✅ All assertions passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        os.unlink(temp_file)


def test_proto_message_creation():
    """
    Test that the ExecutionStatistics protobuf message can be created
    and populated with data.
    """
    print("\n" + "=" * 80)
    print("Testing ExecutionStatistics protobuf message")
    print("=" * 80)
    
    try:
        # Use relative path from test file location
        test_dir = Path(__file__).parent
        repo_root = test_dir.parent
        proto_pb_dir = repo_root / 'gui_agents' / 'proto' / 'pb'
        
        import sys
        sys.path.insert(0, str(proto_pb_dir))
        import agent_pb2
        
        # Create an ExecutionStatistics message
        stats = agent_pb2.ExecutionStatistics(
            steps=5,
            durationSeconds=120,
            inputTokens=2000,
            outputTokens=500,
            totalTokens=2500,
            cost=0.025,
            currencySymbol="￥"
        )
        
        print(f"Created ExecutionStatistics: {stats}")
        
        # Verify fields
        assert stats.steps == 5, f"Expected 5 steps, got {stats.steps}"
        assert stats.durationSeconds == 120, f"Expected 120 seconds, got {stats.durationSeconds}"
        assert stats.inputTokens == 2000, f"Expected 2000 input tokens, got {stats.inputTokens}"
        assert stats.outputTokens == 500, f"Expected 500 output tokens, got {stats.outputTokens}"
        assert stats.totalTokens == 2500, f"Expected 2500 total tokens, got {stats.totalTokens}"
        assert abs(stats.cost - 0.025) < 0.001, f"Expected 0.025 cost, got {stats.cost}"
        assert stats.currencySymbol == "￥", f"Expected ￥ symbol, got {stats.currencySymbol}"
        
        # Test QueryTaskStatusResponse with executionStatistics
        response = agent_pb2.QueryTaskStatusResponse(
            taskId="test-task-123",
            status=agent_pb2.TaskStatus.SUCCESS,
            message="Task completed",
            result=""
        )
        
        response.executionStatistics.CopyFrom(stats)
        
        assert response.HasField("executionStatistics"), "executionStatistics field not set"
        assert response.executionStatistics.steps == 5, "executionStatistics not copied correctly"
        
        print("✅ All protobuf tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = True
    
    success &= test_analyze_display_json()
    success &= test_proto_message_creation()
    
    print("\n" + "=" * 80)
    if success:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed")
    print("=" * 80)
    
    exit(0 if success else 1)
