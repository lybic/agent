#!/usr/bin/env python3
"""
Test script for Prometheus metrics integration.

This test verifies that the Prometheus metrics module works correctly with and without
prometheus_client installed.
"""

import sys
import os
from pathlib import Path

# Add the gui_agents/metrics directory directly to sys.path to avoid importing gui_agents.__init__
project_root = Path(__file__).parent.parent
metrics_path = project_root / "gui_agents" / "metrics"
sys.path.insert(0, str(metrics_path))


def test_metrics_without_prometheus():
    """Test that metrics work as no-ops when prometheus_client is not available."""
    print("=" * 80)
    print("Testing metrics without prometheus_client")
    print("=" * 80)
    
    # Force disable prometheus
    os.environ['ENABLE_PROMETHEUS'] = 'false'
    
    # Import directly from the module file
    import prometheus_metrics
    PrometheusMetrics = prometheus_metrics.PrometheusMetrics
    get_metrics_instance = prometheus_metrics.get_metrics_instance
    
    # Create metrics instance with prometheus disabled
    metrics = PrometheusMetrics(enabled=False)
    
    # Verify it's disabled
    assert not metrics.enabled, "Metrics should be disabled"
    
    # Test that all operations are no-ops (should not raise exceptions)
    try:
        metrics.record_task_created("pending")
        metrics.record_task_active(5)
        metrics.record_task_utilization(5, 10)
        metrics.record_task_execution_duration(120.5)
        metrics.record_task_queue_wait(5.2)
        
        metrics.record_grpc_request("RunAgentInstruction")
        metrics.record_grpc_error("RunAgentInstruction", "INTERNAL")
        metrics.record_grpc_stream_connection("GetAgentTaskStream", 1)
        metrics.record_grpc_stream_connection("GetAgentTaskStream", -1)
        
        metrics.record_tokens(1000, 200)
        metrics.record_cost(0.005, "USD")
        metrics.record_sandbox_created("Windows")
        metrics.record_task_steps(10)
        
        metrics.record_config_update("global")
        metrics.update_system_metrics(memory_bytes=1024*1024, temp_files=5, stream_tasks=3)
        metrics.update_success_rate(8, 10)
        metrics.update_uptime()
        
        # Test context manager
        with metrics.grpc_method_timer("TestMethod"):
            pass
        
        print("✅ All no-op operations completed without errors")
        return True
    except Exception as e:
        print(f"❌ No-op operations failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_metrics_with_prometheus():
    """Test that metrics work correctly when prometheus_client is available."""
    print("\n" + "=" * 80)
    print("Testing metrics with prometheus_client")
    print("=" * 80)
    
    try:
        import prometheus_client
        print(f"✓ prometheus_client is available (version: {prometheus_client.__version__})")
    except ImportError:
        print("⚠ prometheus_client not installed, skipping this test")
        print("  Install with: pip install prometheus-client")
        return True  # Not a failure, just skipped
    
    # Enable prometheus
    os.environ['ENABLE_PROMETHEUS'] = 'true'
    
    import prometheus_metrics
    PrometheusMetrics = prometheus_metrics.PrometheusMetrics
    
    # Create metrics instance with prometheus enabled
    metrics = PrometheusMetrics(enabled=True)
    
    # Verify it's enabled
    assert metrics.enabled, "Metrics should be enabled"
    
    try:
        # Test task metrics
        metrics.record_task_created("pending")
        metrics.record_task_created("running")
        metrics.record_task_active(2)
        metrics.record_task_utilization(2, 5)
        metrics.record_task_execution_duration(45.5)
        metrics.record_task_queue_wait(2.3)
        
        # Test gRPC metrics
        metrics.record_grpc_request("RunAgentInstruction")
        metrics.record_grpc_request("QueryTaskStatus")
        metrics.record_grpc_error("RunAgentInstruction", "INTERNAL")
        metrics.record_grpc_stream_connection("GetAgentTaskStream", 1)
        metrics.record_grpc_stream_connection("GetAgentTaskStream", -1)
        
        # Test business metrics
        metrics.record_tokens(1500, 300)
        metrics.record_cost(0.008, "￥")
        metrics.record_sandbox_created("Windows")
        metrics.record_sandbox_created("Linux")
        metrics.record_task_steps(15)
        
        # Test system metrics
        metrics.record_config_update("global")
        metrics.update_system_metrics(memory_bytes=2048*1024, temp_files=10, stream_tasks=5)
        metrics.update_success_rate(18, 20)
        metrics.update_uptime()
        metrics.update_service_info(
            version="0.5.0",
            max_concurrent_tasks=5,
            log_level="INFO",
            domain="test-host"
        )
        
        # Test context manager
        with metrics.grpc_method_timer("TestMethod"):
            import time
            time.sleep(0.01)
        
        print("✅ All prometheus operations completed successfully")
        
        # Try to generate metrics output (won't start HTTP server in test)
        from prometheus_client import generate_latest
        metrics_output = generate_latest()
        
        # Verify some metrics are present in the output
        output_str = metrics_output.decode('utf-8')
        assert 'agent_tasks_created_total' in output_str, "Task creation metrics not found"
        assert 'agent_grpc_requests_total' in output_str, "gRPC request metrics not found"
        assert 'agent_tokens_consumed_total' in output_str, "Token metrics not found"
        
        print(f"✅ Metrics output generated ({len(output_str)} bytes)")
        print(f"   Sample metrics found in output:")
        print(f"   - agent_tasks_created_total")
        print(f"   - agent_grpc_requests_total")
        print(f"   - agent_tokens_consumed_total")
        
        return True
        
    except Exception as e:
        print(f"❌ Prometheus operations failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_metrics_singleton():
    """Test that get_metrics_instance returns a singleton."""
    print("\n" + "=" * 80)
    print("Testing metrics singleton pattern")
    print("=" * 80)
    
    import prometheus_metrics
    get_metrics_instance = prometheus_metrics.get_metrics_instance
    
    # Reset environment
    os.environ['ENABLE_PROMETHEUS'] = 'false'
    
    # Get two instances
    metrics1 = get_metrics_instance()
    metrics2 = get_metrics_instance()
    
    # They should be the same object
    assert metrics1 is metrics2, "get_metrics_instance should return the same instance"
    
    print("✅ Singleton pattern verified")
    return True


def test_environment_variable_control():
    """Test that ENABLE_PROMETHEUS environment variable controls metrics."""
    print("\n" + "=" * 80)
    print("Testing environment variable control")
    print("=" * 80)
    
    import prometheus_metrics
    PrometheusMetrics = prometheus_metrics.PrometheusMetrics
    
    try:
        import prometheus_client
        prometheus_available = True
    except ImportError:
        prometheus_available = False
        print("⚠ prometheus_client not installed, testing with unavailable client")
    
    # Test with disabled
    os.environ['ENABLE_PROMETHEUS'] = 'false'
    metrics_disabled = PrometheusMetrics()
    assert not metrics_disabled.enabled, "Metrics should be disabled when ENABLE_PROMETHEUS=false"
    print("✅ ENABLE_PROMETHEUS=false correctly disables metrics")
    
    # Test with enabled (only works if prometheus_client is available)
    os.environ['ENABLE_PROMETHEUS'] = 'true'
    metrics_enabled = PrometheusMetrics()
    if prometheus_available:
        assert metrics_enabled.enabled, "Metrics should be enabled when ENABLE_PROMETHEUS=true and prometheus_client is available"
        print("✅ ENABLE_PROMETHEUS=true correctly enables metrics")
    else:
        assert not metrics_enabled.enabled, "Metrics should be disabled when prometheus_client is not available"
        print("✅ Metrics correctly disabled when prometheus_client not available")
    
    # Test with other truthy values
    for value in ['1', 'yes', 'True', 'TRUE']:
        os.environ['ENABLE_PROMETHEUS'] = value
        metrics_test = PrometheusMetrics()
        if prometheus_available:
            assert metrics_test.enabled, f"Metrics should be enabled with ENABLE_PROMETHEUS={value}"
    
    print("✅ All environment variable tests passed")
    return True


if __name__ == "__main__":
    success = True
    
    # Run all tests
    success &= test_metrics_without_prometheus()
    success &= test_metrics_with_prometheus()
    success &= test_metrics_singleton()
    success &= test_environment_variable_control()
    
    print("\n" + "=" * 80)
    if success:
        print("✅ All Prometheus metrics tests passed!")
        print("\nTo enable Prometheus monitoring in production:")
        print("  1. Install prometheus-client: pip install prometheus-client psutil")
        print("  2. Set environment variable: ENABLE_PROMETHEUS=true")
        print("  3. Optionally set PROMETHEUS_PORT=8000 (default)")
        print("  4. Configure Prometheus to scrape http://your-server:8000/metrics")
    else:
        print("❌ Some Prometheus metrics tests failed")
    print("=" * 80)
    
    sys.exit(0 if success else 1)
