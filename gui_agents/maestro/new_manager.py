"""
New Manager Module for GUI-Agent Architecture
Responsible for task planning, decomposition, and resource allocation
"""

import json
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union
from enum import Enum

from gui_agents.utils.common_utils import Node, Dag, parse_dag
from gui_agents.utils.id_utils import generate_uuid
from gui_agents.tools.new_tools import NewTools
# from gui_agents.core.new_knowledge import NewKnowledgeBase
from gui_agents.prompts import module

from .new_global_state import NewGlobalState
from .data_models import SubtaskData  # Add import for SubtaskData
from .enums import (
    TaskStatus, SubtaskStatus, GateDecision, GateTrigger,
    ControllerState, ExecStatus, ManagerStatus, TRIGGER_CODE_BY_MODULE
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


@dataclass
class SupplementStrategy:
    """Supplement collection strategy"""
    needed_info: str
    collection_strategy: Dict[str, Any]
    collected_data: str


class NewManager:
    """
    Enhanced Manager module for GUI-Agent architecture
    Responsible for task planning, decomposition, and resource allocation
    """

    def __init__(
        self,
        tools_dict: Dict[str, Any],
        global_state: NewGlobalState,
        local_kb_path: str = "",
        platform: str = "Windows",
        enable_search: bool = False,
        enable_narrative: bool = False,
        max_replan_attempts: int = 3,
    ):
        """
        Initialize the Manager module
        
        Args:
            tools_dict: Dictionary containing tool configurations
            global_state: Global state instance
            local_kb_path: Path to local knowledge base
            platform: Target platform (Windows/Darwin/Ubuntu)
            enable_search: Whether to enable web search
            max_replan_attempts: Maximum replanning attempts
        """
        self.tools_dict = tools_dict
        self.global_state = global_state
        self.local_kb_path = local_kb_path
        self.platform = platform
        self.enable_search = enable_search
        self.enable_narrative = enable_narrative
        self.max_replan_attempts = max_replan_attempts

        # Initialize status
        self.status = ManagerStatus.IDLE
        self.plan_scenario = PlanningScenario.REPLAN
        self.planning_history = []
        self.replan_attempts = 0
        self.supplement_attempts = 0

        # Initialize tools
        self._initialize_tools()

        # # Initialize knowledge base
        # self._initialize_knowledge_base()

        logger.info("NewManager initialized successfully")

    def _initialize_tools(self):
        """Initialize required tools with backward-compatible keys"""
        self.planner_agent_name = "planner_role"
        self.supplement_agent_name = "supplement_role"
        self.dag_translator_agent_name = "dag_translator"

        # planner_agent
        self.planner_agent = NewTools()
        self.planner_agent.register_tool(
            self.planner_agent_name,
            self.tools_dict[self.planner_agent_name]["provider"],
            self.tools_dict[self.planner_agent_name]["model"],
        )

        # dag_translator_agent
        self.dag_translator_agent = NewTools()
        self.dag_translator_agent.register_tool(
            self.dag_translator_agent_name,
            self.tools_dict[self.dag_translator_agent_name]["provider"],
            self.tools_dict[self.dag_translator_agent_name]["model"],
        )

        # supplement_agent
        self.supplement_agent = NewTools()
        self.supplement_agent.register_tool(
            self.supplement_agent_name,
            self.tools_dict[self.supplement_agent_name]["provider"],
            self.tools_dict[self.supplement_agent_name]["model"],
        )

        # Embedding engine for Memory
        self.embedding_engine = NewTools()
        self.embedding_engine.register_tool(
            "embedding",
            self.tools_dict["embedding"]["provider"],
            self.tools_dict["embedding"]["model"],
        )

        # Web search engine (optional)
        if self.enable_search and self.tools_dict.get("websearch"):
            self.search_engine = NewTools()
            self.search_engine.register_tool(
                "websearch",
                self.tools_dict["websearch"]["provider"],
                self.tools_dict["websearch"]["model"],
            )
        else:
            self.search_engine = None

    def _initialize_knowledge_base(self):
        """Initialize knowledge base for RAG operations"""
        kb_tools_dict = {
            "query_formulator": self.tools_dict.get("query_formulator", {}),
            "context_fusion": self.tools_dict.get("context_fusion", {}),
            "narrative_summarization": self.tools_dict.get("narrative_summarization", {}),
            "episode_summarization": self.tools_dict.get("episode_summarization", {}),
        }

        self.knowledge_base = NewKnowledgeBase(
            embedding_engine=self.embedding_engine,
            local_kb_path=self.local_kb_path,
            platform=self.platform,
            Tools_dict=kb_tools_dict,
        )

    def plan_task(self, scenario: Union[PlanningScenario, str]) -> PlanningResult:
        """
        Execute task planning based on scenario and current trigger_code
        
        Args:
            scenario: Planning scenario (INITIAL_PLAN|REPLAN|SUPPLEMENT or enum)
            
        Returns:
            PlanningResult: Planning result with subtasks or supplement
        """
        try:
            scenario_enum = self._normalize_scenario(scenario)
            self.status = ManagerStatus.PLANNING
            
            # 获取当前的 trigger_code 来决定具体的规划策略
            current_trigger_code = self._get_current_trigger_code()
            
            self.global_state.log_operation("manager", "planning_start", {
                "scenario": scenario_enum.value,
                "trigger_code": current_trigger_code,
                "timestamp": time.time()
            })

            if scenario_enum == PlanningScenario.SUPPLEMENT:
                return self._handle_supplement_scenario()
            else:
                return self._handle_planning_scenario(scenario_enum, current_trigger_code)

        except Exception as e:
            logger.error(f"Planning failed: {e}")
            self.status = ManagerStatus.ERROR
            self.global_state.log_operation("manager", "planning_error", {
                "error": str(e),
                "timestamp": time.time()
            })

            return PlanningResult(
                success=False,
                scenario=self._normalize_scenario(scenario).value if isinstance(
                    scenario, str) else scenario.value,
                subtasks=[],
                supplement="",
                reason=f"Planning failed: {str(e)}",
                created_at=datetime.now().isoformat())
        finally:
            self.status = ManagerStatus.IDLE

    def _normalize_scenario(
            self, scenario: Union[PlanningScenario, str]) -> PlanningScenario:
        """Normalize string/enum scenario to PlanningScenario enum (case-insensitive)."""
        if isinstance(scenario, PlanningScenario):
            return scenario
        s = str(scenario).strip().lower()
        if s in {"replan", "re-plan"}:
            return PlanningScenario.REPLAN
        if s in {"supplement", "supp"}:
            return PlanningScenario.SUPPLEMENT
        # Default to INITIAL_PLAN if unknown
        return PlanningScenario.REPLAN

    def _handle_planning_scenario(self,
                                  scenario: PlanningScenario,
                                  trigger_code: str = "controller") -> PlanningResult:
        """Handle planning scenarios (INITIAL_PLAN/REPLAN) with specific trigger_code context"""
        # Get planning context with trigger_code
        context = self._get_planning_context(scenario, trigger_code)

        # Retrieve external knowledge (web + narrative) and optionally fuse
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
                    # self.global_state.add_event("manager", "retrieve_knowledge_error", str(e))

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
                    # self.global_state.add_event("manager", "retrieve_narrative_error", str(e))

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
                        web_knowledge=web_text,  #type: ignore
                        similar_task=similar_task,
                        experience=exp_text,  #type: ignore
                    )
                    self.global_state.log_llm_operation("manager",
                                                    "knowledge_fusion", {
                                                        "tokens": k_tokens,
                                                        "cost": k_cost
                                                    },
                                                    str_input=f"Objective: {objective}, Web: {web_text}, Experience: {exp_text}")
            except Exception as e:
                logger.warning(f"Knowledge fusion failed: {e}")
                # self.global_state.add_event("manager", "knowledge_fusion_error", str(e))

        except Exception as e:
            logger.warning(f"Knowledge retrieval pipeline failed: {e}")
            # self.global_state.add_event("manager", "knowledge_pipeline_error", str(e))

        # Generate planning prompt (with integrated knowledge if any) based on trigger_code
        prompt = self._generate_planning_prompt(
            scenario, context, integrated_knowledge=integrated_knowledge, trigger_code=trigger_code)

        # Execute planning using the registered planner tool
        plan_result, total_tokens, cost_string = self.planner_agent.execute_tool(
            self.planner_agent_name, {
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
            img_input=context.get("screenshot")
        )

        # After planning, also generate DAG and action queue
        dag_info, dag_obj = self._generate_dag(context.get("task_objective", ""), plan_result)
        action_queue: List[Node] = self._topological_sort(dag_obj)

        # Parse planning result
        try:
            # Validate and enhance subtasks
            enhanced_subtasks = self._enhance_subtasks(action_queue)

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

                # Switch current subtask to the first newly planned subtask
                # if first_new_subtask_id:
                # self.global_state.set_current_subtask_id(first_new_subtask_id)
                # self.global_state.update_task_status(TaskStatus.PENDING)
                # self.global_state.add_event(
                #     "manager",
                #     "set_current_subtask",
                #     f"current_subtask_id={first_new_subtask_id}"
                # )
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

                # If no current subtask is selected yet, set the first one
                # task = self.global_state.get_task()
                # if not task.current_subtask_id and enhanced_subtasks:
                # self.global_state.set_current_subtask_id(enhanced_subtasks[0]["subtask_id"])
                # self.global_state.update_task_status(TaskStatus.PENDING)
                # self.global_state.add_event(
                #     "manager",
                #     "set_current_subtask",
                #     f"current_subtask_id={enhanced_subtasks[0]['subtask_id']}"
                # )

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

    def _handle_supplement_scenario(self) -> PlanningResult:
        """Handle supplement collection scenario"""
        try:
            self.status = ManagerStatus.SUPPLEMENTING
            self.supplement_attempts += 1

            # Get supplement context
            context = self._get_supplement_context()
            
            # Get the current command that triggered supplement to understand why
            supplement_reason = context.get("supplement_reason")
            
            # Record the supplement reason in global state
            if supplement_reason:
                self.global_state.add_supplement_entry(
                    entry_type="Worker Supplement Request",
                    description=supplement_reason,
                    status="open"
                )
            
            # Generate supplement prompt
            prompt = self._generate_supplement_prompt(context, supplement_reason) #type: ignore
            
            # Execute supplement plan: use LLM tool if available, otherwise auto-build
            if self.supplement_agent:
                supplement_result, total_tokens, cost_string = self.supplement_agent.execute_tool(
                    self.supplement_agent_name,
                    {"str_input": prompt}
                )
                # Log supplement operation with LLM details
                self.global_state.log_llm_operation(
                    "manager",
                    "supplement_collection",
                    {
                        "attempt": self.supplement_attempts,
                        "tokens": total_tokens,
                        "cost": cost_string
                    },
                    str_input=prompt
                )
                # Parse strategy
                try:
                    strategy_data = json.loads(supplement_result)
                    strategy = SupplementStrategy(**strategy_data)
                except json.JSONDecodeError:
                    # Fallback to auto strategy if model output is not valid JSON
                    strategy = self._auto_build_supplement_strategy(context)
            else:
                # No supplement tool configured; build strategy automatically
                strategy = self._auto_build_supplement_strategy(context)

            # Execute collection strategy
            collected_data = self._execute_supplement_strategy(strategy)

            # Update supplement content
            self._update_supplement_content(collected_data)

            return PlanningResult(
                success=True,
                scenario=PlanningScenario.SUPPLEMENT.value,
                subtasks=[],
                supplement=collected_data,
                reason="Successfully collected supplement data",
                created_at=datetime.now().isoformat()
            )

        except Exception as e:
            logger.error(f"Supplement collection failed: {e}")
            return PlanningResult(
                success=False,
                scenario=PlanningScenario.SUPPLEMENT.value,
                subtasks=[],
                supplement="",
                reason=f"Supplement collection failed: {str(e)}",
                created_at=datetime.now().isoformat()
            )

    def _auto_build_supplement_strategy(self, context: Dict[str, Any]) -> SupplementStrategy:
        """Heuristic fallback to construct a reasonable supplement strategy when LLM is unavailable."""
        objective = context.get("task_objective", "").strip()
        failed_info = context.get("failed_subtasks", "")
        existing = context.get("existing_supplement", "")
        # Simple keyword extraction heuristic
        base_keywords: List[str] = []
        if objective:
            base_keywords.extend([kw for kw in objective.split() if len(kw) > 3])
        if failed_info and failed_info != "No failed subtasks":
            base_keywords.extend([kw for kw in failed_info.split() if len(kw) > 4])
        # Deduplicate and cap
        dedup = []
        for k in base_keywords:
            if k.lower() not in {x.lower() for x in dedup}:
                dedup.append(k)
        rag_keywords = dedup[:5]
        search_queries = [" ".join(rag_keywords[:3])] if rag_keywords else []
        needed_info = "Missing context to proceed effectively." if not existing else "Augment existing supplement with up-to-date references."
        return SupplementStrategy(
            needed_info=needed_info,
            collection_strategy={
                "use_rag": True,
                "rag_keywords": rag_keywords,
                "use_websearch": bool(self.search_engine is not None),
                "search_queries": search_queries,
                "priority": "rag_first" if self.search_engine is None else "parallel",
            },
            collected_data="",
        )

    def _get_planning_context(self, scenario: PlanningScenario, trigger_code: str) -> Dict[str, Any]:
        """Get context information for planning with trigger_code specific details"""
        task = self.global_state.get_task()
        subtasks = self.global_state.get_subtasks()
        screenshot = self.global_state.get_screenshot()

        is_replan_now = self.replan_attempts > 0

        context = {
            "task_objective": task.objective or "",
            "task_status": task.status or "",
            "all_subtasks": subtasks,
            # "current_subtask_id": task.current_subtask_id,
            "history_subtasks": self._get_history_subtasks_info(),
            "pending_subtasks": self._get_pending_subtasks_info(),
            "screenshot": screenshot,
            "platform": self.platform,
            "planning_scenario": "replan" if is_replan_now else "initial_plan",
            "replan_attempts": self.replan_attempts,
            "planning_history": self.planning_history[-3:] if self.planning_history else [],
            "trigger_code": trigger_code
        }

        # Add failure information only when truly re-planning
        if is_replan_now:
            context["failed_subtasks"] = self._get_failed_subtasks_info()
            context["failure_reasons"] = self._get_failure_reasons()

        # Add trigger_code specific context information
        context.update(self._get_trigger_code_specific_context(trigger_code))

        return context

    def _get_trigger_code_specific_context(self, trigger_code: str) -> Dict[str, Any]:
        """Get trigger_code specific context information"""
        context = {}
        
        if trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["work_cannot_execute"]:
            # Worker无法执行的情况
            context["trigger_context"] = {
                "type": "worker_cannot_execute",
                "description": "Worker reported that the current subtask cannot be executed",
                "focus": "Need to analyze why the subtask cannot be executed and find alternative approaches"
            }
            # 获取当前失败的subtask信息
            current_subtask = self._get_current_failed_subtask()
            if current_subtask:
                context["current_failed_subtask"] = current_subtask
                
        elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["quality_check_failed"]:
            # 质检失败的情况
            context["trigger_context"] = {
                "type": "quality_check_failed",
                "description": "Quality check failed for the current subtask",
                "focus": "Need to understand why quality check failed and improve the approach"
            }
            # 获取质检失败的具体信息
            context["quality_check_failure"] = self._get_quality_check_failure_info()
            
        elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["no_worker_decision"]:
            # Worker没有决策的情况
            context["trigger_context"] = {
                "type": "no_worker_decision",
                "description": "Worker could not make a decision for the current subtask",
                "focus": "Need to provide clearer instructions or break down the subtask"
            }
            
        elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["get_action_error"]:
            # GET_ACTION状态错误的情况
            context["trigger_context"] = {
                "type": "get_action_error",
                "description": "Error occurred during GET_ACTION state processing",
                "focus": "Need to handle the error and provide alternative approaches"
            }
            
        elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["quality_check_error"]:
            # 质检错误的情况
            context["trigger_context"] = {
                "type": "quality_check_error",
                "description": "Error occurred during quality check process",
                "focus": "Need to handle the quality check error and continue with alternative approaches"
            }
            
        elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["final_check_failed"]:
            # 最终质检失败的情况
            context["trigger_context"] = {
                "type": "final_check_failed",
                "description": "Final quality check failed for the entire task",
                "focus": "Need to address the final quality issues and complete the task"
            }
            # 获取最终质检失败的信息
            context["final_check_failure"] = self._get_final_check_failure_info()
            
        elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["rule_replan_long_execution"]:
            # 长时间执行需要重规划的情况
            context["trigger_context"] = {
                "type": "long_execution_replan",
                "description": "Task has been executing for too long, need to replan",
                "focus": "Need to optimize the execution plan and reduce execution time"
            }
            # 获取执行时间信息
            context["execution_time_info"] = self._get_execution_time_info()
            
        elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["no_subtasks"]:
            # 没有subtask的情况
            context["trigger_context"] = {
                "type": "no_subtasks",
                "description": "No subtasks available for execution",
                "focus": "Need to create initial subtasks for the task"
            }
            
        elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["init_error"]:
            # 初始化错误的情况
            context["trigger_context"] = {
                "type": "init_error",
                "description": "Error occurred during task initialization",
                "focus": "Need to handle initialization error and start fresh"
            }
            
        elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["supplement_completed"]:
            # 补充资料完成的情况
            context["trigger_context"] = {
                "type": "supplement_completed",
                "description": "Supplement collection completed, ready to replan",
                "focus": "Use the collected supplement information to improve planning"
            }
            # 获取补充资料信息
            context["supplement_info"] = self._get_supplement_info()
            
        elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["supplement_error"]:
            # 补充资料错误的情况
            context["trigger_context"] = {
                "type": "supplement_error",
                "description": "Error occurred during supplement collection",
                "focus": "Handle supplement error and continue with available information"
            }
            
        else:
            # 默认情况
            context["trigger_context"] = {
                "type": "general_replan",
                "description": f"General replanning triggered by: {trigger_code}",
                "focus": "Analyze the current situation and improve the plan"
            }
            
        return context

    def _get_current_failed_subtask(self) -> Optional[Dict[str, Any]]:
        """获取当前失败的subtask信息"""
        task = self.global_state.get_task()
        if task.current_subtask_id:
            subtask = self.global_state.get_subtask(task.current_subtask_id)
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

    def _get_quality_check_failure_info(self) -> Dict[str, Any]:
        """获取质检失败的具体信息"""
        task = self.global_state.get_task()
        if task.current_subtask_id:
            # 获取最新的质检记录
            latest_gate = self.global_state.get_latest_gate_check_for_subtask(task.current_subtask_id)
            if latest_gate:
                return {
                    "gate_check_id": latest_gate.gate_check_id,
                    "decision": latest_gate.decision,
                    "notes": latest_gate.notes,
                    "trigger": latest_gate.trigger,
                    "created_at": latest_gate.created_at
                }
        return {"error": "No quality check information available"}

    def _get_final_check_failure_info(self) -> Dict[str, Any]:
        """获取最终质检失败的信息"""
        # 获取所有质检记录
        gate_checks = self.global_state.get_gate_checks()
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

    def _get_execution_time_info(self) -> Dict[str, Any]:
        """获取执行时间信息"""
        task = self.global_state.get_task()
        return {
            "step_num": task.step_num,
            "plan_num": task.plan_num,
            "task_created_at": task.created_at,
            "current_time": datetime.now().isoformat()
        }

    def _get_supplement_info(self) -> Dict[str, Any]:
        """获取补充资料信息"""
        supplement_content = self.global_state.get_supplement()
        return {
            "supplement_content": supplement_content,
            "supplement_length": len(supplement_content) if supplement_content else 0
        }

    def _get_supplement_context(self) -> Dict[str, Any]:
        """Get context information for supplement collection"""
        task = self.global_state.get_task()
        subtasks = self.global_state.get_subtasks()
        supplement = self.global_state.get_supplement()

        # Get current subtask that needs supplement
        current_subtask = None
        supplement_reason = ""
        if task.current_subtask_id:
            current_subtask = self.global_state.get_subtask(task.current_subtask_id)
            # Get the reason for supplement collection from the current command's message field
            if current_subtask:
                current_command = self.global_state.get_current_command_for_subtask(current_subtask.subtask_id)
                if current_command:
                    # Check if the command has a message field that explains why supplement is needed
                    if hasattr(current_command, 'message') and current_command.message:
                        supplement_reason = current_command.message
                    # Fallback to action type if message is not available
                    elif hasattr(current_command, 'action') and current_command.action:
                        action_type = current_command.action.get('type', '')
                        if action_type == 'Supplement':
                            supplement_reason = current_command.action.get('message', 'Worker requested supplement')
                else:
                    supplement_reason = ""
        
        return {
            "task_objective": task.objective or "",
            "current_subtask": current_subtask,
            "all_subtasks": subtasks,
            "existing_supplement": supplement,
            "supplement_attempts": self.supplement_attempts,
            "supplement_reason": supplement_reason
        }

    def _generate_planning_prompt(self, scenario: PlanningScenario, context: Dict[str, Any], integrated_knowledge: str = "", trigger_code: str = "controller") -> str:
        """Generate planning prompt based on scenario, context and trigger_code"""

        # Determine scenario from context to ensure auto mode works
        planning_scenario: str = context.get("planning_scenario", "initial_plan")
        history_subtasks: str = context.get("history_subtasks", "")
        pending_subtasks: str = context.get("pending_subtasks", "")
        is_replan: bool = planning_scenario == "replan"
        trigger_context = context.get("trigger_context", {})
        # Generate trigger_code specific planning guidance
        trigger_specific_guidance = self._generate_trigger_specific_guidance(trigger_code, trigger_context, context)

        # Scenario-specific planning task section
        if is_replan:
            planning_task = f"""
# Current Planning Task
You need to RE-PLAN the task based on prior attempts and failures.

# Planning Focus (Re-plan)
- Analyze why previous attempts failed and identify bottlenecks
- Preserve valid progress; DO NOT duplicate completed subtasks
- Adjust ordering, refine steps, or replace failing subtasks
- Ensure dependencies remain valid and achievable

{trigger_specific_guidance}
"""
            decision = """
# Planning Decision (Re-plan)
- Prioritize resolving blockers and mitigating risks found previously
- Introduce new/modified subtasks only where necessary
- Keep completed subtasks out of the list; reference them only in dependencies
"""
        else:
            planning_task = f"""
# Current Planning Task
You need to perform INITIAL PLANNING to decompose the objective into executable subtasks.

# Planning Focus (Initial)
- Cover the full path from start to completion
- Define clear, verifiable completion criteria for each subtask
- Keep reasonable granularity; avoid overly fine steps unless needed for reliability

{trigger_specific_guidance}
"""
            decision = """
# Planning Decision (Initial)
- Decompose the user objective into an ordered set of executable subtasks
- Make dependencies explicit and minimize unnecessary coupling
- Assign appropriate worker roles to each subtask
"""

        # Common guidance and output schema
        common_guidance = f"""
# Decomposition Principles
1. Each subtask should have clear objectives and completion criteria
2. Dependencies between subtasks should be clear
3. Assign appropriate Worker type for each subtask
4. Consider execution risks and exceptional cases


# Task Information
Objective: {context.get('task_objective', '')}
Planning Scenario: {planning_scenario}
Trigger Code: {trigger_code}
Current Progress: {self._count_subtasks_from_info(context.get('history_subtasks', ''))} subtask completed, {self._count_subtasks_from_info(context.get('pending_subtasks', ''))} subtask pending
History Subtasks: {history_subtasks}
Pending Subtasks: {pending_subtasks}
Platform: {context.get('platform', '')}
"""

        # Replan-specific extra diagnostic information
        replan_info = ""
        if is_replan:
            replan_info = f"""
# Re-planning Information
Re-planning Attempts: {context.get('replan_attempts', 0)}
Failed Subtasks: {context.get('failed_subtasks', '')}
Failure Reasons: {context.get('failure_reasons', '')}

# Re-plan Output Constraints
- Only include new subtasks in the JSON list
- Do not include already completed subtasks
- Keep or update dependencies to reference existing subtask IDs when applicable
"""

        # Environment information
        env_info = f"""
# Current Environment Information
Screenshot Available: {'Yes' if context.get('screenshot') else 'No'}

# Retrieved/Integrated Knowledge
You may refer to some retrieved knowledge if you think they are useful.{integrated_knowledge if integrated_knowledge else 'N/A'}

Please output the planning solution based on the above information:
"""

        planning_prompt = f"""
{planning_task}
{decision}
{common_guidance}
{replan_info}
{env_info}
"""

        return planning_prompt

    def _generate_trigger_specific_guidance(self, trigger_code: str, trigger_context: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate trigger_code specific planning guidance"""
        
        if trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["work_cannot_execute"]:
            return """
# Worker Cannot Execute - Specific Guidance
- The Worker reported that the current subtask cannot be executed
- Analyze the specific reason for failure and find alternative approaches
- Consider breaking down the subtask into smaller, more manageable steps
- Look for alternative methods or tools to achieve the same goal
- Ensure the new plan addresses the specific execution barriers identified
"""
            
        elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["quality_check_failed"]:
            quality_info = context.get("quality_check_failure", {})
            return f"""
# Quality Check Failed - Specific Guidance
- The quality check failed for the current subtask
- Review the quality check notes: {quality_info.get('notes', 'No notes available')}
- Identify what specific quality criteria were not met
- Improve the approach to meet the quality standards
- Consider adding intermediate verification steps
- Ensure the new plan includes better quality control measures
"""
            
        elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["no_worker_decision"]:
            return """
# No Worker Decision - Specific Guidance
- Worker could not make a decision for the current subtask
- Provide clearer, more specific instructions
- Break down the subtask into smaller, more obvious steps
- Add more context or examples to guide the worker
- Consider using a different worker role that might be better suited
- Ensure the new plan has clear decision criteria and fallback options
"""
            
        elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["get_action_error"]:
            return """
# GET_ACTION Error - Specific Guidance
- Error occurred during GET_ACTION state processing
- Handle the error gracefully and provide alternative approaches
- Consider simplifying the action generation process
- Add error handling and recovery mechanisms
- Ensure the new plan is more robust and error-resistant
"""
            
        elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["quality_check_error"]:
            return """
# Quality Check Error - Specific Guidance
- Error occurred during quality check process
- Handle the quality check error and continue with alternative approaches
- Consider using simpler quality criteria
- Add fallback quality assessment methods
- Ensure the new plan includes error handling for quality checks
"""
            
        elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["final_check_failed"]:
            final_info = context.get("final_check_failure", {})
            return f"""
# Final Check Failed - Specific Guidance
- Final quality check failed for the entire task
- Total gate checks: {final_info.get('total_gate_checks', 0)}
- Failed gate checks: {final_info.get('failed_gate_checks', 0)}
- Address the final quality issues and complete the task
- Review all completed subtasks for completeness
- Add missing steps or verification procedures
- Ensure the new plan addresses the root causes of final check failure
"""
            
        elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["rule_replan_long_execution"]:
            exec_info = context.get("execution_time_info", {})
            return f"""
# Long Execution Replan - Specific Guidance
- Task has been executing for too long, need to replan
- Current step number: {exec_info.get('step_num', 0)}
- Current plan number: {exec_info.get('plan_num', 0)}
- Optimize the execution plan and reduce execution time
- Consider parallel execution where possible
- Simplify complex subtasks into more efficient steps
- Add timeouts and progress monitoring
- Ensure the new plan is more time-efficient
"""
            
        elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["no_subtasks"]:
            return """
# No Subtasks - Specific Guidance
- No subtasks available for execution
- Create initial subtasks for the task
- Break down the main objective into logical steps
- Ensure all necessary steps are covered
- Consider dependencies and execution order
- Assign appropriate worker roles to each subtask
"""
            
        elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["init_error"]:
            return """
# Init Error - Specific Guidance
- Error occurred during task initialization
- Handle initialization error and start fresh
- Simplify the initial setup process
- Add error recovery mechanisms
- Ensure the new plan has better initialization procedures
"""
            
        elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["supplement_completed"]:
            supplement_info = context.get("supplement_info", {})
            return f"""
# Supplement Completed - Specific Guidance
- Supplement collection completed, ready to replan
- Supplement content length: {supplement_info.get('supplement_length', 0)} characters
- Use the collected supplement information to improve planning
- Incorporate the new information into the task plan
- Update subtasks based on the additional context
- Ensure the new plan leverages all available information
"""
            
        elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["supplement_error"]:
            return """
# Supplement Error - Specific Guidance
- Error occurred during supplement collection
- Handle supplement error and continue with available information
- Work with the information that is already available
- Consider alternative information sources
- Ensure the new plan can work with limited information
"""
            
        else:
            return f"""
# General Replanning - Specific Guidance
- General replanning triggered by: {trigger_code}
- Analyze the current situation and improve the plan
- Consider all available context and information
- Address any identified issues or bottlenecks
- Ensure the new plan is more robust and effective
"""

    def _generate_dag(self, instruction: str, plan: str) -> Tuple[Dict, Dag]:
        """Generate a DAG from instruction and plan using dag_translator, with retries and fallback."""
        max_retries = 3
        retry = 0
        dag_obj: Optional[Dag] = None
        dag_raw = ""
        total_tokens = 0
        cost_string = ""
        dag_input = f"Instruction: {instruction}\nPlan: {plan}"

        while retry < max_retries and dag_obj is None:
            # if retry > 0:
            #     self.global_state.add_event("manager", "dag_retry", f"retry={retry}")
            dag_raw, total_tokens, cost_string = self.dag_translator_agent.execute_tool(
                self.dag_translator_agent_name, {"str_input": dag_input}
            )
            dag_obj = parse_dag(dag_raw)
            retry += 1 if dag_obj is None else 0

        self.global_state.log_llm_operation(
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
            self.global_state.add_event("manager", "default_dag_created", "fallback simple DAG used")

        return {"dag": dag_raw}, dag_obj

    def _topological_sort(self, dag: Dag) -> List[Node]:
        """Topological sort of the DAG using DFS; returns node list on error."""
        if not getattr(dag, 'nodes', None):
            return []
        if len(dag.nodes) == 1:
            return dag.nodes

        from collections import defaultdict

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

    def _generate_supplement_prompt(self, context: Dict[str, Any], supplement_reason: str = "") -> str:
        """Generate supplement collection prompt"""

        system_info = """
# System Architecture
You are the Manager (task planner) in the GUI-Agent system. The system includes:
- Controller: Central scheduling and process control
- Manager: Task planning and resource allocation (your role)
- Worker: Execute specific operations (Operator/Analyst/Technician)
- Evaluator: Quality inspection
- Hardware: Low-level execution

# Current Planning Task
During execution, necessary information was found to be missing. You need to collect supplementary materials.

# Collection Tools
- RAG Retrieval: Retrieve relevant documents and materials from knowledge base
- Web Search: Search for latest information from the internet
- Combined Use: RAG retrieval first, then web search supplementation

# Collection Strategy
1. Clearly identify the type and importance of required information
2. Choose appropriate retrieval keywords and search strategies
3. Verify and organize collected information
4. Update supplement.md file

# Output Format
You must output the following JSON format:
{
  "needed_info": "Detailed description of required information",
  "collection_strategy": {
    "use_rag": true/false,
    "rag_keywords": ["keyword1", "keyword2"],
    "use_websearch": true/false,
    "search_queries": ["search query1", "search query2"],
    "priority": "rag_first|websearch_first|parallel"
  },
  "collected_data": "Collected information content (fill in after collection execution)"
}
"""

        supplement_prompt = f"""
{system_info}

# Missing Information Situation
Task Objective: {context.get('task_objective', '')}
Current Subtask: {context.get('current_subtask', {})}
Existing Supplement: {context.get('existing_supplement', '')}
Supplement Attempts: {context.get('supplement_attempts', 0)}
Failed Subtasks: {context.get('failed_subtasks', '')}
Supplement Reason: {supplement_reason}

Please output the supplementary material collection solution and execute it based on the above information:
"""

        return supplement_prompt

    def _enhance_subtasks(self, subtasks: List[Node]) -> List[Dict]:
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
                "task_id": self.global_state.task_id,
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

    def _execute_supplement_strategy(self, strategy: SupplementStrategy) -> str:
        """Execute supplement collection strategy"""
        collected_data = []

        # Execute RAG retrieval if enabled
        if strategy.collection_strategy.get("use_rag", False):
            rag_keywords = strategy.collection_strategy.get("rag_keywords", [])
            for keyword in rag_keywords:
                try:
                    # Use knowledge base to retrieve relevant information (most_similar_task, retrieved_experience, tokens, cost)
                    _, retrieved_experience, _, _ = self.knowledge_base.retrieve_narrative_experience(keyword)  # type: ignore
                    if retrieved_experience:
                        collected_data.append(f"RAG Result for '{keyword}': {retrieved_experience}")
                except Exception as e:
                    logger.warning(f"RAG retrieval failed for keyword '{keyword}': {e}")

        # Execute web search if enabled
        if strategy.collection_strategy.get("use_websearch", False) and self.search_engine:
            search_queries = strategy.collection_strategy.get("search_queries", [])
            for query in search_queries:
                try:
                    search_result, _, _ = self.search_engine.execute_tool("websearch", {"query": query})
                    if search_result:
                        collected_data.append(f"Web Search Result for '{query}': {search_result}")
                except Exception as e:
                    logger.warning(f"Web search failed for query '{query}': {e}")

        # Combine collected data
        combined_data = "\n\n".join(collected_data) if collected_data else "No data collected"

        # Update strategy with collected data
        strategy.collected_data = combined_data

        return combined_data

    def _update_supplement_content(self, collected_data: str):
        """Update supplement content in global state"""
        current_supplement = self.global_state.get_supplement()

        # Add new supplement entry
        entry_id = f"supplement-{int(time.time() * 1000)}"
        timestamp = datetime.now().isoformat()

        new_entry = f"""
## Supplement Entry - {entry_id}
- **Created**: {timestamp}
- **Type**: Collected Information
- **Content**: {collected_data}
- **Status**: Collected

---
"""

        updated_content = current_supplement + new_entry
        self.global_state.set_supplement(updated_content)

    def _get_failed_subtasks_info(self) -> str:
        """Get information about failed subtasks"""
        failed_subtasks = []
        all_subtasks = self.global_state.get_subtasks()

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

    def _get_failure_reasons(self) -> str:
        """Get failure reasons from subtask history"""
        failure_reasons = []
        all_subtasks = self.global_state.get_subtasks()

        for subtask in all_subtasks:
            if subtask.status == SubtaskStatus.REJECTED.value:
                reasons = subtask.reasons_history or []
                if reasons:
                    failure_reasons.extend([r.get("text", "") for r in reasons])

        return "; ".join(failure_reasons) if failure_reasons else "No specific failure reasons"

    def _get_history_subtasks_info(self) -> str:
        """Get information about completed subtasks"""
        history_subtasks = []
        task = self.global_state.get_task()
        all_subtasks = self.global_state.get_subtasks()

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

    def _get_pending_subtasks_info(self) -> str:
        """Get information about pending subtasks"""
        pending_subtasks = []
        task = self.global_state.get_task()
        all_subtasks = self.global_state.get_subtasks()

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

    def _count_subtasks_from_info(self, subtasks_info: str) -> int:
        """Count subtasks from the JSON string info returned by _get_*_subtasks_info methods"""
        if not subtasks_info or subtasks_info in ["No completed subtasks", "No pending subtasks"]:
            return 0
        try:
            subtasks_list = json.loads(subtasks_info)
            return len(subtasks_list) if isinstance(subtasks_list, list) else 0
        except (json.JSONDecodeError, TypeError):
            return 0

    def get_planning_status(self) -> Dict[str, Any]:
        """Get current planning status"""
        return {
            "status": self.status.value,
            "replan_attempts": self.replan_attempts,
            "supplement_attempts": self.supplement_attempts,
            "planning_history_count": len(self.planning_history),
            "max_replan_attempts": self.max_replan_attempts,
        }

    def reset_planning_state(self):
        """Reset planning state (useful for new tasks)"""
        self.replan_attempts = 0
        self.supplement_attempts = 0
        self.planning_history = []
        self.status = ManagerStatus.IDLE

        self.global_state.add_event("manager", "planning_reset", "Planning state reset")

    def can_replan(self) -> bool:
        """Check if replanning is still allowed"""
        return self.replan_attempts < self.max_replan_attempts

    def _get_current_trigger_code(self) -> str:
        """获取当前的 trigger_code"""
        controller_state = self.global_state.get_controller_state()
        return controller_state.get("trigger_code", "")

# Export a friendly alias to match the interface name used elsewhere
Manager = NewManager
