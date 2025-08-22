"""
Evaluator module

This module implements the Evaluator as the quality assurance component.
It follows the design document provided by the user. The Evaluator is
responsible for validating execution quality at key checkpoints and
providing gate decisions to drive the controller flow.

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime
import os

from .new_global_state import NewGlobalState
from .enums import GateDecision, GateTrigger, WorkerDecision, WorkerDecision
from gui_agents.tools.new_tools import NewTools
from gui_agents.prompts import get_prompt


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


# ========= Prompt Templates (loaded via prompts registry) =========
def _get_scene_template(scene: str) -> str:
    if scene == "WORKER_SUCCESS":
        return get_prompt("evaluator/worker_success_role", "")
    if scene == "WORKER_STALE":
        return get_prompt("evaluator/worker_stale_role", "")
    if scene == "FINAL_CHECK":
        return get_prompt("evaluator/final_check_role", "")
    # PERIODIC_CHECK
    return get_prompt("evaluator/periodic_role", "")


def _build_system_prompt(scene: str) -> str:
    """Compose system prompt = system_architecture + evaluator scene template."""
    arch = get_prompt("system_architecture", "")
    scene_tmpl = _get_scene_template(scene)
    return f"{arch}\n\n{scene_tmpl}".strip()


class Evaluator:
    """Quality Evaluator implementation.

    The Evaluator consumes the complete NewGlobalState as input and makes a
    gate decision for the specified trigger type. The actual decision logic
    that leverages LLM prompts is left as placeholders for future work.
    """

    def __init__(self,
                 global_state: NewGlobalState,
                 tools_dict: Optional[Dict[str, Any]] = None):
        """Create Evaluator.

        Args:
            global_state: Shared global state store
            tools_dict: Tool configuration dict, e.g. {"evaluator": {"provider": ..., "model": ...}}
        """
        self.global_state = global_state
        # Initialize evaluator tool via Tools using provided tools_dict or fallback to tools_config.json
        self.tools_dict = tools_dict or {}
        provider = None
        model_name = None
        if self.tools_dict.get("evaluator"):
            provider = self.tools_dict["evaluator"].get("provider")
            model_name = self.tools_dict["evaluator"].get("model")
        if not provider or not model_name:
            import json
            tools_config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "tools",
                "tools_config.json")
            with open(tools_config_path, "r") as f:
                tools_config = json.load(f)
            for tool in tools_config.get("tools", []):
                if tool.get("tool_name") == "evaluator":
                    provider = tool.get("provider")
                    model_name = tool.get("model_name")
                    break
        if not provider or not model_name:
            raise ValueError(
                "Missing evaluator tool configuration (provider/model)")

        # Use the new tool system: register four evaluator role tools by scene
        self.evaluator_agent = NewTools()
        for tool_name in ("worker_success_role", "worker_stale_role",
                          "periodic_role", "final_check_role"):
            try:
                self.evaluator_agent.register_tool(tool_name, provider,
                                                   model_name)
            except Exception:
                # Be tolerant: ignore duplicate registrations or other non-critical errors
                pass

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
        subtask_id: Optional[str] = task.current_subtask_id

        # Infer trigger type from global state
        trigger_type = self._infer_trigger_type()

        # Use LLM to make decision via Tools
        scene = trigger_type
        tool_name = self._scene_to_tool_name(scene)
        # Build prompts
        system_prompt = _build_system_prompt(scene)
        prompt = self.build_prompt(scene)
        screenshot = globalstate.get_screenshot()

        # Inject system prompt dynamically per scene
        try:
            tool_obj = self.evaluator_agent.tools.get(tool_name)
            if tool_obj and hasattr(tool_obj, "llm_agent"):
                tool_obj.llm_agent.reset()
                tool_obj.llm_agent.add_system_prompt(system_prompt)
        except Exception:
            pass

        content, _tokens, _cost = self.evaluator_agent.execute_tool(
            tool_name, {
                "str_input": prompt,
                "img_input": screenshot
            })
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
            # FINAL_CHECK reuses periodic_check trigger category
            "FINAL_CHECK": GateTrigger.PERIODIC_CHECK,
        }[scene]

        # Persist to global state in system format
        from .data_models import create_gate_check_data
        gate_check_id = globalstate.add_gate_check(
            create_gate_check_data(
                gate_check_id="",
                task_id=globalstate.task_id,
                decision=decision.value,
                subtask_id=subtask_id,
                notes=notes,
                trigger=trigger_enum.value,
            ))

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
        pending = task.pending_subtask_ids or []
        completed = task.history_subtask_ids or []
        current_subtask_id = task.current_subtask_id

        if not pending and completed:
            return "FINAL_CHECK"

        if current_subtask_id:
            # Get the latest command for current subtask to check worker_decision
            latest_command = self.global_state.get_current_command_for_subtask(current_subtask_id)
            if latest_command and latest_command.worker_decision:
                worker_decision = latest_command.worker_decision
                if worker_decision == WorkerDecision.WORKER_DONE.value:
                    return "WORKER_SUCCESS"
                if worker_decision == WorkerDecision.STALE_PROGRESS.value:
                    return "WORKER_STALE"

        return "PERIODIC_CHECK"

    def _scene_to_tool_name(self, scene: str) -> str:
        """Map scene name to the concrete tool name in the new tool system."""
        mapping = {
            "WORKER_SUCCESS": "worker_success_role",
            "WORKER_STALE": "worker_stale_role",
            "PERIODIC_CHECK": "periodic_role",
            "FINAL_CHECK": "final_check_role",
        }
        return mapping.get(scene, "periodic_role")

    # ========= Prompt building helpers =========
    def _format_commands(self, commands) -> str:
        """Format command records into a compact text block."""
        lines = []
        for cmd in commands:
            if not cmd:
                continue
            cmd_id = getattr(cmd, "command_id",
                             "") if not isinstance(cmd, dict) else cmd.get(
                                 "command_id", "")
            status = getattr(cmd, "exec_status",
                             "") if not isinstance(cmd, dict) else cmd.get(
                                 "exec_status", "")
            msg = getattr(cmd, "exec_message",
                          "") if not isinstance(cmd, dict) else cmd.get(
                              "exec_message", "")
            pre = getattr(cmd, "pre_screenshot_id",
                          "") if not isinstance(cmd, dict) else cmd.get(
                              "pre_screenshot_id", "")
            post = getattr(cmd, "post_screenshot_id",
                           "") if not isinstance(cmd, dict) else cmd.get(
                               "post_screenshot_id", "")
            lines.append(
                f"- [{cmd_id}] status={status} pre={pre} post={post} msg={msg}")
        return "\n".join(lines)

    def _format_subtask_brief(self, subtask) -> str:
        if not subtask:
            return "(no subtask)"
        if isinstance(subtask, dict):
            title = subtask.get("title", "")
            desc = subtask.get("description", "")
            status = subtask.get("status", "")
        else:
            title = getattr(subtask, "title", "")
            desc = getattr(subtask, "description", "")
            status = getattr(subtask, "status", "")
        return f"title={title}\nstatus={status}\ndescription={desc}"

    def _format_task_brief(self) -> str:
        task = self.global_state.get_task()
        return f"task_id={task.task_id}\nobjective={task.objective}"

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
        subtask_id = task.current_subtask_id
        subtask = self.global_state.get_subtask(
            subtask_id) if subtask_id else None

        # gather commands
        all_commands = self.global_state.get_commands()

        if scene in ("WORKER_SUCCESS", "WORKER_STALE",
                     "PERIODIC_CHECK") and subtask_id:
            subtask_cmd_ids = set(
                (subtask.command_trace_ids if subtask else []))
            sub_commands = [
                c for c in all_commands
                if c and (getattr(c, "command_id", None) in subtask_cmd_ids or
                          (isinstance(c, dict) and
                           c.get("command_id") in subtask_cmd_ids))
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
        """Build user prompt string containing only runtime inputs."""
        inputs = self._collect_scene_inputs(scene)

        parts = [
            "# GlobalState Information\n",
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

    def _get_worker_report(self, subtask) -> str:
        """Extract the latest worker-reported reason from subtask.

        Priority:
        1) subtask.last_reason_text
        2) the latest entry in subtask.reasons_history[].text
        3) empty string
        """
        if not subtask:
            return ""
        # 1) direct field
        if isinstance(subtask, dict):
            text = subtask.get("last_reason_text")
            if isinstance(text, str) and text.strip():
                return text.strip()
        else:
            text_val = getattr(subtask, "last_reason_text", None)
            if isinstance(text_val, str) and text_val.strip():
                return text_val.strip()

        # 2) history fallback
        hist = subtask.get("reasons_history") if isinstance(
            subtask, dict) else getattr(subtask, "reasons_history", [])
        if isinstance(hist, list) and hist:
            try:

                def get_at(entry):
                    if isinstance(entry, dict):
                        return entry.get("at", "")
                    return getattr(entry, "at", "")

                latest = max(hist, key=lambda x: get_at(x))
                if isinstance(latest, dict):
                    t = latest.get("text", "")
                else:
                    t = getattr(latest, "text", "")
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
