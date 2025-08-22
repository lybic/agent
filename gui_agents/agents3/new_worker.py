"""
New Worker Module for GUI-Agent Architecture (agents3)
- Provides an Operator role that integrates action planning (LLM) and visual grounding
- Produces Action dicts compatible with agents3 `Action.py` and `hardware_interface.py`
- Uses `NewGlobalState` for observations and event logging

This implementation merges the essential behaviors of the legacy `worker.py` and `grounding.py` into a
single, concise Operator that is easy to invoke from the Controller.
"""

from __future__ import annotations

import re
import time
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
from desktop_env.desktop_env import DesktopEnv

# from gui_agents.tools.tools import Tools
from gui_agents.tools.new_tools import NewTools
from gui_agents.utils.common_utils import (
    parse_single_code_from_string,
    sanitize_code,
    extract_first_agent_function,
)
from gui_agents.agents3.grounding import Grounding
from gui_agents.agents3.data_models import create_command_data

from .new_global_state import NewGlobalState
from .enums import (
    ControllerState,
    ExecStatus,
    GateTrigger,
    WorkerDecision,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper data structures
# ---------------------------------------------------------------------------
@dataclass
class StepResult:
    """Lightweight step result for controller/evaluator handoff."""
    step_id: str
    ok: bool
    error: Optional[str]
    latency_ms: int
    outcome: str
    action: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Technician – executes terminal commands and scripts
# ---------------------------------------------------------------------------
class Technician:
    """Technician role: execute system-level operations via terminal commands.

    Responsibilities:
    - Generate bash/python scripts to complete system tasks
    - Execute scripts via environment controller
    - Return execution results and status

    Tools_dict requirements:
    - coding_agent: {"provider": str, "model": str} - LLM for code generation
    """

    def __init__(
        self,
        *,
        tools_dict: Dict[str, Any],
        global_state: NewGlobalState,
        platform: str = "unknown",
        env_controller: DesktopEnv,
        client_password: str = "",
        # max_execution_time: int = 300,
    ) -> None:
        self.tools_dict = tools_dict
        self.global_state = global_state
        self.platform = platform
        # self.env_controller = env_controller.controller
        if env_controller:
            self.env_controller = env_controller.controller
        else:
            self.env_controller = None
        self.client_password = client_password
        # self.max_execution_time = max_execution_time

        # LLM for code generation
        self.technician_agent_name = "technician_role"
        self.technician_agent = NewTools()
        self.technician_agent.register_tool(
            self.technician_agent_name,
            self.tools_dict[self.technician_agent_name]["provider"],
            self.tools_dict[self.technician_agent_name]["model"],
        )

    def execute_task(
        self,
        *,
        subtask: Dict[str, Any],
        guidance: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a system-level task using terminal commands.

        Returns a dict containing:
        - plan: generated code/script
        - execution_result: output from script execution
        - step_result: StepResult as dict
        - outcome: one of {"worker_done", "worker_fail", "worker_supplement", "worker_stale_progress", "worker_generate_action", "worker_fail"}
        - action: when outcome is worker_generate_action, a list of (lang, code) blocks
        """
        if not self.env_controller:
            msg = "No environment controller available for Technician"
            logger.warning(msg)
            self.global_state.add_event("technician", "no_controller", msg)
            result = StepResult(
                step_id=f"{subtask.get('subtask_id','unknown')}.tech-0",
                ok=False,
                error=msg,
                latency_ms=0,
                outcome=WorkerDecision.CANNOT_EXECUTE.value,
            )
            return {
                "plan": "",
                "execution_result": "",
                "step_result": result.__dict__,
                "outcome": WorkerDecision.CANNOT_EXECUTE.value,
                "action": None,
            }

        # Build coding prompt
        subtask_title = subtask.get("title", "")
        subtask_desc = subtask.get("description", "")
        
        system_message = []
        system_message.append(f"# Your linux username is \"user\"")
        system_message.append(f"# Your client password is: {self.client_password}")
        system_message.append(f"# Platform: {self.platform}")
        
        task_prompt = []
        task_prompt.append(f"# Task: {subtask_title}")
        task_prompt.append(f"# Description: {subtask_desc}")
        if guidance:
            task_prompt.append(f"# Guidance: {guidance}")
        task_prompt.append(f"# Platform: {self.platform}")
        task_prompt.append("\nGenerate the appropriate bash or python code to complete this task.")
        task_prompt.append("Wrap your code in ```bash or ```python code blocks.")
        task_prompt.append("If the task is already done, or cannot proceed, or needs info/QA, output a Decision section like 'Decision: Done' | 'Decision: Failed' | 'Decision: Supplement' | 'Decision: NeedQualityCheck'. If you provide code, that's treated as generate_action.")
        
        full_prompt = "\n".join(system_message) + "\n" + "\n".join(task_prompt)

        # Get screenshot for context
        screenshot_bytes = self.global_state.get_screenshot()

        # Call coding agent
        t0 = time.time()
        try:
            command_plan, total_tokens, cost_string = self.technician_agent.execute_tool(
                self.technician_agent_name,
                {"str_input": full_prompt, "img_input": screenshot_bytes},
            )
            latency_ms = int((time.time() - t0) * 1000)
            
            self.global_state.add_event(
                "technician",
                "code_generated",
                f"tokens={total_tokens}, cost={cost_string}",
            )
        except Exception as e:
            err = f"CODE_GENERATION_FAILED: {e}"
            logger.warning(err)
            self.global_state.add_event("technician", "code_generation_failed", err)
            result = StepResult(
                step_id=f"{subtask.get('subtask_id','unknown')}.tech-1",
                ok=False,
                error=err,
                latency_ms=int((time.time() - t0) * 1000),
                outcome=WorkerDecision.CANNOT_EXECUTE.value,
            )
            return {
                "plan": "",
                "execution_result": "",
                "step_result": result.__dict__,
                "outcome": WorkerDecision.CANNOT_EXECUTE.value,
                "action": None,
            }

        # Extract and classify
        try:
            decision = self._infer_decision_from_text(command_plan)
            code_blocks: List[Tuple[str, str]] = []

            # Only try to extract code blocks when no explicit decision is detected
            if decision is None:
                code_blocks = self._extract_code_blocks(command_plan)

            if decision is None and code_blocks:
                ok = True
                outcome = WorkerDecision.GENERATE_ACTION.value
                err = None
            elif decision == "done":
                ok = True
                outcome = WorkerDecision.WORKER_DONE.value
                err = None
            elif decision == "failed":
                ok = False
                outcome = WorkerDecision.CANNOT_EXECUTE.value
                err = None
            elif decision == "supplement":
                ok = False
                outcome = WorkerDecision.SUPPLEMENT.value
                err = None
            elif decision == "need_quality_check":
                ok = True
                outcome = WorkerDecision.STALE_PROGRESS.value
                err = None
            else:
                # No clear signal; treat as cannot execute
                ok = False
                outcome = WorkerDecision.CANNOT_EXECUTE.value
                err = "No code blocks or valid decision found"
        except Exception as e:
            ok = False
            outcome = WorkerDecision.CANNOT_EXECUTE.value
            code_blocks = []
            err = f"CLASSIFICATION_FAILED: {e}"
            logger.warning(err)
        
        result = StepResult(
            step_id=f"{subtask.get('subtask_id','unknown')}.tech-1",
            ok=ok,
            error=err,
            latency_ms=latency_ms,
            outcome=outcome,
        )

        # Log execution result
        self.global_state.add_event(
            "technician",
            "task_executed" if ok else "task_failed",
            f"outcome={outcome}",
        )

        return {
            "command_plan": command_plan,
            "action": code_blocks if outcome == WorkerDecision.GENERATE_ACTION.value else None,
            "step_result": result.__dict__,
            "outcome": outcome,
        }

    def _extract_code_blocks(self, text: str) -> List[Tuple[str, str]]:
        """Extract code blocks from markdown-style text."""
        import re
        
        # Pattern to match ```language\ncode\n```
        pattern = r'```(\w+)\n(.*?)\n```'
        matches = re.findall(pattern, text, re.DOTALL)
        
        code_blocks = []
        for lang, code in matches:
            lang = lang.lower()
            code = code.strip()
            if code:
                code_blocks.append((lang, code))
        
        return code_blocks

    def _infer_decision_from_text(self, text: str) -> Optional[str]:
        """Infer high-level decision from free-form LLM text.
        Returns one of: "done", "failed", "supplement", "need_quality_check", or None.
        """
        lowered = text.lower()
        # Prefer explicit Decision: <label>
        import re
        m = re.search(r"decision\s*[:\-]\s*(done|failed|supplement|need\s*quality\s*check)", lowered)
        if m:
            label = m.group(1)
            label = label.replace(" ", "_")
            return label
        if "need_quality_check" in lowered or "need quality check" in lowered:
            return "need_quality_check"
        if "supplement" in lowered:
            return "supplement"
        if "failed" in lowered or "cannot execute" in lowered or "can't proceed" in lowered:
            return "failed"
        if "done" in lowered or "completed" in lowered or "already finished" in lowered:
            return "done"
        return None

# ---------------------------------------------------------------------------
# Analyst – provides data analysis and recommendations
# ---------------------------------------------------------------------------
class Analyst:
    """Analyst role: analyze screen content and provide analytical support.

    Responsibilities:
    - Analyze current screen state and content
    - Provide recommendations and insights
    - Extract and process information from UI elements
    - Support decision-making with data analysis

    Tools_dict requirements:
    - analyst_agent: {"provider": str, "model": str} - LLM for analysis
    """

    def __init__(
        self,
        tools_dict: Dict[str, Any],
        global_state: NewGlobalState,
        platform: str = "unknown",
        enable_search: bool = False,
    ) -> None:
        self.tools_dict = tools_dict
        self.global_state = global_state
        self.platform = platform

        # LLM for analysis
        self.analyst_agent_name = "analyst_role"
        self.analyst_agent = NewTools()
        self.analyst_agent.register_tool(
            self.analyst_agent_name,
            self.tools_dict[self.analyst_agent_name]["provider"],
            self.tools_dict[self.analyst_agent_name]["model"],
        )

    def analyze_task(
        self,
        *,
        subtask: Dict[str, Any],
        guidance: Optional[str] = None,
        analysis_type: str = "general",
    ) -> Dict[str, Any]:
        """Analyze the current state and provide recommendations.

        Args:
            subtask: Current subtask information
            guidance: Optional guidance from manager
            analysis_type: Type of analysis ("general", "screen_content", "data_extraction", "recommendation")

        Returns a dict containing:
        - analysis: detailed analysis result
        - recommendations: list of recommendations
        - extracted_data: any extracted information
        - step_result: StepResult as dict
        - outcome: one of {"analysis_complete", "CANNOT_EXECUTE", "STALE_PROGRESS"}
        """
        screenshot_bytes = self.global_state.get_screenshot()
        if not screenshot_bytes:
            msg = "No screenshot available for analysis"
            logger.warning(msg)
            self.global_state.add_event("analyst", "no_screenshot", msg)
            result = StepResult(
                step_id=f"{subtask.get('subtask_id','unknown')}.analyst-0",
                ok=False,
                error=msg,
                latency_ms=0,
                outcome="STALE_PROGRESS",
            )
            return {
                "analysis": "",
                "recommendations": [],
                "extracted_data": {},
                "step_result": result.__dict__,
                "outcome": "STALE_PROGRESS",
            }

        # Build analysis prompt based on type
        analysis_prompt = self._build_analysis_prompt(subtask, guidance, analysis_type)

        # Call analyst agent
        t0 = time.time()
        try:
            analysis_result, total_tokens, cost_string = self.analyst_agent.execute_tool(
                self.analyst_agent_name,
                {"str_input": analysis_prompt, "img_input": screenshot_bytes},
            )
            latency_ms = int((time.time() - t0) * 1000)
            
            self.global_state.add_event(
                "analyst",
                "analysis_completed",
                f"type={analysis_type}, tokens={total_tokens}, cost={cost_string}",
            )
        except Exception as e:
            err = f"ANALYSIS_FAILED: {e}"
            logger.warning(err)
            self.global_state.add_event("analyst", "analysis_failed", err)
            result = StepResult(
                step_id=f"{subtask.get('subtask_id','unknown')}.analyst-1",
                ok=False,
                error=err,
                latency_ms=int((time.time() - t0) * 1000),
                outcome="CANNOT_EXECUTE",
            )
            return {
                "analysis": "",
                "recommendations": [],
                "extracted_data": {},
                "step_result": result.__dict__,
                "outcome": "CANNOT_EXECUTE",
            }

        # Parse analysis result
        try:
            parsed_result = self._parse_analysis_result(analysis_result, analysis_type)
            ok = True
            outcome = "analysis_complete"
            err = None
        except Exception as e:
            ok = False
            outcome = "CANNOT_EXECUTE"
            parsed_result = {
                "analysis": f"Failed to parse analysis: {str(e)}",
                "recommendations": [],
                "extracted_data": {}
            }
            err = f"PARSE_ANALYSIS_FAILED: {e}"
            logger.warning(err)

        result = StepResult(
            step_id=f"{subtask.get('subtask_id','unknown')}.analyst-1",
            ok=ok,
            error=err,
            latency_ms=latency_ms,
            outcome=outcome,
        )

        # Log analysis result
        self.global_state.add_event(
            "analyst",
            "analysis_ready" if ok else "analysis_failed",
            f"outcome={outcome}, type={analysis_type}",
        )

        return {
            "analysis": parsed_result["analysis"],
            "recommendations": parsed_result["recommendations"],
            "extracted_data": parsed_result["extracted_data"],
            "step_result": result.__dict__,
            "outcome": outcome,
        }

    def _build_analysis_prompt(self, subtask: Dict[str, Any], guidance: Optional[str], analysis_type: str) -> str:
        """Build analysis prompt based on type and context."""
        subtask_title = subtask.get("title", "")
        subtask_desc = subtask.get("description", "")
        
        base_prompt = f"""# Analysis Task
You are an expert analyst helping with GUI automation tasks.

## Current Context
- Subtask: {subtask_title}
- Description: {subtask_desc}
- Platform: {self.platform}
"""
        
        if guidance:
            base_prompt += f"- Guidance: {guidance}\n"

        if analysis_type == "screen_content":
            specific_prompt = """
## Analysis Type: Screen Content Analysis
Analyze the current screen and provide:
1. **Screen Overview**: What type of application/interface is shown
2. **Key Elements**: Important UI elements, buttons, forms, data visible
3. **Current State**: What state the application appears to be in
4. **Navigation Options**: Available actions or next steps
5. **Data Extraction**: Any important data or information visible

Output format:
```json
{
  "analysis": "Detailed screen analysis...",
  "recommendations": ["recommendation1", "recommendation2"],
  "extracted_data": {
    "key1": "value1",
    "key2": "value2"
  }
}
```
"""
        elif analysis_type == "data_extraction":
            specific_prompt = """
## Analysis Type: Data Extraction
Extract and structure data from the current screen:
1. **Text Content**: All readable text and labels
2. **Form Fields**: Input fields, dropdowns, checkboxes
3. **Tables/Lists**: Structured data in tables or lists
4. **Status Information**: Progress, notifications, alerts
5. **Numerical Data**: Numbers, percentages, counts

Output format:
```json
{
  "analysis": "Data extraction summary...",
  "recommendations": ["how to use this data"],
  "extracted_data": {
    "text_content": ["text1", "text2"],
    "form_fields": {"field1": "value1"},
    "tables": [{"col1": "val1", "col2": "val2"}],
    "status": "current status",
    "numbers": {"metric1": 123}
  }
}
```
"""
        elif analysis_type == "recommendation":
            specific_prompt = """
## Analysis Type: Recommendation
Provide strategic recommendations for completing the subtask:
1. **Current Assessment**: Evaluate current progress
2. **Next Steps**: Recommended actions to take
3. **Potential Issues**: Risks or problems to watch for
4. **Alternative Approaches**: Other ways to achieve the goal
5. **Success Criteria**: How to know when subtask is complete

Output format:
```json
{
  "analysis": "Strategic assessment...",
  "recommendations": [
    "immediate next action",
    "alternative approach",
    "risk mitigation"
  ],
  "extracted_data": {
    "progress_assessment": "current progress",
    "success_criteria": ["criteria1", "criteria2"],
    "risks": ["risk1", "risk2"]
  }
}
```
"""
        else:  # general analysis
            specific_prompt = """
## Analysis Type: General Analysis
Provide comprehensive analysis of the current situation:
1. **Situation Assessment**: What's currently happening
2. **Progress Evaluation**: How well the subtask is progressing
3. **Actionable Insights**: What should be done next
4. **Data Summary**: Key information from the screen

Output format:
```json
{
  "analysis": "Comprehensive analysis...",
  "recommendations": ["actionable recommendation"],
  "extracted_data": {
    "situation": "current situation",
    "progress": "progress status",
    "key_info": "important information"
  }
}
```
"""

        return base_prompt + specific_prompt

    def _parse_analysis_result(self, result: str, analysis_type: str) -> Dict[str, Any]:
        """Parse the analysis result from LLM response."""
        import json
        import re
        
        # Try to extract JSON from the response
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', result, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                return {
                    "analysis": parsed.get("analysis", ""),
                    "recommendations": parsed.get("recommendations", []),
                    "extracted_data": parsed.get("extracted_data", {})
                }
            except json.JSONDecodeError:
                pass
        
        # Fallback: try to parse the entire result as JSON
        try:
            parsed = json.loads(result)
            return {
                "analysis": parsed.get("analysis", ""),
                "recommendations": parsed.get("recommendations", []),
                "extracted_data": parsed.get("extracted_data", {})
            }
        except json.JSONDecodeError:
            pass
        
        # Final fallback: treat as plain text analysis
        return {
            "analysis": result,
            "recommendations": [],
            "extracted_data": {}
        }


# ---------------------------------------------------------------------------
# Operator – merges the planning and grounding flows
# ---------------------------------------------------------------------------
class Operator:
    """Operator role: generate next UI action and ground it to screen coordinates.

    Responsibilities:
    - Query the LLM action generator to propose the next grounded action (code snippet)
    - Parse the proposed action and extract intent + arguments
    - If necessary, run visual grounding to obtain precise coordinates
    - Return a normalized action dict compatible with `Action.py` for hardware execution

    """

    def __init__(
        self,
        tools_dict: Dict[str, Any],
        global_state: NewGlobalState,
        platform: str = "unknown",
        enable_search: bool = False,
        screen_size: List[int] = [1920, 1080],
    ) -> None:
        self.tools_dict = tools_dict
        self.global_state = global_state
        self.platform = platform
        self.enable_search = enable_search
        self.screen_size = screen_size

        # Embedding engine for Memory
        self.embedding_engine = NewTools()
        self.embedding_engine.register_tool(
            "embedding",
            self.tools_dict["embedding"]["provider"],
            self.tools_dict["embedding"]["model"],
        )

        # LLM for action generation
        self.operator_agent_name = "operator_role"
        tool_params = {}
        action_gen_cfg = self.tools_dict.get("action_generator", {})
        if self.enable_search:
            tool_params["enable_search"] = action_gen_cfg.get("enable_search", True)
            tool_params["search_provider"] = action_gen_cfg.get("search_provider", "bocha")
            tool_params["search_model"] = action_gen_cfg.get("search_model", "")
        else:
            tool_params["enable_search"] = False
        self.operator_agent = NewTools()
        self.operator_agent.register_tool(
            self.operator_agent_name,
            self.tools_dict[self.operator_agent_name]["provider"],
            self.tools_dict[self.operator_agent_name]["model"],
             **tool_params
        )

        # Visual grounding
        self.grounding_agent = Grounding(
            Tools_dict=self.tools_dict,
            platform=self.platform,
            width=self.screen_size[0],
            height=self.screen_size[1]
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_next_action(
        self,
        *,
        subtask: Dict[str, Any],
        guidance: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate and ground the next action for the given subtask.

        Returns a dict containing:
        - plan: raw LLM output text
        - action: JSON action dict (if ok)
        - step_result: StepResult as dict
        - outcome: one of {"generate_action", "CANNOT_EXECUTE", "STALE_PROGRESS"}
        """
        task = self.global_state.get_task()
        screenshot_bytes = self.global_state.get_screenshot()
        if not screenshot_bytes:
            # Without screenshot, we cannot ground; signal stale
            msg = "No screenshot available for action generation"
            logger.warning(msg)
            self.global_state.add_event("worker", "no_screenshot", msg)
            result = StepResult(
                step_id=f"{subtask.get('subtask_id','unknown')}.step-0",
                ok=False,
                error=msg,
                latency_ms=0,
                outcome="STALE_PROGRESS",
            )
            return {
                "plan": "",
                "action": None,
                "step_result": result.__dict__,
                "outcome": "STALE_PROGRESS",
            }

        # Build concise generator prompt
        subtask_title = subtask.get("title", "")
        subtask_desc = subtask.get("description", "")
        message = []
        message.append(f"Remember only complete the subtask: {subtask_title}")
        message.append(f"You can use this extra information for completing the current subtask: {subtask_desc}")
        if guidance:
            message.append(f"GUIDANCE: {guidance}")
        message.append("Return exactly one action as an agent.* function in Python fenced code under (Grounded Action).")
        generator_prompt = "\n\n".join(message)

        # Call action generator
        t0 = time.time()
        action_plan, total_tokens, cost_string = self.operator_agent.execute_tool(
            self.operator_agent_name,
            {"str_input": generator_prompt, "img_input": screenshot_bytes},
        )
        latency_ms = int((time.time() - t0) * 1000)
        self.global_state.add_event(
            "worker",
            "action_plan_generated",
            f"tokens={total_tokens}, cost={cost_string}",
        )

        # Parse action code
        try:
            action_code = parse_single_code_from_string(action_plan.split("Grounded Action")[-1])
            action_code = sanitize_code(action_code)
        except Exception as e:
            err = f"PARSE_ACTION_FAILED: {e}"
            logger.warning(err)
            self.global_state.add_event("worker", "parse_action_failed", err)
            result = StepResult(
                step_id=f"{subtask.get('subtask_id','unknown')}.step-1",
                ok=False,
                error=err,
                latency_ms=latency_ms,
                outcome="CANNOT_EXECUTE",
            )
            return {
                "action_plan": action_plan,
                "action": None,
                "step_result": result.__dict__,
                "outcome": "CANNOT_EXECUTE",
            }

        # Convert code into a normalized action dict
        agent: Grounding = self.grounding_agent
        try:
            plan_code = extract_first_agent_function(action_code)
            exec_code = eval(plan_code)  # type: ignore
            ok = True
            # Determine outcome based on action type
            action_type = ""
            if isinstance(exec_code, dict):
                action_type = str(exec_code.get("type", ""))
            if action_type == "Done":
                outcome = "worker_done"
            elif action_type == "Failed":
                outcome = "worker_fail"
            elif action_type == "Supplement":
                outcome = "worker_supplement"
            elif action_type == "NeedQualityCheck":
                outcome = "worker_stale_progress"
            else:
                outcome = "worker_generate_action"

            err = None
        except Exception as e:
            ok = False
            outcome = "CANNOT_EXECUTE"
            exec_code = None
            err = f"BUILD_ACTION_FAILED: {e}"
            logger.warning(err)

        result = StepResult(
            step_id=f"{subtask.get('subtask_id','unknown')}.step-1",
            ok=ok,
            error=err,
            latency_ms=latency_ms,
            outcome=outcome,
            action=exec_code,
        )

        # Log
        self.global_state.add_event(
            "worker",
            "action_ready" if ok else "action_failed",
            f"outcome={outcome}",
        )
        return {
            "action_plan": action_plan,
            "action": exec_code,
            "step_result": result.__dict__,
            "outcome": outcome,
        }

# ---------------------------------------------------------------------------
# Public facade for the new Worker module
# ---------------------------------------------------------------------------
class NewWorker:
    """Worker facade exposing specialized roles.

    Provides access to:
    - Operator: GUI interface operations with visual grounding
    - Technician: System-level operations via terminal commands
    - Analyst: Data analysis and recommendations
    """

    def __init__(
        self,
        tools_dict: Dict[str, Any],
        global_state: NewGlobalState,
        env_controller: DesktopEnv,
        platform: str = "unknown",
        enable_search: bool = False,
        client_password: str = "",
        screen_size: List[int] = [1920, 1080],
    ) -> None:
        self.operator = Operator(
            tools_dict=tools_dict,
            global_state=global_state,
            platform=platform,
            enable_search=enable_search,
            screen_size=screen_size,
        )
        
        self.technician = Technician(
            tools_dict=tools_dict,
            global_state=global_state,
            platform=platform,
            env_controller=env_controller,
            client_password=client_password,
        )
            
        self.analyst = Analyst(
            tools_dict=tools_dict,
            global_state=global_state,
            platform=platform,
            enable_search=enable_search,
        )
        self._global_state = global_state
        self._tools_dict = tools_dict
        self._platform = platform

    def process_subtask_and_create_command(self) -> Optional[str]:
        """Route to the right role, create command/decision if applicable, and return worker_decision string.
        Returns one of WorkerDecision values or None on no-op/error.
        """
        subtask_id = self._global_state.get_task().current_subtask_id
        subtask = self._global_state.get_subtask(subtask_id) #type: ignore
        if not subtask:
            logging.warning(f"Worker: subtask {subtask_id} not found")
            return None

        role = (subtask.assignee_role or "operator").lower()
        try:
            if role == "operator":
                res = self.operator.generate_next_action(subtask=subtask.to_dict())  # type: ignore
                outcome = (res.get("outcome") or "").strip()
                action = res.get("action")
                action_plan = res.get("action_plan", "")
                
                # Create command with complete information
                cmd = create_command_data(
                    command_id="", 
                    task_id=self._global_state.task_id, 
                    action=action or {}, 
                    subtask_id=subtask_id,
                    assignee_role=subtask.assignee_role or "operator"
                )
                command_id = self._global_state.add_command(cmd)
                
                pre_screenshot_analysis = ""
                pre_screenshot_id = self._global_state.get_screenshot_id()
                # Generate screenshot analysis using analyst role
                # analysis_res = self.analyst.analyze_task(
                #     subtask=subtask.to_dict(), 
                #     analysis_type="screen_content"
                # )
                # pre_screenshot_analysis = analysis_res.get("analysis", "")

                # Update command with all fields
                self._global_state.update_command_fields(
                    command_id,
                    assignee_role=subtask.assignee_role or "operator",
                    action=action or {},
                    pre_screenshot_id=pre_screenshot_id,
                    pre_screenshot_analysis=pre_screenshot_analysis
                )

                # Update worker decision based on outcome
                if outcome == WorkerDecision.GENERATE_ACTION.value and action:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.GENERATE_ACTION.value)
                elif outcome == WorkerDecision.WORKER_DONE.value:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.WORKER_DONE.value)
                elif outcome == WorkerDecision.SUPPLEMENT.value:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.SUPPLEMENT.value)
                elif outcome == WorkerDecision.CANNOT_EXECUTE.value:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.CANNOT_EXECUTE.value)
                elif outcome == WorkerDecision.STALE_PROGRESS.value:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.STALE_PROGRESS.value)

            if role == "technician":
                res = self.technician.execute_task(subtask=subtask.to_dict())  # type: ignore
                outcome = (res.get("outcome") or "").strip()
                action = res.get("action")
                command_plan = res.get("command_plan", "")
                
                # Create command with complete information
                cmd = create_command_data(
                    command_id="", 
                    task_id=self._global_state.task_id, 
                    action=action or {}, 
                    subtask_id=subtask_id,
                    assignee_role=subtask.assignee_role or "technician"
                )
                command_id = self._global_state.add_command(cmd)
                
                pre_screenshot_analysis = ""
                # Add screenshot and get ID
                pre_screenshot_id = self._global_state.get_screenshot_id()
                # Generate screenshot analysis using analyst role
                # analysis_res = self.analyst.analyze_task(
                #     subtask=subtask.to_dict(), 
                #     analysis_type="screen_content"
                # )
                # pre_screenshot_analysis = analysis_res.get("analysis", "")

                # Update command with all fields
                self._global_state.update_command_fields(
                    command_id,
                    assignee_role=subtask.assignee_role or "technician",
                    action=action or {},
                    pre_screenshot_id=pre_screenshot_id,
                    pre_screenshot_analysis=pre_screenshot_analysis
                )

                # Update worker decision based on outcome
                if outcome == WorkerDecision.GENERATE_ACTION.value and action:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.GENERATE_ACTION.value)
                elif outcome == WorkerDecision.WORKER_DONE.value:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.WORKER_DONE.value)
                elif outcome == WorkerDecision.STALE_PROGRESS.value:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.STALE_PROGRESS.value)
                elif outcome == WorkerDecision.SUPPLEMENT.value:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.SUPPLEMENT.value)
                elif outcome == WorkerDecision.CANNOT_EXECUTE.value:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.CANNOT_EXECUTE.value)

            if role == "analyst":
                res = self.analyst.analyze_task(subtask=subtask.to_dict(), analysis_type="general")  # type: ignore
                outcome = (res.get("outcome") or "").strip()
                analysis = res.get("analysis", "")
                recommendations = res.get("recommendations", [])
                extracted_data = res.get("extracted_data", {})
                
                # Create command with complete information
                cmd = create_command_data(
                    command_id="", 
                    task_id=self._global_state.task_id, 
                    action={"analysis": analysis, "recommendations": recommendations, "extracted_data": extracted_data}, 
                    subtask_id=subtask_id,
                    assignee_role=subtask.assignee_role or "analyst"
                )
                command_id = self._global_state.add_command(cmd)
                
                pre_screenshot_analysis = ""
                # Add screenshot and get ID
                pre_screenshot_id = self._global_state.get_screenshot_id()
                # Use the analysis result as pre_screenshot_analysis
                # pre_screenshot_analysis = analysis

                # Update command with all fields
                self._global_state.update_command_fields(
                    command_id,
                    assignee_role=subtask.assignee_role or "analyst",
                    action={"analysis": analysis, "recommendations": recommendations, "extracted_data": extracted_data},
                    pre_screenshot_id=pre_screenshot_id,
                    pre_screenshot_analysis=pre_screenshot_analysis
                )
                
                if outcome == "analysis_complete":
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.STALE_PROGRESS.value)
                    return WorkerDecision.STALE_PROGRESS.value
                elif outcome == "STALE_PROGRESS":
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.STALE_PROGRESS.value)
                    return WorkerDecision.STALE_PROGRESS.value
                else:
                    self._global_state.update_command_worker_decision(command_id, WorkerDecision.CANNOT_EXECUTE.value)
                    return WorkerDecision.CANNOT_EXECUTE.value

            # logging.info(f"Worker: unknown assignee_role '{role}' for subtask {subtask_id}")
            return WorkerDecision.CANNOT_EXECUTE.value
        except Exception as e:
            logging.error(f"Worker: error processing subtask {subtask_id}: {e}")
            return WorkerDecision.CANNOT_EXECUTE.value


# Export friendly alias
Worker = NewWorker 