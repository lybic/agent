"""
Planning module for Manager
Handles task planning, DAG generation, and context building
"""

import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass

from gui_agents.utils.common_utils import Node
from gui_agents.maestro.data_models import SubtaskData
from gui_agents.maestro.manager.utils import (
    enhance_subtasks, generate_dag, topological_sort
)
from gui_agents.maestro.manager.planning_helpers import (
    get_planning_context, generate_planning_prompt
)

logger = logging.getLogger(__name__)


class PlanningScenario(str, Enum):
    """Planning scenario types"""
    REPLAN = "replan"
    SUPPLEMENT = "supplement"


@dataclass
class PlanningResult:
    """Planning result data structure"""
    success: bool
    scenario: str
    subtasks: List[Dict]
    supplement: str
    reason: str
    created_at: str


class PlanningHandler:
    """Handles task planning and DAG generation"""
    
    def __init__(self, global_state, planner_agent, dag_translator_agent, 
                 knowledge_base, search_engine, platform, enable_search, enable_narrative):
        self.global_state = global_state
        self.planner_agent = planner_agent
        self.dag_translator_agent = dag_translator_agent
        self.knowledge_base = knowledge_base
        self.search_engine = search_engine
        self.platform = platform
        self.enable_search = enable_search
        self.enable_narrative = enable_narrative
        self.planning_history = []
        self.replan_attempts = 0
    
    def handle_planning_scenario(self, scenario: PlanningScenario, trigger_code: str = "controller") -> PlanningResult:
        """Handle planning scenarios (INITIAL_PLAN/REPLAN) with specific trigger_code context"""
        # Get planning context with trigger_code
        context = get_planning_context(
            self.global_state, 
            self.platform, 
            self.replan_attempts, 
            self.planning_history, 
            trigger_code
        )

        # Retrieve external knowledge (web + narrative) and optionally fuse
        integrated_knowledge = self._retrieve_and_fuse_knowledge(context)

        # Generate planning prompt (with integrated knowledge if any) based on trigger_code
        prompt = generate_planning_prompt(context, integrated_knowledge=integrated_knowledge, trigger_code=trigger_code)

        # Execute planning using the registered planner tool
        plan_result, total_tokens, cost_string = self.planner_agent.execute_tool(
            "planner_role", {
                "str_input": prompt,
                "img_input": context.get("screenshot")
            })

        # Log planning operation (reflect initial vs replan based on attempts)
        scenario_label = context.get("planning_scenario", scenario.value)
        self.global_state.log_llm_operation(
            "manager", "task_planning", {
                "scenario": scenario_label,
                "trigger_code": trigger_code,
                "plan_result": plan_result,
                "tokens": total_tokens,
                "cost": cost_string
            },
            str_input=prompt,
            # img_input=context.get("screenshot")
        )

        # After planning, also generate DAG and action queue
        dag_info, dag_obj = generate_dag(self.dag_translator_agent, self.global_state, context.get("task_objective", ""), plan_result)
        action_queue: List[Node] = topological_sort(dag_obj)

        # Parse planning result
        try:
            # Validate and enhance subtasks
            enhanced_subtasks = enhance_subtasks(action_queue, self.global_state.task_id)

            # Determine if we are in re-plan phase based on attempts
            is_replan_now = context.get("planning_scenario") == "replan"
            first_new_subtask_id: Optional[str] = None

            if is_replan_now:
                # Remove all not-yet-completed (pending) subtasks
                task = self.global_state.get_task()
                old_pending_ids = list(task.pending_subtask_ids or [])
                if old_pending_ids:
                    self.global_state.delete_subtasks(old_pending_ids)

                # Append new subtasks and capture the first new subtask id
                for i, subtask_dict in enumerate(enhanced_subtasks):
                    subtask_data = SubtaskData(
                        subtask_id=subtask_dict["subtask_id"],
                        task_id=subtask_dict["task_id"],
                        title=subtask_dict["title"],
                        description=subtask_dict["description"],
                        assignee_role=subtask_dict["assignee_role"],
                        status=subtask_dict["status"],
                        attempt_no=subtask_dict["attempt_no"],
                        reasons_history=subtask_dict["reasons_history"],
                        command_trace_ids=subtask_dict["command_trace_ids"],
                        gate_check_ids=subtask_dict["gate_check_ids"],
                        last_reason_text=subtask_dict["last_reason_text"],
                        last_gate_decision=subtask_dict["last_gate_decision"],
                        created_at=subtask_dict["created_at"],
                        updated_at=subtask_dict["updated_at"],
                    )
                    new_id = self.global_state.add_subtask(subtask_data)
                    if first_new_subtask_id is None:
                        first_new_subtask_id = new_id
            else:
                # Initial planning: append new subtasks; set current only if not set
                for subtask_dict in enhanced_subtasks:
                    subtask_data = SubtaskData(
                        subtask_id=subtask_dict["subtask_id"],
                        task_id=subtask_dict["task_id"],
                        title=subtask_dict["title"],
                        description=subtask_dict["description"],
                        assignee_role=subtask_dict["assignee_role"],
                        status=subtask_dict["status"],
                        attempt_no=subtask_dict["attempt_no"],
                        reasons_history=subtask_dict["reasons_history"],
                        command_trace_ids=subtask_dict["command_trace_ids"],
                        gate_check_ids=subtask_dict["gate_check_ids"],
                        last_reason_text=subtask_dict["last_reason_text"],
                        last_gate_decision=subtask_dict["last_gate_decision"],
                        created_at=subtask_dict["created_at"],
                        updated_at=subtask_dict["updated_at"],
                    )
                    self.global_state.add_subtask(subtask_data)

            # Update planning history
            self.planning_history.append({
                "scenario": scenario_label,
                "trigger_code": trigger_code,
                "subtasks": enhanced_subtasks,
                "dag": dag_info.get("dag", ""),
                "action_queue_len": len(action_queue),
                "timestamp": datetime.now().isoformat(),
                "tokens": total_tokens,
                "cost": cost_string
            })

            # Bump attempts after any successful planning to distinguish initial vs replan next time
            self.replan_attempts += 1

            return PlanningResult(
                success=True,
                scenario=scenario_label,
                subtasks=enhanced_subtasks,
                supplement="",
                reason=f"Successfully planned {len(enhanced_subtasks)} subtasks with trigger_code: {trigger_code}",
                created_at=datetime.now().isoformat()
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse planning result: {e}")
            return PlanningResult(
                success=False,
                scenario=scenario_label,
                subtasks=[],
                supplement="",
                reason=f"Failed to parse planning result: {str(e)}",
                created_at=datetime.now().isoformat()
            )

    def _retrieve_and_fuse_knowledge(self, context: Dict[str, Any]) -> str:
        """Retrieve external knowledge (web + narrative) and optionally fuse"""
        integrated_knowledge = ""
        web_knowledge = None
        most_similar_task = ""
        retrieved_experience = None

        try:
            objective = context.get("task_objective", "")
            observation = {"screenshot": context.get("screenshot")}

            search_query = None
            if self.enable_search and self.search_engine:
                try:
                    # 1) formulate_query
                    formulate_start = time.time()
                    search_query, f_tokens, f_cost = self.knowledge_base.formulate_query(
                        objective, observation)
                    formulate_duration = time.time() - formulate_start
                    self.global_state.log_operation(
                        "manager", "formulate_query", {
                            "tokens": f_tokens,
                            "cost": f_cost,
                            "query": search_query,
                            "duration": formulate_duration
                        })
                    # 2) websearch directly using search_engine
                    if search_query:
                        web_knowledge, ws_tokens, ws_cost = self.search_engine.execute_tool(
                            "websearch", {"query": search_query})
                        # Not all tools return token/cost; guard format
                        self.global_state.log_llm_operation(
                            "manager", "web_knowledge", {
                                "query": search_query,
                                "tokens": ws_tokens,
                                "cost": ws_cost
                            },
                            str_input=search_query
                        )
                except Exception as e:
                    logger.warning(f"Web search retrieval failed: {e}")

            if self.enable_narrative:
                try:
                    most_similar_task, retrieved_experience, n_tokens, n_cost = (
                        self.knowledge_base.retrieve_narrative_experience(
                            objective))
                    self.global_state.log_llm_operation(
                        "manager", "retrieve_narrative_experience", {
                            "tokens": n_tokens,
                            "cost": n_cost,
                            "task": most_similar_task
                        },
                        str_input=objective
                    )
                except Exception as e:
                    logger.warning(f"Narrative retrieval failed: {e}")

            # 3) Conditional knowledge fusion
            try:
                do_fusion_web = web_knowledge is not None and str(
                    web_knowledge).strip() != ""
                do_fusion_narr = retrieved_experience is not None and str(
                    retrieved_experience).strip() != ""
                if do_fusion_web or do_fusion_narr:
                    web_text = web_knowledge if do_fusion_web else None
                    similar_task = most_similar_task if do_fusion_narr else ""
                    exp_text = retrieved_experience if do_fusion_narr else ""
                    integrated_knowledge, k_tokens, k_cost = self.knowledge_base.knowledge_fusion(
                        observation=observation,
                        instruction=objective,
                        web_knowledge=web_text,
                        similar_task=similar_task,
                        experience=exp_text,
                    )
                    self.global_state.log_llm_operation("manager",
                                                    "knowledge_fusion", {
                                                        "tokens": k_tokens,
                                                        "cost": k_cost
                                                    },
                                                    str_input=f"Objective: {objective}, Web: {web_text}, Experience: {exp_text}")
            except Exception as e:
                logger.warning(f"Knowledge fusion failed: {e}")

        except Exception as e:
            logger.warning(f"Knowledge retrieval pipeline failed: {e}")

        return integrated_knowledge