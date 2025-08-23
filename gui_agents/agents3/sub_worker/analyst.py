"""
Analyst Module for GUI-Agent Architecture (agents3)
- Provides data analysis and recommendations
- Analyzes screen content and extracts information
- Supports decision-making with analytical insights
"""

from __future__ import annotations

import json
import re
import time
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from gui_agents.tools.new_tools import NewTools
from gui_agents.agents3.new_global_state import NewGlobalState

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
        elif analysis_type == "memorize_analysis":
            specific_prompt = """
## Analysis Type: Memorize Content Analysis
Analyze the memorized information and provide comprehensive answers based on the stored content:

1. **Content Review**: Review all memorized information from previous steps
2. **Question Analysis**: Identify what questions or problems need to be answered
3. **Information Synthesis**: Combine and organize the memorized data
4. **Answer Generation**: Provide comprehensive answers based on the memorized content
5. **Validation**: Ensure answers are complete and accurate

**Important**: Use ONLY the information that was previously memorized. Do not make assumptions or add external knowledge.

Output format:
```json
{
  "analysis": "Comprehensive analysis of memorized content and generated answers...",
  "recommendations": [
    "how to use this information",
    "next steps based on answers"
  ],
  "extracted_data": {
    "memorized_content": "summary of what was memorized",
    "questions_answered": ["question1: answer1", "question2: answer2"],
    "key_findings": ["finding1", "finding2"],
    "completeness_check": "verification that all memorized content was used"
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