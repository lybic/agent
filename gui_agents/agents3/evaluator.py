"""
Evaluator module

This module implements the Evaluator as the quality assurance component.
It follows the design document provided by the user. The Evaluator is
responsible for validating execution quality at key checkpoints and
providing gate decisions to drive the controller flow.

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime
import os

from .new_global_state import NewGlobalState
from .enums import GateDecision, GateTrigger
from ..core.mllm import LLMAgent


# ========= Data Structures =========
@dataclass
class GateCheck:
    """Quality gate record structure.

    This mirrors the system GateCheck format described in the design.
    """

    gate_check_id: str
    task_id: str
    subtask_id: str
    trigger: str
    decision: str
    notes: str
    created_at: str


# ========= Prompt Templates =========
# Shared system information used for all scenes
SYSTEM_INFO = (
    "You are the Evaluator in the GUI-Agent system, responsible for verifying task "
    "execution quality and providing clear decisions for the Controller.\n")

# 1) WORKER_SUCCESS (Subtask Completion Verification)
SUCCESS_VERIFICATION_PROMPT = """
# System Role
You are the Evaluator in the GUI-Agent system, responsible for verifying task execution quality. When a Worker claims to have completed a subtask, you need to determine if it is truly complete.

# Input Information
- Current subtask description and target requirements
- Complete command execution records for this subtask
- Current screenshot
- Related artifacts and supplement materials

# Verification Points

## 1. Goal Achievement Verification
- Carefully analyze all requirements in the subtask description
- Check if each requirement has corresponding completion evidence in execution records
- Verify that all key success indicators are met
- Critical operations must have clear success feedback

## 2. Execution Completeness Check
- Review command sequence to confirm all necessary steps were executed
- Check if execution logic is coherent without obvious omissions
- Verify the rationality of execution order

## 3. Final State Confirmation
- Analyze if current screenshot shows expected completion state
- Check for error messages or warnings
- Confirm expected results have been produced (e.g., file creation, data saving, status updates)

## 4. Anomaly Detection
- Identify any unexpected state changes
- Assess if Worker's success judgment might be mistaken
- Note any overlooked potential issues

# Judgment Principle
When evidence is insufficient or uncertain, lean toward conservative decisions (choose gate_fail over gate_done) and explain the lack of evidence in the reason.

# Decision Output
You can only output one of the following two decisions:
- **gate_done**: Confirm subtask is completed
- **gate_fail**: Subtask is not actually completed

# Output Format
Decision: [gate_done/gate_fail]
Reason: [Brief explanation of judgment basis, within 100 words]
"""

# 2) WORKER_STALE (Execution Stagnation)
STALE_ANALYSIS_PROMPT = """
# System Role
You are the Evaluator in the GUI-Agent system, responsible for analyzing execution stagnation issues. When a Worker reports execution is stalled, you need to diagnose the cause and provide recommendations.

# Input Information
- Current subtask description and target requirements
- Complete command execution records for this subtask
- Current screenshot
- Worker's reported stagnation reason
- Related artifacts and supplement materials

# Analysis Points

## 1. Stagnation Cause Diagnosis
- Technical obstacles: unresponsive interface, elements cannot be located, system errors
- Logical dilemmas: path blocked, stuck in loop, unsure of next step
- Resource deficiency: missing passwords, configurations, permissions, etc.

## 2. Progress Assessment
- Analyze proportion of completed work relative to subtask
- Evaluate distance from current position to goal
- Consider time invested and number of attempts

## 3. Continuation Feasibility Analysis
- Judge probability of success if continuing
- Whether alternative execution paths exist
- Whether Worker has capability to solve current problem

## 4. Risk Assessment
- Potential negative impacts of continuing operation
- Whether existing progress might be damaged

# Judgment Principle
When uncertain if problem is solvable, lean toward conservative decisions to avoid wasting excessive resources.

# Decision Output
You can only output one of the following three decisions:
- **gate_continue**: Problem is surmountable, recommend continuing
- **gate_fail**: Cannot continue, needs replanning
- **gate_supplement**: Missing critical information, needs supplementation

