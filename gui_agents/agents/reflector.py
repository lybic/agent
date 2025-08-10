from typing import Optional, List, Callable, Literal, Any, Dict

try:
    # Local imports within the project
    from gui_agents.tools.tools import Tools  # type: ignore
except Exception:
    # Fallback for different import paths during tests
    from ..tools.tools import Tools  # type: ignore

# NOTE: StepResult is only used for typing; avoid hard import cycles by using a light protocol
try:
    from gui_agents.types import StepResult  # type: ignore
except Exception:
    try:
        from ..types import StepResult  # type: ignore
    except Exception:
        # Minimal fallback type to avoid import errors if StepResult location changes
        class StepResult:  # type: ignore
            step_id: str
            ok: bool
            error: Optional[str]
            latency_ms: Optional[float]
            action: Optional[str]
            is_patch: bool
            

class Reflector:
    """Encapsulates the trajectory reflection logic as a standalone helper.

    This class manages a dedicated Tools instance for the trajectory reflector
    and exposes a minimal API for initialization, priming, trajectory reflection,
    and manager decision support (PATCH vs REPLAN).
    """

    def __init__(
        self,
        tools_dict: dict,
        tool_name: str = "traj_reflector",
        logger_cb: Optional[Callable[[str, dict], None]] = None,
    ) -> None:
        self._tool_name = tool_name
        self._logger = logger_cb
        self._available = tool_name in tools_dict
        self._tools: Optional[Tools] = None

        if self._available:
            self._tools = Tools()
            self._tools.register_tool(
                tool_name,
                tools_dict[tool_name]["provider"],
                tools_dict[tool_name]["model"],
            )

    def is_available(self) -> bool:
        return self._available and (self._tools is not None)

    def _log(self, operation: str, data: dict) -> None:
        if self._logger is not None:
            try:
                self._logger(operation, data)
            except Exception:
                pass

    def prime_initial(self, text: str, screenshot: Optional[Any]) -> None:
        """Prime the reflector with the initial subtask context and screen.

        This mirrors the previous worker-first-turn behavior.
        """
        if not self.is_available():
            return
        try:
            assert self._tools is not None
            self._tools.tools[self._tool_name].llm_agent.add_message(
                text + "\n\nThe initial screen is provided. No action has been taken yet.",
                image_content=screenshot,
                role="user",
            )
        except Exception as e:
            self._log("reflector_prime_error", {"error": str(e)})

    def reflect_trajectory(self, context_text: str, screenshot: Optional[Any]) -> str:
        """Produce a textual reflection for inclusion in agent prompts."""
        if not self.is_available():
            return ""
        try:
            assert self._tools is not None
            out, tokens, cost = self._tools.execute_tool(
                self._tool_name, {"str_input": context_text, "img_input": screenshot}
            )
            self._tools.reset(self._tool_name)
            
            # Log the input for this model call
            self._log("reflector_trajectory", {
                "input": context_text,
                "tokens": tokens,
                "cost": cost,
                "output": str(out)
            })
            
            return str(out)
        except Exception as e:
            self._log("reflector_trajectory_error", {"error": str(e)})
            return ""

    def reflect_manager_decision(
        self, recent: List[StepResult], reason: str
    ) -> Literal["PATCH", "REPLAN", "CONTINUE", "UNKNOWN"]:
        """Lightweight decision support for Manager: choose PATCH vs REPLAN vs CONTINUE.

        Returns one of "PATCH", "REPLAN", "CONTINUE", or "UNKNOWN" if the model output is ambiguous.
        """
        if not self.is_available():
            return "UNKNOWN"
        try:
            recent_text = "\n".join(
                f"step_id={getattr(r, 'step_id', '?')}, ok={getattr(r, 'ok', '?')}, "
                f"error={getattr(r, 'error', None)}, latency_ms={getattr(r, 'latency_ms', None)}, "
                f"action={getattr(r, 'action', None)}, is_patch={getattr(r, 'is_patch', False)}"
                for r in (recent or [])
            ) or "(no recent results)"

            prompt = (
                f"Trajectory appears stuck based on execution-monitor signal: {reason}.\n"
                f"Recent StepResults (most recent last):\n{recent_text}\n\n"
                "Question: Based on the recent execution results, what should be done?\n"
                "- PATCH: If this is a transient UI state that can be resolved with a small stabilization action (e.g., waiting for UI to load, scrolling to reveal content)\n"
                "- REPLAN: If the plan is fundamentally wrong and requires replanning (e.g., wrong approach, missing steps, incorrect assumptions)\n"
                "- CONTINUE: If the execution is progressing normally and should continue without intervention (e.g., actions are working as expected, minor delays are normal, progress is being made)\n"
                "Consider the context: if actions are succeeding (ok=True) and errors are minor or expected, CONTINUE is often the right choice.\n\n"
                "IMPORTANT: Start your response with exactly one of these words: PATCH, REPLAN, or CONTINUE\n"
                "Then provide a brief rationale for your decision."
            )

            assert self._tools is not None
            out, tokens, cost = self._tools.execute_tool(
                self._tool_name, {"str_input": prompt, "img_input": None}
            )
            self._tools.reset(self._tool_name)

            # Log the input for this model call
            self._log("reflector_manager_decision", {
                "input": prompt,
                "tokens": tokens,
                "cost": cost,
                "output": str(out),
                "reason": reason
            })

            decision_text = str(out).upper()
            
            # More robust parsing logic
            # First, look for exact matches at the beginning of lines
            lines = decision_text.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('REPLAN'):
                    return "REPLAN"
                elif line.startswith('PATCH'):
                    return "PATCH"
                elif line.startswith('CONTINUE'):
                    return "CONTINUE"
            
            # If no exact line matches, look for keywords with priority
            # REPLAN has highest priority (most conservative)
            if "REPLAN" in decision_text:
                return "REPLAN"
            elif "PATCH" in decision_text:
                return "PATCH"
            elif "CONTINUE" in decision_text:
                return "CONTINUE"
            
            # If still no match, try to infer from context
            # Look for words that suggest the decision
            if any(word in decision_text for word in ["WRONG", "FUNDAMENTALLY", "REPLANNING", "RESTART"]):
                return "REPLAN"
            elif any(word in decision_text for word in ["WAIT", "SCROLL", "STABILIZE", "TRANSIENT"]):
                return "PATCH"
            elif any(word in decision_text for word in ["NORMAL", "PROGRESSING", "WORKING", "EXPECTED"]):
                return "CONTINUE"
            
            return "UNKNOWN"
        except Exception as e:
            self._log("reflector_decision_error", {"error": str(e)})
            return "UNKNOWN"

    def reflect_agent_log(
        self, agent_log: List[Dict[str, Any]], reason: str
    ) -> str:
        """Analyze agent log entries to provide insights for planning.
        
        Returns a string with insights about the recent agent behavior.
        """
        if not self.is_available():
            return ""
        try:
            # Extract relevant information from agent log
            recent_actions = []
            for entry in agent_log[-10:]:  # Last 10 entries
                content = entry.get("content", "")
                action_type = entry.get("type", "unknown")
                
                # Look for action patterns in the content
                if "agent.hotkey" in content:
                    # Extract the hotkey action
                    import re
                    hotkey_match = re.search(r"agent\.hotkey\(\[([^\]]+)\], (\d+)\)", content)
                    if hotkey_match:
                        key = hotkey_match.group(1).strip("'\"")
                        duration = hotkey_match.group(2)
                        recent_actions.append(f"Hotkey: {key} ({duration}ms)")
                    else:
                        recent_actions.append("Hotkey action")
                elif "Hardware action" in content:
                    recent_actions.append("Hardware action executed")
                elif "Previous action verification" in content:
                    # Extract verification result
                    if "did not result in" in content:
                        recent_actions.append("Action failed to produce expected result")
                    elif "resulted in" in content:
                        recent_actions.append("Action produced result")
                else:
                    recent_actions.append(f"{action_type}: {content[:100]}...")

            recent_text = "\n".join(recent_actions) if recent_actions else "(no recent actions)"

            prompt = (
                f"Analyze the recent agent behavior for planning context: {reason}.\n"
                f"Recent agent actions (most recent last):\n{recent_text}\n\n"
                "Provide insights about:\n"
                "- Whether the agent is making progress or stuck in loops\n"
                "- What patterns or issues you observe\n"
                "- What the agent should focus on next\n"
                "- Any potential problems with the current approach\n"
                "Keep your response concise and actionable."
            )

            assert self._tools is not None
            out, tokens, cost = self._tools.execute_tool(
                self._tool_name, {"str_input": prompt, "img_input": None}
            )
            self._tools.reset(self._tool_name)

            # Log the input for this model call
            self._log("reflector_agent_log", {
                "input": prompt,
                "tokens": tokens,
                "cost": cost,
                "output": str(out)
            })

            return str(out)
        except Exception as e:
            self._log("reflector_agent_log_error", {"error": str(e)})
            return ""

    def reset(self) -> None:
        if self.is_available():
            try:
                assert self._tools is not None
                self._tools.reset(self._tool_name)
            except Exception:
                pass 