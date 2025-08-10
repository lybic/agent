from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Dict, Any


class Directive(Enum):
    CONTINUE = auto()
    PATCH = auto()
    REPLAN = auto()


@dataclass
class StepResult:
    step_id: str
    latency_ms: int
    ok: bool = True
    error: Optional[str] = None
    action: Optional[str] = None
    is_patch: bool = False


def build_step_result(
    *,
    global_state: Any,
    code: List[Any],
    exec_error: Optional[str],
    step_dispatch_time_sec: float,
    fallback_step_id: Optional[str] = None,
) -> StepResult:
    """Construct a StepResult with consistent error/action mapping.

    - step_id: prefers global_state.get_last_step_id(); falls back to provided fallback.
    - error mapping: maps common substrings to ELEMENT_NOT_FOUND; maps agent.fail(...) to LLM_FAIL.
    - action: prefers global_state.get_last_action(); falls back to code[0]['type'] when available.
    - is_patch: gets from global_state.get_last_is_patch().
    """
    # Step id
    step_id: Optional[str] = None
    if hasattr(global_state, 'get_last_step_id'):
        step_id = global_state.get_last_step_id()
    step_id = step_id or (fallback_step_id or "step-unknown")

    # Error mapping
    mapped_error: Optional[str] = None
    if exec_error is not None:
        lowered = str(exec_error).lower()
        if any(k in lowered for k in ["not found", "no such element", "target not on screen", "locatecenteronscreen"]):
            mapped_error = "ELEMENT_NOT_FOUND"
        else:
            mapped_error = str(exec_error)

    # Action selection - use global_state
    action_value: Optional[str] = None
    if hasattr(global_state, 'get_last_action'):
        action_value = global_state.get_last_action()
    
    # Final fallback to code
    if action_value is None and isinstance(code, list) and len(code) > 0:
        first = code[0]
        if isinstance(first, dict) and "type" in first:
            action_value = str(first.get("type"))

    # Get is_patch from global_state
    is_patch: bool = False
    if hasattr(global_state, 'get_last_is_patch'):
        is_patch = global_state.get_last_is_patch()

    # Build result
    result = StepResult(
        step_id=step_id,
        latency_ms=int(step_dispatch_time_sec * 1000),
        ok=(mapped_error is None),
        error=mapped_error,
        action=action_value,
        is_patch=is_patch,
    )

    # Post-hoc mapping for explicit model fail signal
    if result.action and str(result.action).lower().startswith("agent.fail("):
        result.error = result.error or "LLM_FAIL"
    


    return result


class ExecutionMonitor:
    """Minimal heuristic execution monitor.

    Aggregates recent step results and emits a directive:
      - PATCH: transient hiccup (e.g., high latency spike), ELEMENT_NOT_FOUND, or repeated identical action
      - REPLAN: two consecutive execution failures (non ELEMENT_NOT_FOUND) or repeated identical action 3x
      - CONTINUE: default
    """

    def __init__(self, window: int = 3, latency_patch_threshold_ms: int = 2500) -> None:
        self.window = max(1, window)
        self.latency_patch_threshold_ms = latency_patch_threshold_ms
        self._recent: List[StepResult] = []
        # Patch counters per step for observability; Manager may also track its own budget
        self._patch_counts_by_step: Dict[str, int] = {}
        # Track last decision reason for external consumers (e.g., Manager -> reflector)
        self._last_reason: Optional[str] = None

    def feed(self, result: Optional[StepResult]) -> Directive:
        if result is None:
            self._last_reason = None
            return Directive.CONTINUE

        self._recent.append(result)
        if len(self._recent) > self.window:
            self._recent.pop(0)

        # Map specific error types to PATCH
        if result.error is not None:
            if str(result.error).upper() == "ELEMENT_NOT_FOUND":
                self._patch_counts_by_step[result.step_id] = self._patch_counts_by_step.get(result.step_id, 0) + 1
                self._last_reason = "ERROR_ELEMENT_NOT_FOUND"
                return Directive.PATCH

            # Non-ENF errors: REPLAN only after two consecutive failures
            recent_fail_flags = [(r.error is not None) for r in self._recent]
            if len(recent_fail_flags) >= 2 and recent_fail_flags[-1] and recent_fail_flags[-2]:
                self._last_reason = "CONSECUTIVE_FAILURES"
                return Directive.REPLAN
            # Otherwise, continue to allow next step (or other heuristics) to decide
            self._last_reason = "SINGLE_FAILURE"
            return Directive.CONTINUE

        # Immediate REPLAN if the LLM returned agent.fail(...)
        if result.action is not None and str(result.action).lower().startswith("agent.fail("):
            self._last_reason = "LLM_FAIL"
            return Directive.REPLAN

        # NOTE: Disable latency-based PATCH for successful planning steps.
        # High LLM planning latency should not cause a UI patch that replaces the intended action.
        if result.latency_ms >= self.latency_patch_threshold_ms:
            self._patch_counts_by_step[result.step_id] = self._patch_counts_by_step.get(result.step_id, 0) + 1
            self._last_reason = "HIGH_LATENCY"
            return Directive.PATCH

        # Heuristic: repeated identical action generation indicates no progress
        # - If last 2 actions are identical -> suggest a light PATCH (e.g., wait/scroll)
        # - If last 3 actions are identical -> escalate to REPLAN
        recent_actions = [r.action for r in self._recent if r.action is not None]
        if len(recent_actions) >= 2 and recent_actions[-1] == recent_actions[-2]:
            # Check if there are 3 in a row
            if len(recent_actions) >= 3 and recent_actions[-1] == recent_actions[-3]:
                self._last_reason = "REPEATED_IDENTICAL_ACTION_3X"
                return Directive.REPLAN
            self._patch_counts_by_step[result.step_id] = self._patch_counts_by_step.get(result.step_id, 0) + 1
            self._last_reason = "REPEATED_IDENTICAL_ACTION_2X"
            return Directive.PATCH


        # Multiple recent not-ok would be handled above, but keep hook for future
        self._last_reason = None
        return Directive.CONTINUE

    def get_patch_count_for_step(self, step_id: str) -> int:
        return self._patch_counts_by_step.get(step_id, 0)

    def get_last_reason(self) -> Optional[str]:
        return self._last_reason

    def get_recent(self, n: int | None = None) -> List[StepResult]:
        if n is None or n >= len(self._recent):
            return list(self._recent)
        return list(self._recent[-n:]) 