# Output Format
Decision: [gate_continue/gate_fail/gate_supplement]
Reason: [Brief explanation of judgment basis, within 100 words]
Suggestion: [If continue, provide breakthrough suggestions; if supplement, specify what materials are needed]
"""

# 3) PERIODIC_CHECK (Regular Health Check)
HEALTH_CHECK_PROMPT = """
# System Role
You are the Evaluator in the GUI-Agent system, responsible for periodic monitoring of task execution health. Controller triggers this check periodically, and you need to assess if current execution status is normal.

# Input Information
- Current subtask description and target requirements
- Complete command execution records for this subtask
- Current screenshot
- Related artifacts and supplement materials

# Monitoring Points

## 1. Execution Progress Monitoring
- Identify which stage of execution is current
- Judge if actual progress meets expectations
- Confirm steady advancement toward goal

## 2. Execution Pattern Analysis
- Whether operations have clear purpose
- Whether there are many exploratory or trial-and-error operations
- Whether execution path is reasonable

## 3. Abnormal Pattern Detection
- Whether stuck in repetitive operations (same operation 3+ times consecutively)
- Whether errors or warnings are accumulating
- Whether obviously deviating from main task path

## 4. Warning Signal Recognition
- Whether there are signs of impending failure
- Whether current trend will lead to problems if continued
- Whether immediate intervention is needed

# Judgment Principle
When problem signs are detected, lean toward early intervention rather than waiting for problems to worsen.

# Decision Output
You can only output one of the following four decisions:
- **gate_continue**: Execution normal, continue current task
- **gate_done**: Detected subtask completion
- **gate_fail**: Found serious problems, intervention needed
- **gate_supplement**: Detected missing necessary resources

# Output Format
Decision: [gate_continue/gate_done/gate_fail/gate_supplement]
Reason: [Brief explanation of judgment basis, within 100 words]
Risk Alert: [If potential risks exist, briefly explain]
"""

# 4) FINAL_CHECK (Overall Task Completion Verification)
FINAL_CHECK_PROMPT = """
# System Role
You are the Evaluator in the GUI-Agent system, responsible for verifying overall task completion. All subtasks have been executed, and you need to determine if the entire task truly meets user requirements.

# Input Information
- Original task description and user requirements
- Task's DoD Checklist (Definition of Done Checklist)
- All subtask descriptions and statuses
- All command execution records for entire task
- Current screenshot
- All artifacts and supplement materials

# Verification Points

## 1. DoD Checklist Verification
- Check each item in the task's completion criteria
- Verify clear completion evidence for each checklist item
- Assess if completion quality meets requirements

## 2. Cross-Subtask Consistency Check
- Whether outputs from different subtasks are compatible
- Whether overall execution flow is coherent and complete
- Whether conflicts or contradictions exist between subtasks

## 3. Final State Verification
- Whether system final state meets task requirements
- Whether all expected outputs have been generated
- Whether there are leftover temporary files or unresolved issues

## 4. User Requirements Satisfaction
- Whether original user requirements are fully satisfied
- Whether solution is complete and usable
- Whether core objectives have been achieved

# Judgment Principle
When core functionality is missing, must determine gate_fail even if other parts are well completed. When evidence is insufficient, lean toward conservative judgment.

# Decision Output
You can only output one of the following two decisions:
- **gate_done**: Confirm entire task successfully completed
- **gate_fail**: Task not fully completed, needs replanning

