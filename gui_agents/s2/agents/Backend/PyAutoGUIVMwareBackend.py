# ---------------------------------------------------------------------------
# 1) Desktop automation backend (PyAutoGUI)
# ---------------------------------------------------------------------------
import os
import subprocess, difflib
import sys
import pyperclip
from PIL import Image
from numpy import imag
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
    Open,
    SwitchApp,
    Screenshot
)

from gui_agents.s2.agents.Backend.Backend import Backend
import time


class PyAutoGUIVMwareBackend(Backend):
    """VMware desktop backend powered by *pyautogui*.

    Pros  : zero dependency besides Python & pyautogui.
    Cons  : Requires an active, visible desktop session (won't work headless).
    """

    _supported = {Click, Drag, TypeText, Scroll, Hotkey, HoldAndPress, Wait, Open, SwitchApp, Screenshot}

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
        elif isinstance(action, Drag):
            return self._drag(action)
        elif isinstance(action, TypeText):
            return self._type(action)
        elif isinstance(action, Scroll):
            return self._scroll(action)
        elif isinstance(action, Hotkey):
            return self._hotkey(action)
        elif isinstance(action, HoldAndPress):
            return self._hold_and_press(action)
        elif isinstance(action, Open):
            return self._open_app(action)
        elif isinstance(action, SwitchApp):
            return self._switch_app(action)
        elif isinstance(action, Screenshot):
            return self._screenshot()
        elif isinstance(action, Wait):
            return f"time.sleep({action.seconds})"
        else:
            # This shouldn't happen due to supports() check, but be safe.
            raise NotImplementedError(f"Unhandled action: {action}")

    # ----- individual helpers ------------------------------------------------
    def _click(self, act: Click) -> str:
        hold_keys = act.hold_keys or []
        code_parts = []
        for k in hold_keys:
            code_parts.append(f"pyautogui.keyDown('{k}')")
        code_parts.append(f"pyautogui.click(x={act.xy[0]}, y={act.xy[1]}, clicks={act.num_clicks}, button='{act.button_type.lower()}', duration={self.default_move_duration})")
        for k in hold_keys:
            code_parts.append(f"pyautogui.keyUp('{k}')")
        return "; ".join(code_parts)

    def _drag(self, act: Drag) -> str:
        hold_keys = act.hold_keys or []
        code_parts = []
        for k in hold_keys:
            code_parts.append(f"pyautogui.keyDown('{k}')")
        code_parts.append(f"pyautogui.moveTo({act.start[0]}, {act.start[1]})")
        code_parts.append(f"pyautogui.dragTo({act.end[0]}, {act.end[1]})")
        for k in hold_keys:
            code_parts.append(f"pyautogui.keyUp('{k}')")
        return "; ".join(code_parts)

    def _type(self, act: TypeText) -> str:
        code_parts = []
        
        if act.xy:
            code_parts.append(f"pyautogui.click({act.xy[0]}, {act.xy[1]})")
        
        if act.overwrite:
            ctrl_key = "command" if self.platform.startswith("darwin") else "ctrl"
            code_parts.append(f"pyautogui.hotkey('{ctrl_key}', 'a')")
            code_parts.append("pyautogui.press('backspace')")
        
        code_parts.append(f"pyperclip.copy('{act.text}')")
        code_parts.append("time.sleep(0.05)")
        
        if self.platform.startswith("darwin"):
            code_parts.append("subprocess.run(['osascript', '-e', 'tell application \"System Events\" to keystroke \"v\" using command down'])")
        else:
            code_parts.append("pyautogui.hotkey('ctrl', 'v', interval=0.05)")
        
        if act.enter:
            code_parts.append("pyautogui.press('enter')")
        
        return "; ".join(code_parts)

    def _scroll(self, act: Scroll) -> str:
        scroll_method = "hscroll" if not act.vertical else "vscroll"
        return f"pyautogui.moveTo({act.xy[0]}, {act.xy[1]}); pyautogui.{scroll_method}({act.clicks})"

    def _hotkey(self, act: Hotkey) -> str:
        keys_str = "', '".join(act.keys)
        return f"print({act.keys}); pyautogui.hotkey('{keys_str}', interval=0.1)"

    def _hold_and_press(self, act: HoldAndPress) -> str:
        hold_keys = list(act.hold_keys)
        press_keys_list = list(act.press_keys)
        code_parts = []
        for k in hold_keys:
            code_parts.append(f"pyautogui.keyDown('{k}')")
        code_parts.append(f"pyautogui.press({press_keys_list})")
        for k in hold_keys:
            code_parts.append(f"pyautogui.keyUp('{k}')")
        return "; ".join(code_parts)

    # ----- NEW: application helpers -----------------------------------------
    def _switch_app(self, act: SwitchApp) -> str:
        """跨平台切换到已打开的指定应用窗口"""
        app_code = act.app_code
        if self.platform.startswith("darwin"):          # macOS
            return f"pyautogui.hotkey('command', 'space'); time.sleep(0.5); pyautogui.typewrite('{app_code}'); pyautogui.press('enter'); time.sleep(1.0)"
        elif self.platform.startswith("linux"):         # X11 + wmctrl
            return f"try: output = subprocess.check_output(['wmctrl', '-lx']).decode('utf-8').splitlines(); titles = [line.split(None, 4)[2] for line in output]; matches = difflib.get_close_matches('{app_code}', titles, n=1, cutoff=0.1); target = matches[0] if matches else None; win_id = next((line.split()[0] for line in output if target in line), None) if target else None; subprocess.run(['wmctrl', '-ia', win_id]) if win_id else None; subprocess.run(['wmctrl', '-ir', win_id, '-b', 'add,maximized_vert,maximized_horz']) if win_id else None; except FileNotFoundError: pyautogui.keyDown('alt'); pyautogui.press('tab'); pyautogui.keyUp('alt')"
        else:                                           # Assume Windows
            return f"pyautogui.hotkey('win', 'd'); time.sleep(0.5); pyautogui.typewrite('{app_code}'); pyautogui.press('enter'); time.sleep(1.0)"

    def _open_app(self, act: Open) -> str:
        target = act.app_or_filename

        if self.platform.startswith("darwin"):
            return f"try: subprocess.run(['open', '-a', '{target}'], check=True); except subprocess.CalledProcessError: script = 'tell application \"{target}\" to activate'; subprocess.run(['osascript', '-e', script], check=True)"
        elif self.platform.startswith("linux"):
            return f"try: subprocess.run(['gtk-launch', '{target}'], check=True); except FileNotFoundError: subprocess.run(['xdg-open', '{target}'], check=True)"
        else:  # Windows
            return f"try: os.startfile('{target}'); except OSError: subprocess.Popen(['start', '', '{target}'], shell=True)"
    
    def _screenshot(self) -> str:
        return "screenshot = pyautogui.screenshot(); return screenshot"