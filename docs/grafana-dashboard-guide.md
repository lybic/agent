# Grafana Dashboard for GUI Agents Service
#
# This is a simplified dashboard configuration. You can import this into Grafana
# or create your own custom dashboard using these queries as a starting point.

# Dashboard Panels and Queries

## 1. Overview Panel

### Service Uptime
Query: `agent_service_uptime_seconds`
Visualization: Stat
Unit: seconds

### Active Tasks
Query: `agent_tasks_active`
Visualization: Gauge
Max: Get from `agent_service_info` (maxConcurrentTasks)

### Task Success Rate
Query: `agent_task_success_rate * 100`
Visualization: Gauge
Unit: percent (0-100)
Thresholds:
  - 0-70: Red
  - 70-90: Yellow
  - 90-100: Green

### Task Utilization
Query: `agent_task_utilization * 100`
Visualization: Gauge
Unit: percent (0-100)

## 2. Task Metrics Panel

### Task Creation Rate
Query: `rate(agent_tasks_created_total[5m])`
Visualization: Graph
Legend: {{status}}

### Task Execution Time (P95)
Query: `histogram_quantile(0.95, rate(agent_task_execution_duration_seconds_bucket[5m]))`
Visualization: Graph
Unit: seconds

### Task Queue Wait Time (P95)
Query: `histogram_quantile(0.95, rate(agent_task_queue_wait_duration_seconds_bucket[5m]))`
Visualization: Graph
Unit: seconds

### Tasks by Status
Query: `sum by (status) (agent_tasks_created_total)`
Visualization: Pie Chart
Legend: {{status}}

## 3. gRPC Service Panel

### gRPC Request Rate
Query: `rate(agent_grpc_requests_total[5m])`
Visualization: Graph
Legend: {{method}}

### gRPC Error Rate
Query: `rate(agent_grpc_errors_total[5m])`
Visualization: Graph
Legend: {{method}} - {{status_code}}

### gRPC Latency (P50, P95, P99)
Queries:
  - P50: `histogram_quantile(0.50, rate(agent_grpc_request_duration_seconds_bucket[5m]))`
  - P95: `histogram_quantile(0.95, rate(agent_grpc_request_duration_seconds_bucket[5m]))`
  - P99: `histogram_quantile(0.99, rate(agent_grpc_request_duration_seconds_bucket[5m]))`
Visualization: Graph
Unit: seconds

### Active Stream Connections
Query: `sum(agent_grpc_stream_connections)`
Visualization: Graph

## 4. Business Metrics Panel

### Token Consumption Rate
Query: `rate(agent_tokens_consumed_total[5m])`
Visualization: Graph
Legend: {{type}}

### Total Tokens Consumed
Query: `agent_tokens_consumed_total`
Visualization: Stat
Legend: {{type}}

### Execution Cost Rate
Query: `rate(agent_execution_cost_total[1h])`
Visualization: Graph
Legend: {{currency}}
Unit: currency/hour

### Total Execution Cost
Query: `agent_execution_cost_total`
Visualization: Stat
Legend: {{currency}}

### Sandboxes Created
Query: `rate(agent_sandbox_created_total[5m])`
Visualization: Graph
Legend: {{sandbox_type}}

### Average Steps Per Task
Query: `rate(agent_proxy_steps_total[5m]) / rate(agent_tasks_created_total{status="completed"}[5m])`
Visualization: Stat
Unit: steps

## 5. System Resources Panel

### Memory Usage
Query: `agent_memory_usage_bytes`
Visualization: Graph
Unit: bytes

### Temporary Files
Query: `agent_temp_files_count`
Visualization: Graph

### Stream Manager Load
Query: `agent_stream_manager_tasks`
Visualization: Graph

## 6. Performance Health Panel

### Task Latency Distribution
Query: `rate(agent_task_latency_seconds_sum[5m]) / rate(agent_task_latency_seconds_count[5m])`
Visualization: Graph
Unit: seconds

### Configuration Updates
Query: `rate(agent_config_updates_total[5m])`
Visualization: Graph
Legend: {{config_type}}

# Grafana Dashboard JSON Template

To create a complete Grafana dashboard, use the Grafana UI to:

1. Create a new dashboard
2. Add panels using the queries above
3. Arrange panels into rows
4. Set appropriate visualizations and thresholds
5. Export as JSON
6. Save to grafana-dashboards/gui-agents.json

# Quick Import Instructions

1. Open Grafana (http://localhost:3000)
2. Go to Dashboards → Import
3. Click "Upload JSON file"
4. Use the exported JSON or create panels manually
5. Select Prometheus as the data source
6. Click "Import"

# Example Time Ranges

- Last 5 minutes: Detailed real-time view
- Last 1 hour: Recent activity
- Last 24 hours: Daily patterns
- Last 7 days: Weekly trends
