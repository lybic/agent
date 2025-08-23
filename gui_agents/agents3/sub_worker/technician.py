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
from gui_agents.utils.common_utils import parse_technician_screenshot_analysis

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
        platform: str = "Ubuntu",
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

    def _get_command_history_for_subtask(self, subtask_id: str) -> str:
        """获取指定subtask的命令历史，格式化为易读的文本"""
        try:
            commands = self.global_state.get_commands_for_subtask(subtask_id)
            if not commands:
                return "无历史操作记录"
            
            history_lines = []
            history_lines.append("=== 历史操作记录 ===")
            
            for i, cmd in enumerate(commands, 1):
                # 格式化每个命令的信息
                action_type = "未知操作"
                action_desc = ""
                
                if isinstance(cmd.action, dict):
                    if "type" in cmd.action:
                        action_type = cmd.action["type"]
                    if "message" in cmd.action:
                        action_desc = cmd.action["message"]
                elif isinstance(cmd.action, list):
                    action_type = "代码生成"
                    if cmd.action:
                        descs = []
                        for idx, (lang, code) in enumerate(cmd.action, 1):
                            code_str = str(code)
                            descs.append(f"[{idx}] 语言: {lang}, 代码长度: {len(code_str)} 代码{code_str}")
                        action_desc = " | ".join(descs)
                
                # 添加命令状态信息
                status = cmd.worker_decision
                message = cmd.message if cmd.message else ""
                
                history_lines.append(f"{i}. [{action_type}] - 状态: {status}")
                if action_desc:
                    history_lines.append(f"   描述: {action_desc}")
                if message:
                    history_lines.append(f"   消息: {message}")
                if cmd.pre_screenshot_analysis:
                    analysis_preview = cmd.pre_screenshot_analysis[:150] + "..." if len(cmd.pre_screenshot_analysis) > 150 else cmd.pre_screenshot_analysis
                    history_lines.append(f"   截图分析: {analysis_preview}")
                history_lines.append("")
            
            return "\n".join(history_lines)
        except Exception as e:
            logger.warning(f"获取命令历史失败: {e}")
            return "获取历史记录失败"

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

        # 获取命令历史
        subtask_id = subtask.get("subtask_id", "")
        command_history = self._get_command_history_for_subtask(subtask_id)

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
        
        # 添加历史操作记录到提示词中
        task_prompt.append(f"# Previous Actions History:")
        task_prompt.append(command_history)
        task_prompt.append("")
        task_prompt.append("# Based on the above history, generate the appropriate bash or python code to complete this task.")
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

        # Parse screenshot analysis and extract/classify
        screenshot_analysis = parse_technician_screenshot_analysis(command_plan)
        self.global_state.add_event("technician", "screenshot_analysis_parsed", f"length={len(screenshot_analysis)}")
        
        try:
            decision = self._infer_decision_from_text(command_plan)
            code_blocks: List[Tuple[str, str]] = []
            decision_message = ""

            # Only try to extract code blocks when no explicit decision is detected
            if decision is None:
                code_blocks = self._extract_code_blocks(command_plan)

            if decision is None and code_blocks:
                ok = True
                outcome = WorkerDecision.GENERATE_ACTION.value
                err = None
                action = code_blocks
                message = ""
            elif decision == "done":
                ok = True
                outcome = WorkerDecision.WORKER_DONE.value
                err = None
                decision_message = self._extract_decision_message(command_plan, decision)
                action = {"type": "Done", "message": decision_message}
                message = decision_message
            elif decision == "failed":
                ok = False
                outcome = WorkerDecision.CANNOT_EXECUTE.value
                err = None
                decision_message = self._extract_decision_message(command_plan, decision)
                action = {"type": "Failed", "message": decision_message}
                message = decision_message
            elif decision == "supplement":
                ok = False
                outcome = WorkerDecision.SUPPLEMENT.value
                err = None
                decision_message = self._extract_decision_message(command_plan, decision)
                action = {"type": "Supplement", "message": decision_message}
                message = decision_message
            elif decision == "need_quality_check":
                ok = True
                outcome = WorkerDecision.STALE_PROGRESS.value
                err = None
                decision_message = self._extract_decision_message(command_plan, decision)
                action = {"type": "NeedQualityCheck", "message": decision_message}
                message = decision_message
            else:
                # No clear signal; treat as cannot execute
                ok = False
                outcome = WorkerDecision.CANNOT_EXECUTE.value
                err = "No code blocks or valid decision found"
                action = None
                message = ""
        except Exception as e:
            ok = False
            outcome = WorkerDecision.CANNOT_EXECUTE.value
            code_blocks = []
            err = f"CLASSIFICATION_FAILED: {e}"
            action = None
            message = ""
            logger.warning(err)
        
        result = StepResult(
            step_id=f"{subtask.get('subtask_id','unknown')}.tech-1",
            ok=ok,
            error=err,
            latency_ms=latency_ms,
            outcome=outcome,
            action=action, # type: ignore
        )

        # Log execution result
        self.global_state.add_event(
            "technician",
            "task_executed" if ok else "task_failed",
            f"outcome={outcome}",
        )

        return {
            "command_plan": command_plan,
            "action": action,
            "step_result": result.__dict__,
            "outcome": outcome,
            "screenshot_analysis": screenshot_analysis,
            "message": message,
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
        # First try to find structured decision format
        if "DECISION_START" in text and "DECISION_END" in text:
            # Extract content between markers
            start_marker = "DECISION_START"
            end_marker = "DECISION_END"
            start_pos = text.find(start_marker) + len(start_marker)
            end_pos = text.find(end_marker)
            
            if start_pos < end_pos:
                decision_content = text[start_pos:end_pos].strip()
                # Look for Decision: line
                import re
                decision_match = re.search(r"Decision:\s*(DONE|FAILED|SUPPLEMENT|NEED_QUALITY_CHECK)", decision_content, re.IGNORECASE)
                if decision_match:
                    decision = decision_match.group(1).lower()
                    if decision == "need_quality_check":
                        return "need_quality_check"
                    return decision

    def _extract_decision_message(self, text: str, decision: str) -> str:
        """Extract the detailed message associated with a decision.
        Returns the message explaining the decision reason and context.
        """
        import re
        
        # First try to extract from structured format
        if "DECISION_START" in text and "DECISION_END" in text:
            start_marker = "DECISION_START"
            end_marker = "DECISION_END"
            start_pos = text.find(start_marker) + len(start_marker)
            end_pos = text.find(end_marker)
            
            if start_pos < end_pos:
                decision_content = text[start_pos:end_pos].strip()
                # Look for Message: line
                message_match = re.search(r"Message:\s*(.+)", decision_content, re.IGNORECASE | re.DOTALL)
                if message_match:
                    message = message_match.group(1).strip()
                    # Clean up the message (remove extra whitespace and newlines)
                    message = re.sub(r'\s+', ' ', message)
                    if message:
                        return message

        return f"Decision {decision} was made"