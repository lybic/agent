# ---------------------------------------------------------------------------
# 1) Desktop automation backend (PyAutoGUI)
# ---------------------------------------------------------------------------
import os
import subprocess, difflib
import sys
import pyperclip
from PIL import Image
from numpy import imag
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
    Done,
    Failed,
    Screenshot
)

from gui_agents.agents.Backend.Backend import Backend
import time


class PyAutoGUIVMwareBackend(Backend):
    """VMware desktop backend powered by *pyautogui*.

    Pros  : zero dependency besides Python & pyautogui.
    Cons  : Requires an active, visible desktop session (won't work headless).
    """

    _supported = {Click, DoubleClick, Move, Scroll, Drag, TypeText, Hotkey, Wait, Done, Failed, Screenshot}

    # ¶ PyAutoGUI sometimes throws exceptions if mouse is moved to a corner.
    def __init__(self, default_move_duration: float = 0.0, platform: str | None = None):
        import pyautogui as pag  # local import to avoid hard requirement
        pag.FAILSAFE = False
        self.pag = pag
        self.default_move_duration = default_move_duration
        self.platform = platform

    # ------------------------------------------------------------------
    def execute(self, action: Action) -> str:
        if not self.supports(type(action)):
            raise NotImplementedError(f"{type(action).__name__} not supported by PyAutoGUIBackend")

        if isinstance(action, Click):
            return self._click(action)
        elif isinstance(action, DoubleClick):
            return self._doubleclick(action)
        elif isinstance(action, Move):
            return self._move(action)
        elif isinstance(action, Scroll):
            return self._scroll(action)
        elif isinstance(action, Drag):
            return self._drag(action)
        elif isinstance(action, TypeText):
            return self._type(action)
        elif isinstance(action, Hotkey):
            return self._hotkey(action)
        elif isinstance(action, Screenshot):
            screenshot = self._screenshot()
            return screenshot # type: ignore
        elif isinstance(action, Wait):
            return f"WAIT"
        elif isinstance(action, Done):
            return f"DONE"
        elif isinstance(action, Failed):
            return f"FAIL"
        else:
            # This shouldn't happen due to supports() check, but be safe.
            raise NotImplementedError(f"Unhandled action: {action}")

    # ----- individual helpers ------------------------------------------------
    def _click(self, act: Click) -> str:
        if act.button == 0:
            button_str = "left"
        elif act.button == 1:
            button_str = "middle"
        elif act.button == 2:
            button_str = "right"

        hold_keys = act.holdKey or []
        code_parts = []
        for k in hold_keys:
            code_parts.append(f"pyautogui.keyDown('{k}')")
            code_parts.append(f"time.sleep(0.05)")
        code_parts.append(f"pyautogui.click(x={act.x}, y={act.y}, clicks=1, button='{button_str}', duration={self.default_move_duration}, interval=0.5)")
        for k in hold_keys:
            code_parts.append(f"pyautogui.keyUp('{k}')")
        return "; ".join(code_parts)

    def _doubleclick(self, act: Click) -> str:
        if act.button == 0:
            button_str = "left"
        elif act.button == 1:
            button_str = "middle"
        elif act.button == 2:
            button_str = "right"

        hold_keys = act.holdKey or []
        code_parts = []
        for k in hold_keys:
            code_parts.append(f"pyautogui.keyDown('{k}')")
            code_parts.append(f"time.sleep(0.05)")
        code_parts.append(f"pyautogui.click(x={act.x}, y={act.y}, clicks=2, button='{button_str}', duration={self.default_move_duration}, interval=0.5)")
        for k in hold_keys:
            code_parts.append(f"pyautogui.keyUp('{k}')")
        return "; ".join(code_parts)

    def _move(self, act: Move) -> None:
        code_parts = []
        for k in act.holdKey or []:
            code_parts.append(f"pyautogui.keyDown('{k}')")
            code_parts.append(f"time.sleep(0.05)")
        code_parts.append(f"pyautogui.moveTo(x = {act.x}, y = {act.y})")
        for k in act.holdKey or []:
            code_parts.append(f"pyautogui.keyUp('{k}')")
        return "; ".join(code_parts)

    def _scroll(self, act: Scroll) -> None:
        code_parts = []
        code_parts.append(f"pyautogui.moveTo(x = {act.x}, y = {act.y})")
        if not act.stepVertical:
            code_parts.append(f"pyautogui.hscroll({act.stepHorizontal})")
        else:
            code_parts.append(f"pyautogui.vscroll({act.stepVertical})")
        return "; ".join(code_parts)

    def _drag(self, act: Drag) -> str:
        hold_keys = act.holdKey or []
        code_parts = []
        for k in hold_keys:
            code_parts.append(f"pyautogui.keyDown('{k}')")
            code_parts.append(f"time.sleep(0.05)")
        code_parts.append(f"pyautogui.moveTo(x = {act.startX}, y = {act.startY})")
        code_parts.append(f"pyautogui.dragTo(x = {act.endX}, y = {act.endY})")
        for k in hold_keys:
            code_parts.append(f"pyautogui.keyUp('{k}')")
        return "; ".join(code_parts)

    def _type(self, act: TypeText) -> str:
        code_parts = []
        code_parts.append(f"pyautogui.write('{act.text}')")
        return "; ".join(code_parts)

    def _hotkey(self, act: Hotkey) -> str:
        code_parts = []
        if act.duration:
            for k in act.keys or []:
                code_parts.append(f"pyautogui.keyDown('{k}')")
                code_parts.append(f"time.sleep(0.05)")    
            code_parts.append(f"time.sleep({act.duration} * 1e-3)")
            for k in act.keys or []:
                code_parts.append(f"pyautogui.keyUp('{k}')")
        else:
            keys_str = "', '".join(act.keys)
            code_parts.append(f"pyautogui.hotkey('{keys_str}', interval=0.1)")
        return "; ".join(code_parts)
    
    def _screenshot(self) -> str:
        return "screenshot = pyautogui.screenshot(); return screenshot"