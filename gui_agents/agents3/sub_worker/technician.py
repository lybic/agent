"""
Technician Module for GUI-Agent Architecture (agents3)
- Provides system-level operations via terminal commands
- Generates and executes bash/python scripts
- Returns execution results and status
"""

from __future__ import annotations

import re
import time
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
from desktop_env.desktop_env import DesktopEnv

from gui_agents.tools.new_tools import NewTools
from gui_agents.agents3.new_global_state import NewGlobalState
from gui_agents.agents3.enums import WorkerDecision

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Lightweight step result for controller/evaluator handoff."""
    step_id: str
    ok: bool
    error: Optional[str]
    latency_ms: int
    outcome: str
    action: Optional[Dict[str, Any]] = None


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
        client_password: str = "",
        # max_execution_time: int = 300,
    ) -> None:
        self.tools_dict = tools_dict
        self.global_state = global_state
        self.platform = platform
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