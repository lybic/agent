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

from gui_agents.utils.common_utils import Node
from gui_agents.tools.tools import Tools
from gui_agents.core.knowledge import KnowledgeBase

from .new_global_state import NewGlobalState
from .data_models import SubtaskData  # Add import for SubtaskData
from .enums import (
    TaskStatus, SubtaskStatus, GateDecision, GateTrigger,
    ControllerState, ExecStatus, ManagerStatus
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
        platform: str = "unknown",
        enable_search: bool = False,
        max_replan_attempts: int = 3,
        max_supplement_attempts: int = 2
    ):
        """
        Initialize the Manager module
        
        Args:
            tools_dict: Dictionary containing tool configurations
            global_state: Global state instance
            local_kb_path: Path to local knowledge base
            platform: Target platform (windows/mac/linux)
            enable_search: Whether to enable web search
            max_replan_attempts: Maximum replanning attempts
            max_supplement_attempts: Maximum supplement collection attempts
        """
        self.tools_dict = tools_dict
        self.global_state = global_state
        self.local_kb_path = local_kb_path
        self.platform = platform
        self.enable_search = enable_search
        self.max_replan_attempts = max_replan_attempts
        self.max_supplement_attempts = max_supplement_attempts
        
        # Initialize status
        self.status = ManagerStatus.IDLE
        self.plan_scenario = PlanningScenario.REPLAN
        self.planning_history = []
        self.replan_attempts = 0
        self.supplement_attempts = 0
        
        # Initialize tools
        self._initialize_tools()
        
        # Initialize knowledge base
        self._initialize_knowledge_base()
        
        logger.info("NewManager initialized successfully")

    def _initialize_tools(self):
        """Initialize required tools with backward-compatible keys"""
        # Planner tool: prefer "subtask_planner" (legacy) then "task_planner"
        planner_cfg = self.tools_dict.get("subtask_planner") or self.tools_dict.get("task_planner")
        if not planner_cfg:
            raise KeyError("Missing tool config for 'subtask_planner' or 'task_planner'")
        self.planner_agent = Tools()
        self.planner_agent.register_tool(
            "subtask_planner",
            planner_cfg["provider"],
            planner_cfg["model"],
        )
        
        # Supplement LLM tool is optional; if missing we will auto-build a strategy
        supp_cfg = (
            self.tools_dict.get("supplement_collector")
            or self.tools_dict.get("narrative_summarization")
            or self.tools_dict.get("context_fusion")
        )
        self.supplement_agent: Optional[Tools] = None
        self.supplement_tool_name: Optional[str] = None
        if supp_cfg:
            self.supplement_agent = Tools()
            # Use declared key name for invocation clarity
            if "supplement_collector" in self.tools_dict:
                self.supplement_tool_name = "supplement_collector"
            elif "narrative_summarization" in self.tools_dict:
                self.supplement_tool_name = "narrative_summarization"
            else:
                self.supplement_tool_name = "context_fusion"
            self.supplement_agent.register_tool(
                self.supplement_tool_name,
                supp_cfg["provider"],
                supp_cfg["model"],
            )
        
        # Embedding engine for RAG
        self.embedding_engine = Tools()
        self.embedding_engine.register_tool(
            "embedding",
            self.tools_dict["embedding"]["provider"],
            self.tools_dict["embedding"]["model"],
        )
        
        # Web search engine (optional)
        if self.enable_search and self.tools_dict.get("websearch"):
            self.search_engine = Tools()
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
            "embedding": self.tools_dict["embedding"],
            "query_formulator": self.tools_dict.get("query_formulator", {}),
            "context_fusion": self.tools_dict.get("context_fusion", {}),
        }
        
        self.knowledge_base = KnowledgeBase(
            embedding_engine=self.embedding_engine,
            local_kb_path=self.local_kb_path,
            platform=self.platform,
            Tools_dict=kb_tools_dict,
        )

    def plan_task(self, scenario: Union[PlanningScenario, str]) -> PlanningResult:
        """
        Execute task planning based on scenario
        
        Args:
            scenario: Planning scenario (INITIAL_PLAN|REPLAN|SUPPLEMENT or enum)
            
        Returns:
            PlanningResult: Planning result with subtasks or supplement
        """
        try:
            scenario_enum = self._normalize_scenario(scenario)
            self.status = ManagerStatus.PLANNING
            # self.global_state.add_event("manager", "planning_start", f"Scenario: {scenario_enum.value}")
            
            if scenario_enum == PlanningScenario.SUPPLEMENT:
                return self._handle_supplement_scenario()
            else:
                return self._handle_planning_scenario(scenario_enum)
                
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            self.status = ManagerStatus.ERROR
            self.global_state.add_event("manager", "planning_error", str(e))
            
            return PlanningResult(
                success=False,
                scenario=self._normalize_scenario(scenario).value if isinstance(scenario, str) else scenario.value,
                subtasks=[],
                supplement="",
                reason=f"Planning failed: {str(e)}",
                created_at=datetime.now().isoformat()
            )
        finally:
            self.status = ManagerStatus.IDLE

    def _normalize_scenario(self, scenario: Union[PlanningScenario, str]) -> PlanningScenario:
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

    def _handle_planning_scenario(self, scenario: PlanningScenario) -> PlanningResult:
        """Handle planning scenarios (INITIAL_PLAN/REPLAN)"""
        # Get planning context
        context = self._get_planning_context(scenario)
        
        # Generate planning prompt
        prompt = self._generate_planning_prompt(scenario, context)
        
        # Execute planning using the registered planner tool
        plan_result, total_tokens, cost_string = self.planner_agent.execute_tool(
            "subtask_planner",
            {"str_input": prompt, "img_input": context.get("screenshot")}
        )
        
        # Log planning operation
        self.global_state.add_event(
            "manager", 
            "task_planning", 
            f"Scenario: {scenario.value}, Tokens: {total_tokens}, Cost: {cost_string}"
        )
        
        # Parse planning result
        try:
            parsed = json.loads(plan_result)
            # Accept either a list of subtasks or an object with a "subtasks" field
            if isinstance(parsed, list):
                subtasks = parsed
            else:
                subtasks = parsed.get("subtasks", [])
            
            # Validate and enhance subtasks
            enhanced_subtasks = self._enhance_subtasks(subtasks, context)
            
            # Store subtasks in global state
            for subtask_dict in enhanced_subtasks:
                # Convert dict to SubtaskData object
                subtask_data = SubtaskData(
                    subtask_id=subtask_dict["subtask_id"],
                    task_id=subtask_dict["task_id"],
                    title=subtask_dict["title"],
                    description=subtask_dict["description"],
                    assignee_role=subtask_dict["assignee_role"],
                    attempt_no=subtask_dict["attempt_no"],
                    status=subtask_dict["status"],
                    reasons_history=subtask_dict["reasons_history"],
                    command_trace_ids=subtask_dict["command_trace_ids"],
                    gate_check_ids=subtask_dict["gate_check_ids"],
                    created_at=subtask_dict["created_at"]
                )
                self.global_state.add_subtask(subtask_data)
            
            # If no current subtask is selected yet, set the first one
            task = self.global_state.get_task()
            if not task.current_subtask_id and enhanced_subtasks:
                self.global_state.set_current_subtask_id(enhanced_subtasks[0]["subtask_id"])
                self.global_state.update_task_status(TaskStatus.PENDING)
                self.global_state.add_event(
                    "manager",
                    "set_current_subtask",
                    f"current_subtask_id={enhanced_subtasks[0]['subtask_id']}"
                )
            
            # Update planning history
            self.planning_history.append({
                "scenario": scenario.value,
                "subtasks": enhanced_subtasks,
                "timestamp": datetime.now().isoformat(),
                "tokens": total_tokens,
                "cost": cost_string
            })
            
            if scenario == PlanningScenario.REPLAN:
                self.replan_attempts += 1
            
            return PlanningResult(
                success=True,
                scenario=scenario.value,
                subtasks=enhanced_subtasks,
                supplement="",
                reason=f"Successfully planned {len(enhanced_subtasks)} subtasks",
                created_at=datetime.now().isoformat()
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse planning result: {e}")
            return PlanningResult(
                success=False,
                scenario=scenario.value,
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
            
            # Generate supplement prompt
            prompt = self._generate_supplement_prompt(context)
            
            # Execute supplement plan: use LLM tool if available, otherwise auto-build
            if self.supplement_agent and self.supplement_tool_name:
                supplement_result, total_tokens, cost_string = self.supplement_agent.execute_tool(
                    self.supplement_tool_name,
                    {"str_input": prompt}
                )
                # Log supplement operation
                self.global_state.add_event(
                    "manager",
                    "supplement_collection",
                    f"Attempt: {self.supplement_attempts}, Tokens: {total_tokens}, Cost: {cost_string}"
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

    def _get_planning_context(self, scenario: PlanningScenario) -> Dict[str, Any]:
        """Get context information for planning"""
        task = self.global_state.get_task()
        subtasks = self.global_state.get_subtasks()
        screenshot = self.global_state.get_screenshot()
        artifacts = self.global_state.get_artifacts()
        
        context = {
            "task_objective": task.objective or "",
            "task_status": task.status or "",
            "current_subtask_id": task.current_subtask_id,
            "completed_subtask_ids": task.completed_subtask_ids or [],
            "pending_subtask_ids": task.pending_subtask_ids or [],
            "all_subtasks": subtasks,
            "screenshot": screenshot,
            "artifacts": artifacts,
            "platform": self.platform,
            "planning_scenario": scenario.value,
            "replan_attempts": self.replan_attempts,
            "planning_history": self.planning_history[-3:] if self.planning_history else []
        }
        
        # Add failure information for replanning
        if scenario == PlanningScenario.REPLAN:
            context["failed_subtasks"] = self._get_failed_subtasks_info()
            context["failure_reasons"] = self._get_failure_reasons()
        
        return context

    def _get_supplement_context(self) -> Dict[str, Any]:
        """Get context information for supplement collection"""
        task = self.global_state.get_task()
        subtasks = self.global_state.get_subtasks()
        supplement = self.global_state.get_supplement()
        
        # Get current subtask that needs supplement
        current_subtask = None
        if task.current_subtask_id:
            current_subtask = self.global_state.get_subtask(task.current_subtask_id)
        
        return {
            "task_objective": task.objective or "",
            "current_subtask": current_subtask,
            "all_subtasks": subtasks,
            "existing_supplement": supplement,
            "supplement_attempts": self.supplement_attempts,
            "failed_subtasks": self._get_failed_subtasks_info()
        }

    def _generate_planning_prompt(self, scenario: PlanningScenario, context: Dict[str, Any]) -> str:
        """Generate planning prompt based on scenario and context"""
        
        # Base system information
        system_info = """
# System Architecture
You are the Manager (task planner) in the GUI-Agent system. The system includes:
- Controller: Central scheduling and process control
- Manager: Task planning and resource allocation (your role)
- Worker: Execute specific operations (Operator/Analyst/Technician)
- Evaluator: Quality inspection
- Hardware: Low-level execution

# Your Responsibilities
As Manager, you are responsible for decomposing user tasks into executable subtasks and re-planning when needed.

# Worker Capabilities
- Operator: Execute GUI interface operations like clicking, form filling, drag and drop
- Analyst: Analyze screen content, provide analytical support and recommendations
- Technician: Use system terminal to execute command line operations
"""
        
        # Planning prompt template
        planning_prompt = f"""
{system_info}

# Current Planning Task
You need to plan or re-plan the task.

# Planning Decision
First determine if this is initial planning or re-planning:
- If initial planning: Decompose user objectives into executable subtasks
- If re-planning: Analyze failure reasons, adjust strategy, preserve valid progress

# Decomposition Principles
1. Each subtask should have clear objectives and completion criteria
2. Dependencies between subtasks should be clear
3. Assign appropriate Worker type for each subtask
4. Consider execution risks and exceptional cases

# Output Format
You must output a JSON format subtask list:
[
  {{
    "title": "Brief title",
    "description": "Detailed description including specific steps and expected results",
    "assignee_role": "operator|analyst|technician",
    "depends_on": ["subtask_id1", "subtask_id2"] // Dependent subtask IDs, can be empty
  }}
]

# Task Information
Objective: {context.get('task_objective', '')}
Planning Scenario: {context.get('planning_scenario', '')}
Current Progress: {len(context.get('completed_subtasks', []))} completed, {len(context.get('pending_subtasks', []))} pending
Platform: {context.get('platform', '')}
"""
        
        # Add failure information for replanning
        if scenario == PlanningScenario.REPLAN:
            planning_prompt += f"""
# Re-planning Information
Re-planning Attempts: {context.get('replan_attempts', 0)}
Failed Subtasks: {context.get('failed_subtasks', '')}
Failure Reasons: {context.get('failure_reasons', '')}
"""
        
        planning_prompt += f"""
# Current Environment Information
Screenshot Available: {'Yes' if context.get('screenshot') else 'No'}
Artifacts: {context.get('artifacts', '')[:200]}...

Please output the planning solution based on the above information:
"""
        
        return planning_prompt

    def _generate_supplement_prompt(self, context: Dict[str, Any]) -> str:
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

Please output the supplementary material collection solution and execute it based on the above information:
"""
        
        return supplement_prompt

    def _enhance_subtasks(self, subtasks: List[Dict], context: Dict[str, Any]) -> List[Dict]:
        """Enhance subtasks with additional metadata"""
        enhanced_subtasks = []
        
        for i, subtask in enumerate(subtasks):
            enhanced_subtask = {
                "subtask_id": f"subtask-{int(time.time() * 1000) + i}",
                "title": subtask.get("title", f"Subtask {i+1}"),
                "description": subtask.get("description", ""),
                "assignee_role": subtask.get("assignee_role", "operator"),
                "depends_on": subtask.get("depends_on", []),
                "status": SubtaskStatus.READY.value,
                "attempt_no": 1,
                "created_at": datetime.now().isoformat(),
                "task_id": self.global_state.task_id,
                "reasons_history": [],
                "command_trace_ids": [],
                "gate_check_ids": []
            }
            
            # Validate assignee role
            if enhanced_subtask["assignee_role"] not in ["operator", "analyst", "technician"]:
                enhanced_subtask["assignee_role"] = "operator"
            
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
                    "reason": subtask.last_reason_text or "Unknown reason"
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

    def get_planning_status(self) -> Dict[str, Any]:
        """Get current planning status"""
        return {
            "status": self.status.value,
            "replan_attempts": self.replan_attempts,
            "supplement_attempts": self.supplement_attempts,
            "planning_history_count": len(self.planning_history),
            "max_replan_attempts": self.max_replan_attempts,
            "max_supplement_attempts": self.max_supplement_attempts
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

    def can_supplement(self) -> bool:
        """Check if supplement collection is still allowed"""
        return self.supplement_attempts < self.max_supplement_attempts 

# Export a friendly alias to match the interface name used elsewhere
Manager = NewManager 