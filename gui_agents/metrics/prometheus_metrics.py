"""
Prometheus metrics collection for GUI Agent service.

This module provides optional Prometheus monitoring for various aspects of the agent service.
Prometheus support is optional and can be enabled via the ENABLE_PROMETHEUS environment variable.
"""

import os
import logging
import time
from typing import Optional, Callable
from functools import wraps

logger = logging.getLogger(__name__)

# Check if prometheus_client is available
try:
    from prometheus_client import (
        Counter, Gauge, Histogram, Summary, Info,
        start_http_server
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.debug("prometheus_client not available. Metrics collection disabled.")


class NoOpMetric:
    """No-op metric class when Prometheus is not available."""
    
    def inc(self, *args, **kwargs):
        pass
    
    def dec(self, *args, **kwargs):
        pass
    
    def set(self, *args, **kwargs):
        pass
    
    def observe(self, *args, **kwargs):
        pass
    
    def labels(self, *args, **kwargs):
        return self
    
    def time(self):
        """Return a context manager that does nothing."""
        return _NoOpContextManager()


class _NoOpContextManager:
    """No-op context manager for timing."""
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass


class PrometheusMetrics:
    """
    Prometheus metrics collector for GUI Agent service.
    
    This class defines and manages all Prometheus metrics for monitoring the agent service.
    If prometheus_client is not installed or Prometheus is disabled, all operations become no-ops.
    """
    
    def __init__(self, enabled: bool = None):
        """
        Initialize Prometheus metrics.
        
        Args:
            enabled: If True, enable metrics collection. If None, check ENABLE_PROMETHEUS env var.
        """
        if enabled is None:
            enabled = os.environ.get("ENABLE_PROMETHEUS", "false").lower() in ("true", "1", "yes")
        
        self.enabled = enabled and PROMETHEUS_AVAILABLE
        
        if not PROMETHEUS_AVAILABLE and enabled:
            logger.warning(
                "Prometheus metrics requested but prometheus_client is not installed. "
                "Install with: pip install prometheus-client"
            )
        
        if self.enabled:
            logger.info("Prometheus metrics collection enabled")
            self._init_metrics()
        else:
            logger.debug("Prometheus metrics collection disabled")
            self._init_noop_metrics()
    
    def _init_metrics(self):
        """Initialize all Prometheus metrics."""
        
        # ====================
        # Task Lifecycle Metrics
        # ====================
        
        self.tasks_created_total = Counter(
            'agent_tasks_created_total',
            'Total number of tasks created',
            ['status']  # pending, running, completed, failed, cancelled
        )
        
        self.tasks_active = Gauge(
            'agent_tasks_active',
            'Number of currently active tasks'
        )
        
        self.task_execution_duration_seconds = Histogram(
            'agent_task_execution_duration_seconds',
            'Task execution duration in seconds',
            buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600)  # 1s to 1h
        )
        
        self.task_queue_wait_duration_seconds = Histogram(
            'agent_task_queue_wait_duration_seconds',
            'Task queue waiting duration in seconds',
            buckets=(0.1, 0.5, 1, 5, 10, 30, 60, 120)
        )
        
        self.task_utilization = Gauge(
            'agent_task_utilization',
            'Task utilization ratio (active_tasks / max_concurrent_tasks)'
        )
        
        # ====================
        # gRPC Service Metrics
        # ====================
        
        self.grpc_requests_total = Counter(
            'agent_grpc_requests_total',
            'Total number of gRPC requests',
            ['method']
        )
        
        self.grpc_request_duration_seconds = Histogram(
            'agent_grpc_request_duration_seconds',
            'gRPC request duration in seconds',
            ['method'],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
        )
        
        self.grpc_errors_total = Counter(
            'agent_grpc_errors_total',
            'Total number of gRPC errors',
            ['method', 'status_code']
        )
        
        self.grpc_stream_connections = Gauge(
            'agent_grpc_stream_connections',
            'Number of active gRPC stream connections',
            ['method']
        )
        
        # ====================
        # Business Resource Metrics
        # ====================
        
        self.tokens_consumed_total = Counter(
            'agent_tokens_consumed_total',
            'Total tokens consumed',
            ['type']  # input, output, total
        )
        
        self.execution_cost_total = Counter(
            'agent_execution_cost_total',
            'Total execution cost',
            ['currency']
        )
        
        self.sandbox_created_total = Counter(
            'agent_sandbox_created_total',
            'Total number of sandboxes created',
            ['sandbox_type']  # Windows, Linux, Android, etc.
        )
        
        self.proxy_steps_total = Counter(
            'agent_proxy_steps_total',
            'Total number of action steps executed'
        )
        
        self.task_steps = Histogram(
            'agent_task_steps',
            'Number of steps per task',
            buckets=(1, 5, 10, 20, 30, 50, 100, 200)
        )
        
        # ====================
        # System Resource Metrics
        # ====================
        
        self.memory_usage_bytes = Gauge(
            'agent_memory_usage_bytes',
            'Memory used for task state storage and caching'
        )
        
        self.temp_files_count = Gauge(
            'agent_temp_files_count',
            'Number of temporary files in runtime directory'
        )
        
        self.stream_manager_tasks = Gauge(
            'agent_stream_manager_tasks',
            'Number of tasks registered in stream manager'
        )
        
        # ====================
        # Performance Health Metrics
        # ====================
        
        self.task_success_rate = Gauge(
            'agent_task_success_rate',
            'Task success rate (completed_tasks / total_tasks)'
        )
        
        self.task_latency_seconds = Summary(
            'agent_task_latency_seconds',
            'Task latency distribution (P50, P95, P99)'
        )
        
        self.service_uptime_seconds = Gauge(
            'agent_service_uptime_seconds',
            'Service uptime in seconds'
        )
        
        self.config_updates_total = Counter(
            'agent_config_updates_total',
            'Total number of configuration updates',
            ['config_type']  # global, task-specific
        )
        
        # Service info
        self.service_info = Info(
            'agent_service',
            'Agent service information'
        )
        
        # Record start time
        self._start_time = time.time()
    
    def _init_noop_metrics(self):
        """Initialize no-op metrics when Prometheus is disabled."""
        noop = NoOpMetric()
        
        # Task Lifecycle Metrics
        self.tasks_created_total = noop
        self.tasks_active = noop
        self.task_execution_duration_seconds = noop
        self.task_queue_wait_duration_seconds = noop
        self.task_utilization = noop
        
        # gRPC Service Metrics
        self.grpc_requests_total = noop
        self.grpc_request_duration_seconds = noop
        self.grpc_errors_total = noop
        self.grpc_stream_connections = noop
        
        # Business Resource Metrics
        self.tokens_consumed_total = noop
        self.execution_cost_total = noop
        self.sandbox_created_total = noop
        self.proxy_steps_total = noop
        self.task_steps = noop
        
        # System Resource Metrics
        self.memory_usage_bytes = noop
        self.temp_files_count = noop
        self.stream_manager_tasks = noop
        
        # Performance Health Metrics
        self.task_success_rate = noop
        self.task_latency_seconds = noop
        self.service_uptime_seconds = noop
        self.config_updates_total = noop
        self.service_info = noop
    
    def update_service_info(self, version: str, max_concurrent_tasks: int, log_level: str, domain: str):
        """Update service information metric."""
        if self.enabled:
            self.service_info.info({
                'version': version,
                'max_concurrent_tasks': str(max_concurrent_tasks),
                'log_level': log_level,
                'domain': domain
            })
    
    def update_uptime(self):
        """Update service uptime metric."""
        if self.enabled:
            self.service_uptime_seconds.set(time.time() - self._start_time)
    
    def record_task_created(self, status: str = "pending"):
        """Record a new task creation."""
        if self.enabled:
            self.tasks_created_total.labels(status=status).inc()
    
    def record_task_active(self, count: int):
        """Record the number of active tasks."""
        if self.enabled:
            self.tasks_active.set(count)
    
    def record_task_utilization(self, active_tasks: int, max_tasks: int):
        """Record task utilization ratio."""
        if self.enabled:
            if max_tasks > 0:
                self.task_utilization.set(active_tasks / max_tasks)
    
    def record_task_execution_duration(self, duration_seconds: float):
        """Record task execution duration."""
        if self.enabled:
            self.task_execution_duration_seconds.observe(duration_seconds)
            self.task_latency_seconds.observe(duration_seconds)
    
    def record_task_queue_wait(self, duration_seconds: float):
        """Record task queue wait duration."""
        if self.enabled:
            self.task_queue_wait_duration_seconds.observe(duration_seconds)
    
    def record_grpc_request(self, method: str):
        """Record a gRPC request."""
        if self.enabled:
            self.grpc_requests_total.labels(method=method).inc()
    
    def record_grpc_error(self, method: str, status_code: str):
        """Record a gRPC error."""
        if self.enabled:
            self.grpc_errors_total.labels(method=method, status_code=status_code).inc()
    
    def record_grpc_stream_connection(self, method: str, delta: int):
        """Record change in gRPC stream connections (delta +1 or -1)."""
        if self.enabled:
            if delta > 0:
                self.grpc_stream_connections.labels(method=method).inc(delta)
            elif delta < 0:
                self.grpc_stream_connections.labels(method=method).dec(-delta)
    
    def record_tokens(self, input_tokens: int, output_tokens: int):
        """Record token consumption."""
        if self.enabled:
            self.tokens_consumed_total.labels(type='input').inc(input_tokens)
            self.tokens_consumed_total.labels(type='output').inc(output_tokens)
            self.tokens_consumed_total.labels(type='total').inc(input_tokens + output_tokens)
    
    def record_cost(self, cost: float, currency: str = "USD"):
        """Record execution cost."""
        if self.enabled:
            self.execution_cost_total.labels(currency=currency).inc(cost)
    
    def record_sandbox_created(self, sandbox_type: str):
        """Record sandbox creation."""
        if self.enabled:
            self.sandbox_created_total.labels(sandbox_type=sandbox_type).inc()
    
    def record_task_steps(self, steps: int):
        """Record number of steps in a task."""
        if self.enabled:
            self.task_steps.observe(steps)
            self.proxy_steps_total.inc(steps)
    
    def record_config_update(self, config_type: str = "global"):
        """Record configuration update."""
        if self.enabled:
            self.config_updates_total.labels(config_type=config_type).inc()
    
    def update_system_metrics(self, memory_bytes: int = None, temp_files: int = None, 
                            stream_tasks: int = None):
        """Update system resource metrics."""
        if self.enabled:
            if memory_bytes is not None:
                self.memory_usage_bytes.set(memory_bytes)
            if temp_files is not None:
                self.temp_files_count.set(temp_files)
            if stream_tasks is not None:
                self.stream_manager_tasks.set(stream_tasks)
    
    def update_success_rate(self, completed_tasks: int, total_tasks: int):
        """Update task success rate."""
        if self.enabled:
            if total_tasks > 0:
                self.task_success_rate.set(completed_tasks / total_tasks)
    
    def grpc_method_timer(self, method_name: str):
        """
        Context manager for timing gRPC method execution.
        
        Usage:
            with metrics.grpc_method_timer("RunAgentInstruction"):
                # ... method implementation ...
        """
        if self.enabled:
            return self.grpc_request_duration_seconds.labels(method=method_name).time()
        else:
            return _NoOpContextManager()
    
    def start_http_server(self, port: int = 8000):
        """
        Start HTTP server for Prometheus to scrape metrics.
        
        Args:
            port: Port to listen on (default: 8000)
        """
        if self.enabled:
            try:
                start_http_server(port)
                logger.info(f"Prometheus metrics HTTP server started on port {port}")
            except Exception as e:
                logger.error(f"Failed to start Prometheus HTTP server: {e}")
        else:
            logger.debug("Prometheus metrics HTTP server not started (metrics disabled)")


# Global metrics instance
_metrics_instance: Optional[PrometheusMetrics] = None


def get_metrics_instance() -> PrometheusMetrics:
    """
    Get or create the global Prometheus metrics instance.
    
    Returns:
        PrometheusMetrics instance (may be disabled/no-op)
    """
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = PrometheusMetrics()
    return _metrics_instance


def grpc_method_metrics(method_name: str):
    """
    Decorator for gRPC methods to automatically record metrics.
    
    Usage:
        @grpc_method_metrics("GetAgentInfo")
        async def GetAgentInfo(self, request, context):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            metrics = get_metrics_instance()
            metrics.record_grpc_request(method_name)
            
            start_time = time.time()
            error_occurred = False
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                # Extract gRPC status code if available
                status_code = getattr(e, 'code', 'UNKNOWN')
                if hasattr(status_code, 'name'):
                    status_code = status_code.name
                metrics.record_grpc_error(method_name, str(status_code))
                raise
            finally:
                duration = time.time() - start_time
                if metrics.enabled:
                    metrics.grpc_request_duration_seconds.labels(method=method_name).observe(duration)
        
        return wrapper
    return decorator