# Output Format
Decision: [gate_done/gate_fail]
Reason: [Brief explanation of judgment basis, within 100 words]
Incomplete Items: [If gate_fail, list main incomplete items]
"""


class Evaluator:
    """Quality Evaluator implementation.

    The Evaluator consumes the complete NewGlobalState as input and makes a
    gate decision for the specified trigger type. The actual decision logic
    that leverages LLM prompts is left as placeholders for future work.
    """

    def __init__(self, global_state: NewGlobalState):
        """Create Evaluator.

        Args:
            global_state: Shared global state store
        """
        self.global_state = global_state

        # Read LLM configuration from tools_config.json (following old version pattern)
        import json
        tools_config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "tools",
            "tools_config.json")

        try:
            with open(tools_config_path, "r") as f:
                tools_config = json.load(f)
        except FileNotFoundError:
            raise ValueError(
                f"tools_config.json not found at {tools_config_path}")

        # Find evaluator tool configuration
        evaluator_config = None
        for tool in tools_config.get("tools", []):
            if tool.get("tool_name") == "evaluator":
                evaluator_config = tool
                break

        if not evaluator_config:
            raise ValueError(
                "evaluator tool configuration not found in tools_config.json")

        provider = evaluator_config.get("provider")
        model_name = evaluator_config.get("model_name")

        if not provider or not model_name:
            raise ValueError(
                "evaluator tool configuration missing provider or model_name")

        # Get API key from environment variable based on provider
        api_key = None
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
        elif provider == "gemini":
            api_key = os.getenv("GOOGLE_API_KEY")
        elif provider == "doubao":
            api_key = os.getenv("DOUBAO_API_KEY")
        elif provider == "zhipu":
            api_key = os.getenv("ZHIPU_API_KEY")
        else:
            # For other providers, try common environment variable names
            api_key = os.getenv(f"{provider.upper()}_API_KEY")

        if not api_key:
            raise ValueError(
                f"API key not found for provider '{provider}'. "
                f"Please set the appropriate environment variable (e.g., {provider.upper()}_API_KEY)"
            )

        engine_params = {
            "engine_type": provider,
            "model": model_name,
            "api_key": api_key,
        }

        self.llm_agent = LLMAgent(engine_params=engine_params,
                                  system_prompt=SYSTEM_INFO)

    # ========= Public API =========
    def quality_check(self) -> GateCheck:
        """Run quality check with no external parameters.

        The trigger type is inferred from the current global state.

        Returns:
            GateCheck: The created gate check record
        """

        globalstate = self.global_state

        # Determine subtask context
        task = globalstate.get_task()
        subtask_id: Optional[str] = task.get("current_subtask_id")

        # Infer trigger type from global state
        trigger_type = self._infer_trigger_type()

        # Use LLM to make decision
        scene = trigger_type
        prompt = self.build_prompt(scene)
        screenshot = globalstate.get_screenshot()

        # Reset conversation and send single-turn prompt with optional image
        self.llm_agent.reset()
        self.llm_agent.add_system_prompt(SYSTEM_INFO)
        self.llm_agent.add_message(prompt,
                                   image_content=screenshot,
                                   role="user")
        content, _tokens, _cost = self.llm_agent.get_response()
        parsed = self.parse_llm_output(content or "")
        normalized = self._normalize_decision(parsed.get("decision", ""), scene)
        if normalized is None:
            raise ValueError(
                f"Invalid decision from LLM: {parsed.get('decision', '')}")
        decision = normalized
        notes = self._compose_notes(parsed)
        trigger_enum = {
            "WORKER_SUCCESS": GateTrigger.WORKER_SUCCESS,
            "WORKER_STALE": GateTrigger.WORKER_STALE,
            "PERIODIC_CHECK": GateTrigger.PERIODIC_CHECK,
            "FINAL_CHECK": GateTrigger.FINAL_CHECK,
        }[scene]

        # Persist to global state in system format
        gate_check_id = globalstate.add_gate_check({
            "subtask_id": subtask_id,
            "trigger": trigger_enum.value,
            "decision": decision.value,
            "notes": notes,
            "created_at": datetime.now().isoformat(),
        })

        # Build dataclass instance to return
        record = GateCheck(
            gate_check_id=gate_check_id,
            task_id=globalstate.task_id,
            subtask_id=subtask_id or "",
            trigger=trigger_enum.value,
            decision=decision.value,
            notes=notes,
            created_at=datetime.now().isoformat(),
        )

        return record

    # ---- Trigger inference ----
    def _infer_trigger_type(self) -> str:
        """Infer trigger type from current global state."""
        task = self.global_state.get_task()
        pending = task.get("pending_subtasks", [])
        completed = task.get("completed_subtasks", [])
        current_subtask_id = task.get("current_subtask_id")

        if not pending and completed:
            return "FINAL_CHECK"

        if current_subtask_id:
            subtask = self.global_state.get_subtask(current_subtask_id)
            if subtask:
                status = subtask.get("status")
                if status == "fulfilled":
                    return "WORKER_SUCCESS"
                if status == "stale":
                    return "WORKER_STALE"

        return "PERIODIC_CHECK"

    # ========= Prompt building helpers =========
    def _format_commands(self, commands: list[dict]) -> str:
        """Format command records into a compact text block."""
        lines = []
        for cmd in commands:
            if not cmd:
                continue
            cmd_id = cmd.get("command_id", "")
            status = cmd.get("exec_status", "")
            msg = cmd.get("exec_message", "")
            pre = cmd.get("pre_screenshot_id", "")
            post = cmd.get("post_screenshot_id", "")
            lines.append(
                f"- [{cmd_id}] status={status} pre={pre} post={post} msg={msg}")
        return "\n".join(lines)

    def _format_subtask_brief(self, subtask: dict | None) -> str:
        if not subtask:
            return "(no subtask)"
        title = subtask.get("title", "")
        desc = subtask.get("description", "")
        status = subtask.get("status", "")
        return f"title={title}\nstatus={status}\ndescription={desc}"

    def _format_task_brief(self) -> str:
        task = self.global_state.get_task()
        return f"task_id={task.get('task_id')}\nobjective={task.get('objective','')}"

    def _get_artifacts_text(self) -> str:
        return self.global_state.get_artifacts()

    def _get_supplement_text(self) -> str:
        return self.global_state.get_supplement()

    def _collect_scene_inputs(self, scene: str) -> dict:
        """Collect and slice inputs for a specific scene.

        Command selection rules:
        - WORKER_SUCCESS: all commands of current subtask
        - WORKER_STALE:   all commands of current subtask
        - PERIODIC_CHECK: last 5 commands of current subtask
        - FINAL_CHECK:    all commands of entire task
        """
        task = self.global_state.get_task()
        subtask_id = task.get("current_subtask_id")
        subtask = self.global_state.get_subtask(
            subtask_id) if subtask_id else None

        # gather commands
        all_commands = self.global_state.get_commands()

        if scene in ("WORKER_SUCCESS", "WORKER_STALE",
                     "PERIODIC_CHECK") and subtask_id:
            subtask_cmd_ids = set((subtask or {}).get("command_trace_ids", []))
            sub_commands = [
                c for c in all_commands
                if c and c.get("command_id") in subtask_cmd_ids
            ]
            if scene == "PERIODIC_CHECK":
                sub_commands = sub_commands[-5:]
            commands = sub_commands
        elif scene == "FINAL_CHECK":
            commands = all_commands
        else:
            commands = []

        return {
            "task_brief": self._format_task_brief(),
            "subtask_brief": self._format_subtask_brief(subtask),
            "commands_text": self._format_commands(commands),
            "artifacts": self._get_artifacts_text(),
            "supplement": self._get_supplement_text(),
            "worker_report": self._get_worker_report(subtask),
        }

    def build_prompt(self, scene: str) -> str:
        """Build final prompt string by composing system info, scene template and inputs."""
        inputs = self._collect_scene_inputs(scene)
        if scene == "WORKER_SUCCESS":
            template = SUCCESS_VERIFICATION_PROMPT
        elif scene == "WORKER_STALE":
            template = STALE_ANALYSIS_PROMPT
        elif scene == "FINAL_CHECK":
            template = FINAL_CHECK_PROMPT
        else:
            template = HEALTH_CHECK_PROMPT

        parts = [
            SYSTEM_INFO,
            template,
            "\n# GlobalState Information\n",
            f"Task:\n{inputs['task_brief']}\n",
            f"Subtask:\n{inputs['subtask_brief']}\n",
            f"Commands:\n{inputs['commands_text']}\n",
            (f"Worker Report:\n{inputs['worker_report']}\n"
             if scene == "WORKER_STALE" else ""),
            f"Artifacts:\n{inputs['artifacts']}\n",
            f"Supplement:\n{inputs['supplement']}\n",
        ]
        return "\n".join(parts)

    def _compose_notes(self, parsed: Dict[str, str]) -> str:
        parts = []
        if parsed.get("reason"):
            parts.append(f"Reason: {parsed['reason']}")
        if parsed.get("suggestion"):
            parts.append(f"Suggestion: {parsed['suggestion']}")
        if parsed.get("risk_alert"):
            parts.append(f"Risk: {parsed['risk_alert']}")
        if parsed.get("incomplete_items"):
            parts.append(f"Incomplete: {parsed['incomplete_items']}")
        return " \n".join(parts) if parts else ""

    def _normalize_decision(self, decision_text: str,
                            scene: str) -> Optional[GateDecision]:
        if not decision_text:
            return None
        d = decision_text.strip().lower()
        # Accept raw or bracketed
        d = d.replace("[", "").replace("]", "")
        # Allow synonyms
        synonyms = {
            "gate_done": GateDecision.GATE_DONE,
            "done": GateDecision.GATE_DONE,
            "gate_fail": GateDecision.GATE_FAIL,
            "fail": GateDecision.GATE_FAIL,
            "gate_supplement": GateDecision.GATE_SUPPLEMENT,
            "supplement": GateDecision.GATE_SUPPLEMENT,
            "gate_continue": GateDecision.GATE_CONTINUE,
            "continue": GateDecision.GATE_CONTINUE,
        }
        candidate = synonyms.get(d)
        if candidate is None:
            return None

        # Enforce allowed set per scene
        allowed = {
            "WORKER_SUCCESS": {GateDecision.GATE_DONE, GateDecision.GATE_FAIL},
            "WORKER_STALE": {
                GateDecision.GATE_CONTINUE, GateDecision.GATE_FAIL,
                GateDecision.GATE_SUPPLEMENT
            },
            "PERIODIC_CHECK": {
                GateDecision.GATE_CONTINUE, GateDecision.GATE_DONE,
                GateDecision.GATE_FAIL, GateDecision.GATE_SUPPLEMENT
            },
            "FINAL_CHECK": {GateDecision.GATE_DONE, GateDecision.GATE_FAIL},
        }[scene]
        return candidate if candidate in allowed else None

    def _get_worker_report(self, subtask: Dict[str, Any] | None) -> str:
        """Extract the latest worker-reported reason from subtask.

        Priority:
        1) subtask["last_reason_text"]
        2) the latest entry in subtask["reasons_history"][].text
        3) empty string
        """
        if not subtask:
            return ""
        # 1) direct field
        text = subtask.get("last_reason_text")
        if isinstance(text, str) and text.strip():
            return text.strip()

        # 2) history fallback
        hist = subtask.get("reasons_history") or []
        if isinstance(hist, list) and hist:
            try:
                latest = max(hist, key=lambda x: x.get("at", ""))
                t = latest.get("text", "")
                return t.strip() if isinstance(t, str) else ""
            except Exception:
                pass
        return ""

    # ========= Output parsing helpers =========
    def parse_llm_output(self, text: str) -> dict:
        """Parse the model output into fields expected by controller and storage.

        Expected keys per scene (subset used per decision):
        - Decision: required
        - Reason: short text
        - Suggestion: optional in STALE
        - Risk Alert: optional in PERIODIC_CHECK
        - Incomplete Items: optional in FINAL_CHECK
        """
        result: dict[str, str] = {}
        if not text:
            return result
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for ln in lines:
            if ln.lower().startswith("decision:"):
                result["decision"] = ln.split(":", 1)[1].strip()
            elif ln.lower().startswith("reason:"):
                result["reason"] = ln.split(":", 1)[1].strip()
            elif ln.lower().startswith("suggestion:"):
                result["suggestion"] = ln.split(":", 1)[1].strip()
            elif ln.lower().startswith("risk alert:"):
                result["risk_alert"] = ln.split(":", 1)[1].strip()
            elif ln.lower().startswith("incomplete items:"):
                result["incomplete_items"] = ln.split(":", 1)[1].strip()
        return result
