# Prometheus Monitoring for GUI Agents

This directory contains the Prometheus metrics integration for the GUI Agents gRPC service.

## Overview

The Prometheus integration provides optional monitoring capabilities for various aspects of the agent service, including:

- **Task Lifecycle Metrics**: Track task creation, execution, and completion
- **gRPC Service Metrics**: Monitor request counts, latency, and errors
- **Business Resource Metrics**: Track token consumption, costs, and sandbox usage
- **System Resource Metrics**: Monitor memory usage and stream manager load
- **Performance Health Metrics**: Track success rates, latency percentiles, and uptime

## Installation

Prometheus monitoring is optional and requires additional dependencies:

```bash
# Install with Prometheus support
pip install -e ".[prometheus]"

# Or install dependencies separately
pip install prometheus-client psutil
```

## Configuration

Prometheus monitoring is controlled via environment variables:

- `ENABLE_PROMETHEUS` - Enable/disable Prometheus metrics (default: `false`)
  - Set to `true`, `1`, or `yes` to enable
- `PROMETHEUS_PORT` - Port for Prometheus HTTP server (default: `8000`)

Example:

```bash
export ENABLE_PROMETHEUS=true
export PROMETHEUS_PORT=8000
python -m gui_agents.grpc_app
```

## Metrics

### Task Lifecycle Metrics

| Metric | Type | Description | Labels |
|--------|------|-------------|--------|
| `agent_tasks_created_total` | Counter | Total number of tasks created | `status` (pending, running, completed, failed, cancelled) |
| `agent_tasks_active` | Gauge | Number of currently active tasks | - |
| `agent_task_execution_duration_seconds` | Histogram | Task execution duration in seconds | - |
| `agent_task_queue_wait_duration_seconds` | Histogram | Task queue waiting duration in seconds | - |
| `agent_task_utilization` | Gauge | Task utilization ratio (active/max) | - |

### gRPC Service Metrics

| Metric | Type | Description | Labels |
|--------|------|-------------|--------|
| `agent_grpc_requests_total` | Counter | Total number of gRPC requests | `method` |
| `agent_grpc_request_duration_seconds` | Histogram | gRPC request duration in seconds | `method` |
| `agent_grpc_errors_total` | Counter | Total number of gRPC errors | `method`, `status_code` |
| `agent_grpc_stream_connections` | Gauge | Number of active gRPC stream connections | `method` |

### Business Resource Metrics

| Metric | Type | Description | Labels |
|--------|------|-------------|--------|
| `agent_tokens_consumed_total` | Counter | Total tokens consumed | `type` (input, output, total) |
| `agent_execution_cost_total` | Counter | Total execution cost | `currency` |
| `agent_sandbox_created_total` | Counter | Total number of sandboxes created | `sandbox_type` |
| `agent_proxy_steps_total` | Counter | Total number of action steps executed | - |
| `agent_task_steps` | Histogram | Number of steps per task | - |

### System Resource Metrics

| Metric | Type | Description | Labels |
|--------|------|-------------|--------|
| `agent_memory_usage_bytes` | Gauge | Memory used for task state storage | - |
| `agent_temp_files_count` | Gauge | Number of temporary files | - |
| `agent_stream_manager_tasks` | Gauge | Number of tasks in stream manager | - |

### Performance Health Metrics

| Metric | Type | Description | Labels |
|--------|------|-------------|--------|
| `agent_task_success_rate` | Gauge | Task success rate (completed/total) | - |
| `agent_task_latency_seconds` | Summary | Task latency distribution (P50, P95, P99) | - |
| `agent_service_uptime_seconds` | Gauge | Service uptime in seconds | - |
| `agent_config_updates_total` | Counter | Total number of configuration updates | `config_type` |

### Service Information

| Metric | Type | Description |
|--------|------|-------------|
| `agent_service_info` | Info | Agent service information (version, max_concurrent_tasks, log_level, domain) |

## Prometheus Configuration

Add the following to your Prometheus configuration file (`prometheus.yml`):

```yaml
scrape_configs:
  - job_name: 'gui_agents'
    static_configs:
      - targets: ['localhost:8000']
    scrape_interval: 15s
```

## Example Queries

### Average Task Execution Time
```promql
rate(agent_task_execution_duration_seconds_sum[5m]) / rate(agent_task_execution_duration_seconds_count[5m])
```

### Task Success Rate
```promql
agent_task_success_rate
```

### gRPC Request Rate by Method
```promql
rate(agent_grpc_requests_total[5m])
```

### Active Tasks
```promql
agent_tasks_active
```

### Task Utilization
```promql
agent_task_utilization
```

### Token Consumption Rate
```promql
rate(agent_tokens_consumed_total[5m])
```

### gRPC Error Rate
```promql
rate(agent_grpc_errors_total[5m])
```

## Grafana Dashboard

You can create a Grafana dashboard to visualize these metrics. Here's a suggested layout:

1. **Overview Panel**: Service uptime, active tasks, success rate
2. **Task Metrics**: Task creation rate, execution time, queue wait time
3. **gRPC Metrics**: Request rate, error rate, latency
4. **Resource Metrics**: Memory usage, token consumption, costs
5. **System Health**: Utilization, stream connections, temp files

## Testing

Run the test suite to verify Prometheus integration:

```bash
python tests/test_prometheus_metrics.py
```

The tests verify:
- Metrics work as no-ops when Prometheus is disabled
- Metrics collect data correctly when Prometheus is enabled
- Environment variable control works correctly
- Singleton pattern is properly implemented

## Architecture

The metrics module uses a singleton pattern with lazy initialization:

1. `PrometheusMetrics` class defines and manages all metrics
2. When Prometheus is disabled, all operations become no-ops
3. When Prometheus is enabled, metrics are collected and exposed via HTTP
4. The metrics instance is shared across the entire gRPC service

### No-Op Pattern

When `prometheus_client` is not installed or `ENABLE_PROMETHEUS=false`, all metric operations are no-ops:

```python
from gui_agents.metrics import get_metrics_instance

metrics = get_metrics_instance()  # Works even without prometheus_client
metrics.record_task_created("pending")  # No-op if disabled
```

This allows the code to always call metrics methods without checking if Prometheus is enabled.

## Performance Considerations

- Metrics collection has minimal overhead (microseconds per operation)
- HTTP server runs on a separate port and doesn't block gRPC requests
- Metrics are updated periodically (every 10 seconds) for system resources
- No data is persisted; Prometheus scrapes metrics from memory

## Security Considerations

- The Prometheus HTTP endpoint exposes operational metrics only
- No sensitive data (API keys, task content) is included in metrics
- The endpoint should be protected by network policies in production
- Consider using authentication/authorization if exposing publicly

## Troubleshooting

### Metrics not appearing in Prometheus

1. Verify `ENABLE_PROMETHEUS=true` is set
2. Check that prometheus_client is installed: `pip show prometheus-client`
3. Verify the HTTP server is running on the configured port
4. Check Prometheus can reach the endpoint: `curl http://localhost:8000/metrics`

### Memory usage increasing

- Prometheus metrics use minimal memory (KB per metric)
- High cardinality labels can increase memory usage
- The current implementation uses low-cardinality labels
- System metrics are updated periodically, not on every request

### Metrics showing incorrect values

- Ensure task lifecycle methods are being called correctly
- Check logs for errors in metrics collection
- Verify the service has been running long enough for metrics to accumulate
- Some metrics (like success_rate) require completed tasks to show data
