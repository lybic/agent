# ---------------------------------------------------------------------------
# 1) Desktop automation backend (PyAutoGUI)
# ---------------------------------------------------------------------------
from gui_agents.s2.agents.Action import (
    Action,
    Click,
    Drag,
    TypeText,
    Scroll,
    Hotkey,
    HoldAndPress,
    Wait,
    MouseButton,
    ScrollAxis,
)

from gui_agents.s2.agents.Backend import Backend
import time


class PyAutoGUIBackend(Backend):
    """Pure local desktop backend powered by *pyautogui*.

    Pros  : zero dependency besides Python & pyautogui.
    Cons  : Requires an active, visible desktop session (won't work headless).
    """

    _supported = {Click, Drag, TypeText, Scroll, Hotkey, HoldAndPress, Wait}

    # ¶ PyAutoGUI sometimes throws exceptions if mouse is moved to a corner.
    def __init__(self, default_move_duration: float = 0.0):
        import pyautogui as pag  # local import to avoid hard requirement

        pag.FAILSAFE = False
        self.pag = pag
        self.default_move_duration = default_move_duration

    # ------------------------------------------------------------------
    def execute(self, action: Action) -> None:
        if not self.supports(type(action)):
            raise NotImplementedError(f"{type(action).__name__} not supported by PyAutoGUIBackend")

        if isinstance(action, Click):
            self._click(action)
        elif isinstance(action, Drag):
            self._drag(action)
        elif isinstance(action, TypeText):
            self._type(action)
        elif isinstance(action, Scroll):
            self._scroll(action)
        elif isinstance(action, Hotkey):
            self._hotkey(action)
        elif isinstance(action, HoldAndPress):
            self._hold_and_press(action)
        elif isinstance(action, Wait):
            time.sleep(action.seconds)
        else:
            # This shouldn't happen due to supports() check, but be safe.
            raise NotImplementedError(f"Unhandled action: {action}")

    # ----- individual helpers ------------------------------------------------
    def _click(self, act: Click) -> None:
        for k in act.hold_keys or []:
            self.pag.keyDown(k)
        self.pag.click(
            x=act.xy[0],
            y=act.xy[1],
            clicks=act.clicks,
            button=act.button.name.lower(),
            duration=self.default_move_duration,
        )
        for k in act.hold_keys or []:
            self.pag.keyUp(k)

    def _drag(self, act: Drag) -> None:
        for k in act.hold_keys or []:
            self.pag.keyDown(k)
        self.pag.moveTo(*act.start)
        self.pag.dragTo(*act.end, duration=act.duration)
        for k in act.hold_keys or []:
            self.pag.keyUp(k)

    def _type(self, act: TypeText) -> None:
        if act.xy:
            self.pag.click(*act.xy)
        if act.overwrite:
            self.pag.hotkey("ctrl", "a")
            self.pag.press("backspace")
        self.pag.write(act.text)
        if act.press_enter:
            self.pag.press("enter")

    def _scroll(self, act: Scroll) -> None:
        self.pag.moveTo(*act.xy)
        if act.axis is ScrollAxis.VERTICAL:
            self.pag.vscroll(act.clicks)
        else:
            self.pag.hscroll(act.clicks)

    def _hotkey(self, act: Hotkey) -> None:
        self.pag.hotkey(*act.keys)

    def _hold_and_press(self, act: HoldAndPress) -> None:
        for k in act.hold_keys:
            self.pag.keyDown(k)
        self.pag.press(list(act.press_keys))
        for k in act.hold_keys:
            self.pag.keyUp(k)

