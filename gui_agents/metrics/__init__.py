"""
Metrics collection module for GUI Agents.

This module provides optional Prometheus metrics collection for monitoring
the agent service. It can be safely imported even if prometheus_client is not installed.
"""

from .prometheus_metrics import PrometheusMetrics, get_metrics_instance

__all__ = ['PrometheusMetrics', 'get_metrics_instance']
