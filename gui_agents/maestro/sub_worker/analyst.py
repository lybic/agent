"""
Analyst Module for GUI-Agent Architecture (agents3)
- Provides data analysis and recommendations based on artifacts content
- Analyzes stored information and extracts insights
- Supports decision-making with analytical insights
- Handles non-GUI interaction subtasks
"""

from __future__ import annotations

import json
import re
import time
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from gui_agents.tools.new_tools import NewTools
from gui_agents.maestro.new_global_state import NewGlobalState

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


class Analyst:
    """Analyst role: analyze artifacts content and provide analytical support.

    Responsibilities:
    - Analyze artifacts content and stored information
    - Provide recommendations and insights based on data
    - Extract and process information from stored content
    - Support decision-making with data analysis
    - Handle non-GUI interaction subtasks

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
        """Analyze the current state and provide recommendations based on artifacts content.

        Args:
            subtask: Current subtask information
            guidance: Optional guidance from manager
            analysis_type: Type of analysis (kept for compatibility, not used in new design)

        Returns a dict containing:
        - analysis: detailed analysis result
        - recommendations: list of recommendations
        - extracted_data: any extracted information
        - step_result: StepResult as dict
        - outcome: one of {"analysis_complete", "CANNOT_EXECUTE", "STALE_PROGRESS"}
        """
        # Get all required context information
        task = self.global_state.get_task()
        artifacts_content = self.global_state.get_artifacts()
        history_subtasks = self.global_state.get_subtasks()  # All subtasks including completed ones
        supplement_content = self.global_state.get_supplement()
        
        # Get current subtask commands
        subtask_id = subtask.get('subtask_id')
        subtask_commands = []
        if subtask_id:
            subtask_obj = self.global_state.get_subtask(subtask_id)
            if subtask_obj and hasattr(subtask_obj, 'command_trace_ids'):
                for cmd_id in subtask_obj.command_trace_ids:
                    cmd = self.global_state.get_command(cmd_id)
                    if cmd:
                        subtask_commands.append(cmd.to_dict() if hasattr(cmd, 'to_dict') else cmd)

        # Check if we have sufficient information to analyze
        if not artifacts_content and not history_subtasks and not supplement_content:
            msg = "No content available for analysis (artifacts, history, or supplement)"
            logger.warning(msg)
            self.global_state.add_event("analyst", "no_content", msg)
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

        # Build analysis prompt with all context information
        analysis_prompt = self._build_analysis_prompt(
            subtask, task, artifacts_content, history_subtasks, 
            supplement_content, subtask_commands, guidance
        )

        # Call analyst agent
        t0 = time.time()
        try:
            analysis_result, total_tokens, cost_string = self.analyst_agent.execute_tool(
                self.analyst_agent_name,
                {"str_input": analysis_prompt},
            )
            latency_ms = int((time.time() - t0) * 1000)
            
            self.global_state.log_llm_operation(
                "analyst",
                "analysis_completed",
                {
                    "tokens": total_tokens,
                    "cost": cost_string,
                    "duration": latency_ms / 1000.0,
                    "llm_output": analysis_result
                },
                str_input=analysis_prompt
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
            parsed_result = self._parse_analysis_result(analysis_result)
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
            f"outcome={outcome}",
        )

        return {
            "analysis": parsed_result["analysis"],
            "recommendations": parsed_result["recommendations"],
            "extracted_data": parsed_result["extracted_data"],
            "summary": parsed_result["summary"],
            "step_result": result.__dict__,
            "outcome": outcome,
        }

    def _build_analysis_prompt(
        self, 
        subtask: Dict[str, Any], 
        task: Any,
        artifacts_content: str,
        history_subtasks: List[Any],
        supplement_content: str,
        subtask_commands: List[Dict[str, Any]],
        guidance: Optional[str]
    ) -> str:
        """Build comprehensive analysis prompt with all context information."""
        
        # Format task information
        task_info = f"任务ID: {task.task_id}\n任务目标: {task.objective}" if task else "任务信息不可用"
        
        # Format subtask information
        subtask_info = f"子任务: {subtask.get('title', '')}\n子任务描述: {subtask.get('description', '')}"
        
        # Format history subtasks
        history_info = "历史子任务信息:\n"
        if history_subtasks:
            for i, hist_subtask in enumerate(history_subtasks[-5:], 1):  # Show last 5
                if hasattr(hist_subtask, 'to_dict'):
                    hist_data = hist_subtask.to_dict()
                else:
                    hist_data = hist_subtask
                history_info += f"{i}. {hist_data.get('title', 'Unknown')}: {hist_data.get('status', 'Unknown')}\n"
        else:
            history_info += "无历史子任务信息\n"
        
        # Format subtask commands
        commands_info = "当前子任务命令信息:\n"
        if subtask_commands:
            for i, cmd in enumerate(subtask_commands[-3:], 1):  # Show last 3 commands
                commands_info += f"{i}. {cmd.get('action', {}).get('type', 'Unknown action')}: {cmd.get('exec_status', 'Unknown')}\n"
        else:
            commands_info += "无命令执行信息\n"
        
        # Format artifacts content
        artifacts_info = f"当前 Artifacts 内容:\n{artifacts_content[:2000]}{'...' if len(artifacts_content) > 2000 else ''}"
        
        # Format supplement content
        supplement_info = f"补充信息:\n{supplement_content[:1000]}{'...' if len(supplement_content) > 1000 else ''}" if supplement_content else "无补充信息"
        
        # Build the complete prompt
        prompt = f"""# 分析任务
你是一个专业的数据分析师，负责分析任务相关的信息。

## 任务上下文
{task_info}

## 子任务信息
{subtask_info}

## 历史子任务信息
{history_info}

## 当前子任务命令信息
{commands_info}

## 当前 Artifacts 内容
{artifacts_info}

## 补充信息
{supplement_info}"""

        if guidance:
            prompt += f"\n## 指导说明\n{guidance}"

        prompt += """

## 分析要求
请根据以上信息，分析并完成子任务要求。你需要：
1. 理解子任务的具体需求
2. 分析相关的历史信息、命令执行情况和当前状态
3. 提供准确的分析结果和建议
4. 确保输出内容对任务完成有价值

## 输出格式
请按照以下JSON格式输出：
{
    "analysis": "详细的分析结果描述",
    "recommendations": ["具体建议1", "具体建议2"],
    "extracted_data": {"key": "value"},
    "summary": "简要总结"
}"""

        return prompt

    def _parse_analysis_result(self, result: str) -> Dict[str, Any]:
        """Parse the analysis result from LLM response."""
        # Try to extract JSON from the response
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', result, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                return {
                    "analysis": parsed.get("analysis", ""),
                    "recommendations": parsed.get("recommendations", []),
                    "extracted_data": parsed.get("extracted_data", {}),
                    "summary": parsed.get("summary", "")
                }
            except json.JSONDecodeError:
                pass
        
        # Fallback: try to parse the entire result as JSON
        try:
            parsed = json.loads(result)
            return {
                "analysis": parsed.get("analysis", ""),
                "recommendations": parsed.get("recommendations", []),
                "extracted_data": parsed.get("extracted_data", {}),
                "summary": parsed.get("summary", "")
            }
        except json.JSONDecodeError:
            pass
        
        # Final fallback: treat as plain text analysis
        return {
            "analysis": result,
            "recommendations": [],
            "extracted_data": {},
            "summary": ""
        } 