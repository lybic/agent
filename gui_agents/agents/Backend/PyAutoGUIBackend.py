# ---------------------------------------------------------------------------
# 1) Desktop automation backend (PyAutoGUI)
# ---------------------------------------------------------------------------
import subprocess
import sys
import pyperclip
from gui_agents.agents.Action import (
    Action,
    Click,
    DoubleClick,
    Move,
    Scroll,
    Drag,
    TypeText,
    Hotkey,
    Wait,
    Screenshot
)

from gui_agents.agents.Backend.Backend import Backend
import time


class PyAutoGUIBackend(Backend):
    """Pure local desktop backend powered by *pyautogui*.

    Pros  : zero dependency besides Python & pyautogui.
    Cons  : Requires an active, visible desktop session (won't work headless).
    """

    _supported = {Click, DoubleClick, Move, Scroll, Drag, TypeText, Hotkey, Wait, Screenshot}

    # ¶ PyAutoGUI sometimes throws exceptions if mouse is moved to a corner.
    def __init__(self, default_move_duration: float = 0.0, platform: str | None = None):
        import pyautogui as pag  # local import to avoid hard requirement
        pag.FAILSAFE = False
        self.pag = pag
        self.default_move_duration = default_move_duration
        # ↙️ Critical patch: save platform identifier
        self.platform = (platform or sys.platform).lower()

    # ------------------------------------------------------------------
    def execute(self, action: Action) -> None:
        if not self.supports(type(action)):
            raise NotImplementedError(f"{type(action).__name__} not supported by PyAutoGUIBackend")

        if isinstance(action, Click):
            self._click(action)
        elif isinstance(action, DoubleClick):
            self._doubleClick(action)
        elif isinstance(action, Move):
            self._move(action)
        elif isinstance(action, Scroll):
            self._scroll(action)
        elif isinstance(action, Drag):
            self._drag(action)
        elif isinstance(action, TypeText):
            self._type(action)
        elif isinstance(action, Hotkey):
            self._hotkey(action)
        elif isinstance(action, Screenshot):
            screenshot = self._screenshot()
            return screenshot # type: ignore
        elif isinstance(action, Wait):
            time.sleep(action.duration * 1e-3)
        else:
            # This shouldn't happen due to supports() check, but be safe.
            raise NotImplementedError(f"Unhandled action: {action}")

    # ----- individual helpers ------------------------------------------------
    def _click(self, act: Click) -> None:
        for k in act.holdKey or []:
            self.pag.keyDown(k)
            time.sleep(0.05)
        
        button_str = 'primary'
        if act.button == 1:
            button_str = "left"
        elif act.button == 4:
            button_str = "middle"
        elif act.button == 2:
            button_str = "right"

        self.pag.click(
            x=act.x,
            y=act.y,
            clicks=1,
            button=button_str, # type: ignore
            duration=self.default_move_duration,
            interval=0.5,
        )
        for k in act.holdKey or []:
            self.pag.keyUp(k)
    
    def _doubleClick(self, act: DoubleClick) -> None:
        for k in act.holdKey or []:
            self.pag.keyDown(k)
            time.sleep(0.05)
        button_str = 'primary'
        if act.button == 1:
            button_str = "left"
        elif act.button == 4:
            button_str = "middle"
        elif act.button == 2:
            button_str = "right"

        self.pag.click(
            x=act.x,
            y=act.y,
            clicks=2,
            button=button_str,
            duration=self.default_move_duration,
            interval=0.5,
        )
        for k in act.holdKey or []:
            self.pag.keyUp(k)

    def _move(self, act: Move) -> None:
        for k in act.holdKey or []:
            self.pag.keyDown(k)
            time.sleep(0.05)
        self.pag.moveTo(x = act.x, y = act.y)
        for k in act.holdKey or []:
            self.pag.keyUp(k)
    
    def _scroll(self, act: Scroll) -> None:
        self.pag.moveTo(x = act.x, y = act.y)
        if act.stepVertical is None:
            if act.stepHorizontal is not None:
                self.pag.hscroll(act.stepHorizontal)
        else:
            self.pag.vscroll(act.stepVertical)

    def _drag(self, act: Drag) -> None:
        for k in act.holdKey or []:
            self.pag.keyDown(k)
            time.sleep(0.05)
            
        self.pag.moveTo(x=act.startX, y=act.startY)
        time.sleep(0.1)
        
        self.pag.mouseDown(button='left')
        time.sleep(0.2)
        
        self.pag.moveTo(x=act.endX, y=act.endY, duration=0.5)
        time.sleep(0.1)
        
        self.pag.mouseUp(button='left')
        
        for k in act.holdKey or []:
            self.pag.keyUp(k)

    def _type(self, act: TypeText) -> None:
        # ------- Paste Chinese / any text --------------------------------
        pyperclip.copy(act.text)
        time.sleep(0.05)  # let clipboard stabilize

        if self.platform.startswith("darwin"):
            # self.pag.hotkey("commandright", "v", interval=0.05)
            # # 1. Press Command key
            subprocess.run([
                "osascript", "-e",
                'tell application "System Events" to keystroke "v" using command down'
            ])

        else:                               # Windows / Linux
            self.pag.hotkey("ctrl", "v", interval=0.05)

    def _hotkey(self, act: Hotkey) -> None:
        # self.pag.hotkey(*act.keys, interval=0.1)
        if act.duration is not None:
            for k in act.keys or []:
                self.pag.keyDown(k)
                time.sleep(act.duration * 1e-3)    
            # time.sleep(act.duration * 1e-3)
            for k in reversed(act.keys):
                self.pag.keyUp(k)
        else:
            self.pag.hotkey(*act.keys, interval=0.1)

    def _screenshot(self):
        screenshot = self.pag.screenshot()
        return screenshot