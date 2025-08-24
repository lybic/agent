"""
Utility functions for Manager module
Contains helper functions for subtask management, DAG operations, and context building
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import defaultdict

from gui_agents.utils.common_utils import Node, Dag, parse_dag
from gui_agents.utils.id_utils import generate_uuid
from gui_agents.maestro.enums import SubtaskStatus, GateDecision

logger = logging.getLogger(__name__)


def enhance_subtasks(subtasks: List[Node], task_id: str) -> List[Dict]:
    """Enhance subtasks with additional metadata.
    Accepts a list of Node where:
    - name -> title
    - info -> description
    - assignee_role -> assignee_role
    """
    enhanced_subtasks = []

    for i, node in enumerate(subtasks):
        node_title = getattr(node, "name", None) or f"Subtask {i+1}"
        node_description = getattr(node, "info", "") or ""
        node_role = getattr(node, "assignee_role", None) or "operator"

        # Validate assignee role
        if node_role not in ["operator", "analyst", "technician"]:
            node_role = "operator"

        enhanced_subtask = {
            "subtask_id": f"subtask-{generate_uuid()[:4]}-{i+1}",
            "task_id": task_id,
            "title": node_title,
            "description": node_description,
            "assignee_role": node_role,
            "status": SubtaskStatus.READY.value,
            "attempt_no": 1,
            "reasons_history": [],
            "command_trace_ids": [],
            "gate_check_ids": [],
            "last_reason_text": "",
            "last_gate_decision": "",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        enhanced_subtasks.append(enhanced_subtask)

    return enhanced_subtasks


def generate_dag(dag_translator_agent, global_state, instruction: str, plan: str) -> tuple[Dict, Dag]:
    """Generate a DAG from instruction and plan using dag_translator, with retries and fallback."""
    max_retries = 3
    retry = 0
    dag_obj: Optional[Dag] = None
    dag_raw = ""
    total_tokens = 0
    cost_string = ""
    dag_input = f"Instruction: {instruction}\nPlan: {plan}"

    while retry < max_retries and dag_obj is None:
        dag_raw, total_tokens, cost_string = dag_translator_agent.execute_tool(
            "dag_translator", {"str_input": dag_input}
        )
        dag_obj = parse_dag(dag_raw)
        retry += 1 if dag_obj is None else 0

    global_state.log_llm_operation(
        "manager", "generated_dag", {
            "dag_obj": str(dag_obj),
            "tokens": total_tokens,
            "cost": cost_string,
            "retry_count": retry-1
        },
        str_input=dag_input
    )

    if dag_obj is None:
        # Fallback to simple DAG
        default_node = Node(name="Execute Task", info=f"Execute instruction: {instruction}", assignee_role="operator")
        dag_obj = Dag(nodes=[default_node], edges=[])
        global_state.add_event("manager", "default_dag_created", "fallback simple DAG used")

    return {"dag": dag_raw}, dag_obj


def topological_sort(dag: Dag) -> List[Node]:
    """Topological sort of the DAG using DFS; returns node list on error."""
    if not getattr(dag, 'nodes', None):
        return []
    if len(dag.nodes) == 1:
        return dag.nodes

    def dfs(node_name, visited, temp_visited, stack):
        if node_name in temp_visited:
            raise ValueError(f"Cycle detected in DAG involving node: {node_name}")
        if visited.get(node_name, False):
            return
        temp_visited.add(node_name)
        visited[node_name] = True
        for neighbor in adj_list.get(node_name, []):
            if not visited.get(neighbor, False):
                dfs(neighbor, visited, temp_visited, stack)
        temp_visited.remove(node_name)
        stack.append(node_name)

    try:
        adj_list = defaultdict(list)
        for u, v in dag.edges:
            if not u or not v:
                continue
            adj_list[u.name].append(v.name)

        visited = {node.name: False for node in dag.nodes}
        temp_visited = set()
        stack: List[str] = []
        for node in dag.nodes:
            if not visited.get(node.name, False):
                dfs(node.name, visited, temp_visited, stack)

        sorted_nodes: List[Node] = []
        for name in stack[::-1]:
            matching = [n for n in dag.nodes if n.name == name]
            if matching:
                sorted_nodes.append(matching[0])
        return sorted_nodes
    except Exception:
        return dag.nodes


def get_failed_subtasks_info(global_state) -> str:
    """Get information about failed subtasks"""
    failed_subtasks = []
    all_subtasks = global_state.get_subtasks()

    for subtask in all_subtasks:
        if subtask.status == SubtaskStatus.REJECTED.value:
            failed_subtasks.append({
                "id": subtask.subtask_id,
                "title": subtask.title,
                "description": subtask.description,
                "assignee_role": subtask.assignee_role,
                "reason": subtask.last_reason_text or "Unknown reason",
            })

    if not failed_subtasks:
        return "No failed subtasks"

    return json.dumps(failed_subtasks, indent=2)


def get_failure_reasons(global_state) -> str:
    """Get failure reasons from subtask history"""
    failure_reasons = []
    all_subtasks = global_state.get_subtasks()

    for subtask in all_subtasks:
        if subtask.status == SubtaskStatus.REJECTED.value:
            reasons = subtask.reasons_history or []
            if reasons:
                failure_reasons.extend([r.get("text", "") for r in reasons])

    return "; ".join(failure_reasons) if failure_reasons else "No specific failure reasons"


def get_history_subtasks_info(global_state) -> str:
    """Get information about completed subtasks"""
    history_subtasks = []
    task = global_state.get_task()
    all_subtasks = global_state.get_subtasks()

    if task.history_subtask_ids:
        for subtask_id in task.history_subtask_ids:
            subtask = next((s for s in all_subtasks if s.subtask_id == subtask_id), None)
            if subtask:
                history_subtasks.append({
                    "id": subtask.subtask_id,
                    "title": subtask.title,
                    "description": subtask.description,
                    "assignee_role": subtask.assignee_role,
                    "status": subtask.status,
                    "completion_reason": subtask.last_reason_text or "Completed successfully",
                    "last_gate_decision": subtask.last_gate_decision,
                })

    if not history_subtasks:
        return "No completed subtasks"

    return json.dumps(history_subtasks, indent=2)


def get_pending_subtasks_info(global_state) -> str:
    """Get information about pending subtasks"""
    pending_subtasks = []
    task = global_state.get_task()
    all_subtasks = global_state.get_subtasks()

    if task.pending_subtask_ids:
        for subtask_id in task.pending_subtask_ids:
            subtask = next((s for s in all_subtasks if s.subtask_id == subtask_id), None)
            if subtask:
                pending_subtasks.append({
                    "id": subtask.subtask_id,
                    "title": subtask.title,
                    "description": subtask.description,
                    "assignee_role": subtask.assignee_role,
                    "status": subtask.status,
                    "attempt_no": subtask.attempt_no,
                })

    if not pending_subtasks:
        return "No pending subtasks"

    return json.dumps(pending_subtasks, indent=2)


def count_subtasks_from_info(subtasks_info: str) -> int:
    """Count subtasks from the JSON string info returned by _get_*_subtasks_info methods"""
    if not subtasks_info or subtasks_info in ["No completed subtasks", "No pending subtasks"]:
        return 0
    try:
        subtasks_list = json.loads(subtasks_info)
        return len(subtasks_list) if isinstance(subtasks_list, list) else 0
    except (json.JSONDecodeError, TypeError):
        return 0


def get_current_failed_subtask(global_state) -> Optional[Dict[str, Any]]:
    """获取当前失败的subtask信息"""
    task = global_state.get_task()
    if task.current_subtask_id:
        subtask = global_state.get_subtask(task.current_subtask_id)
        if subtask and subtask.status == SubtaskStatus.REJECTED.value:
            return {
                "subtask_id": subtask.subtask_id,
                "title": subtask.title,
                "description": subtask.description,
                "assignee_role": subtask.assignee_role,
                "last_reason_text": subtask.last_reason_text,
                "reasons_history": subtask.reasons_history
            }
    return None


def get_quality_check_failure_info(global_state) -> Dict[str, Any]:
    """获取质检失败的具体信息"""
    task = global_state.get_task()
    if task.current_subtask_id:
        # 获取最新的质检记录
        latest_gate = global_state.get_latest_gate_check_for_subtask(task.current_subtask_id)
        if latest_gate:
            return {
                "gate_check_id": latest_gate.gate_check_id,
                "decision": latest_gate.decision,
                "notes": latest_gate.notes,
                "trigger": latest_gate.trigger,
                "created_at": latest_gate.created_at
            }
    return {"error": "No quality check information available"}


def get_final_check_failure_info(global_state) -> Dict[str, Any]:
    """获取最终质检失败的信息"""
    # 获取所有质检记录
    gate_checks = global_state.get_gate_checks()
    if gate_checks:
        latest_gate = max(gate_checks, key=lambda x: x.created_at)
        return {
            "latest_gate_check": {
                "gate_check_id": latest_gate.gate_check_id,
                "decision": latest_gate.decision,
                "notes": latest_gate.notes,
                "trigger": latest_gate.trigger,
                "created_at": latest_gate.created_at
            },
            "total_gate_checks": len(gate_checks),
            "failed_gate_checks": len([gc for gc in gate_checks if gc.decision == GateDecision.GATE_FAIL.value])
        }
    return {"error": "No final check information available"}


def get_execution_time_info(global_state) -> Dict[str, Any]:
    """获取执行时间信息"""
    task = global_state.get_task()
    return {
        "step_num": task.step_num,
        "plan_num": task.plan_num,
        "task_created_at": task.created_at,
        "current_time": datetime.now().isoformat()
    }


def get_supplement_info(global_state) -> Dict[str, Any]:
    """获取补充资料信息"""
    supplement_content = global_state.get_supplement()
    return {
        "supplement_content": supplement_content,
        "supplement_length": len(supplement_content) if supplement_content else 0
    }
