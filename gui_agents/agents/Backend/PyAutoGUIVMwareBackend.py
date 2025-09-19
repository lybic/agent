# ---------------------------------------------------------------------------
# 1) Desktop automation backend (PyAutoGUI)
# ---------------------------------------------------------------------------
import os
import io
from PIL import Image
from typing import Optional
from desktop_env.desktop_env import DesktopEnv
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

def screenshot_bytes_to_pil_image(screenshot_bytes: bytes) -> Optional[Image.Image]:
    """
    Convert the bytes data of obs["screenshot"] to a PIL Image object, preserving the original size
    
    Args:
        screenshot_bytes: The bytes data of the screenshot
    
    Returns:
        PIL Image object, or None if conversion fails
    """
    try:
        # Create PIL Image object directly from bytes
        image = Image.open(io.BytesIO(screenshot_bytes))
        return image
    except Exception as e:
        raise RuntimeError(f"Failed to convert screenshot bytes to PIL Image: {e}")

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
        self.use_precreate_vm = os.getenv("USE_PRECREATE_VM")
        if self.use_precreate_vm is not None:
            if self.use_precreate_vm == "Ubuntu":
                path_to_vm = os.path.join("vmware_vm_data", "Ubuntu-x86", "Ubuntu.vmx")
            elif self.use_precreate_vm == "Windows":
                path_to_vm = os.path.join("vmware_vm_data", "Windows-x86", "Windows 10 x64.vmx")
            else:
                raise ValueError(f"USE_PRECREATE_VM={self.use_precreate_vm} is not supported. Please use Ubuntu or Windows.")

            self.env = DesktopEnv(
                path_to_vm=path_to_vm,
                provider_name="vmware", 
                os_type=self.use_precreate_vm, 
                action_space="pyautogui",
                require_a11y_tree=False
            )
            self.env.reset()


    # ------------------------------------------------------------------
    def execute(self, action: Action) -> str | None:
        if not self.supports(type(action)):
            raise NotImplementedError(f"{type(action).__name__} not supported by PyAutoGUIBackend")
        
        # For automation OSWorld evaluation
        if self.use_precreate_vm is None: 
            if isinstance(action, Click):
                return self._click(action)
            elif isinstance(action, DoubleClick):
                return self._doubleClick(action)
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
        
        # For cli_app
        else:
            if isinstance(action, Click):
                action_pyautogui_code = self._click(action)
            elif isinstance(action, DoubleClick):
                action_pyautogui_code = self._doubleClick(action)
            elif isinstance(action, Move):
                action_pyautogui_code = self._move(action)
            elif isinstance(action, Scroll):
                action_pyautogui_code = self._scroll(action)
            elif isinstance(action, Drag):
                action_pyautogui_code = self._drag(action)
            elif isinstance(action, TypeText):
                action_pyautogui_code = self._type(action)
            elif isinstance(action, Hotkey):
                action_pyautogui_code = self._hotkey(action)
            elif isinstance(action, Screenshot):
                screenshot = self._screenshot()
                return screenshot # type: ignore
            elif isinstance(action, Wait):
                action_pyautogui_code = f"WAIT"
            elif isinstance(action, Done):
                action_pyautogui_code = f"DONE"
            elif isinstance(action, Failed):
                action_pyautogui_code = f"FAIL"
            else:
                # This shouldn't happen due to supports() check, but be safe.
                raise NotImplementedError(f"Unhandled action: {action}")

            self.env.step(action_pyautogui_code)

    # ----- individual helpers ------------------------------------------------
    def _click(self, act: Click) -> str:
        button_str = 'primary'
        if act.button == 1:
            button_str = "left"
        elif act.button == 4:
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

    def _doubleClick(self, act: DoubleClick) -> str:
        
        button_str = 'primary'
        if act.button == 1:
            button_str = "left"
        elif act.button == 4:
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

    def _move(self, act: Move) -> str:
        code_parts = []
        for k in act.holdKey or []:
            code_parts.append(f"pyautogui.keyDown('{k}')")
            code_parts.append(f"time.sleep(0.05)")
        code_parts.append(f"pyautogui.moveTo(x = {act.x}, y = {act.y})")
        for k in act.holdKey or []:
            code_parts.append(f"pyautogui.keyUp('{k}')")
        return "; ".join(code_parts)

    def _scroll(self, act: Scroll) -> str:
        code_parts = []
        code_parts.append(f"pyautogui.moveTo(x = {act.x}, y = {act.y})")
        if act.stepVertical is None:
            if act.stepHorizontal is not None:
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
        code_parts.append("time.sleep(0.1)")

        code_parts.append(f"pyautogui.mouseDown(button='left')")
        code_parts.append("time.sleep(0.2)")

        code_parts.append(f"pyautogui.moveTo(x = {act.endX}, y = {act.endY}, duration=0.5)")
        code_parts.append("time.sleep(0.1)")

        code_parts.append(f"pyautogui.mouseUp(button='left')")

        for k in hold_keys:
            code_parts.append(f"pyautogui.keyUp('{k}')")
        return "; ".join(code_parts)

    def _type(self, act: TypeText) -> str:
        code_parts = []
        code_parts.append(f"pyautogui.write('{act.text}')")
        return "; ".join(code_parts)

    def _hotkey(self, act: Hotkey) -> str:
        code_parts = []
        if act.duration is not None:
            for k in act.keys or []:
                code_parts.append(f"pyautogui.keyDown('{k}')")
                code_parts.append(f"time.sleep({act.duration} * 1e-3)")
            for k in reversed(act.keys):
                code_parts.append(f"pyautogui.keyUp('{k}')")
        else:
            keys_str = "', '".join(act.keys)
            code_parts.append(f"pyautogui.hotkey('{keys_str}', interval=0.1)")
        return "; ".join(code_parts)
    
    def _screenshot(self) -> str:
        if self.use_precreate_vm is None:
            return "screenshot = pyautogui.screenshot(); return screenshot"
        else:
            obs = self.env._get_obs()
            return screenshot_bytes_to_pil_image(obs["screenshot"])
