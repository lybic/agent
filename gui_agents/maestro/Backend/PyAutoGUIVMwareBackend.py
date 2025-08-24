# ---------------------------------------------------------------------------
# 1) Desktop automation backend (PyAutoGUI)
# ---------------------------------------------------------------------------
import os
import io
from PIL import Image
from typing import Optional
from desktop_env.desktop_env import DesktopEnv
from gui_agents.maestro.Action import (
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
    Screenshot,
    SetCellValues,
    SwitchApplications,
    Open
)

from gui_agents.maestro.Backend.Backend import Backend
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

    _supported = {Click, DoubleClick, Move, Scroll, Drag, TypeText, Hotkey, Wait, Done, Failed, Screenshot, SetCellValues, SwitchApplications, Open}

    # ¶ PyAutoGUI sometimes throws exceptions if mouse is moved to a corner.
    def __init__(self, default_move_duration: float = 0.0, platform: str | None = None, **kwargs):
        import pyautogui as pag  # local import to avoid hard requirement
        pag.FAILSAFE = False
        self.pag = pag
        self.default_move_duration = default_move_duration
        # Extract env_controller from kwargs if provided, but don't require it
        self.env_controller = kwargs.get('env_controller', None)


    # ------------------------------------------------------------------
    def execute(self, action: Action) -> str: # type: ignore
        if not self.supports(type(action)):
            raise NotImplementedError(f"{type(action).__name__} not supported by PyAutoGUIBackend")
        
        # For automation OSWorld evaluation
        if self.env_controller is None: 
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
            elif isinstance(action, SetCellValues):
                return self._set_cell_values(action)
            elif isinstance(action, SwitchApplications):
                return self._switch_applications(action)
            elif isinstance(action, Open):
                return self._open(action)
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
            elif isinstance(action, SetCellValues):
                action_pyautogui_code = self._set_cell_values(action)
            elif isinstance(action, SwitchApplications):
                action_pyautogui_code = self._switch_applications(action)
            elif isinstance(action, Open):
                action_pyautogui_code = self._open(action)
            else:
                # This shouldn't happen due to supports() check, but be safe.
                raise NotImplementedError(f"Unhandled action: {action}")

            self.env_controller.step(action_pyautogui_code)

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
        if self.env_controller is None:
            return "screenshot = pyautogui.screenshot(); return screenshot"
        else:
            obs = self.env_controller._get_obs()
            return screenshot_bytes_to_pil_image(obs["screenshot"]) #type: ignore

    def _set_cell_values(self, act: SetCellValues) -> str:
        """Set cell values in LibreOffice Calc (Linux only)"""
        if self.env_controller is None: # Assuming env_controller is self.env_controller
            return f"# SetCellValues not supported on platform: {self.env_controller.platform}" # type: ignore
        if self.env_controller.platform == "Ubuntu":
            # Create Python script for LibreOffice automation
            script_content = f"""
import uno
import subprocess

def set_cell_values(new_cell_values, app_name, sheet_name):
    # Clean up previous TCP connections
    subprocess.run('echo "osworld-public-evaluation" | sudo -S ss --kill --tcp state TIME-WAIT sport = :2002', 
                  shell=True, check=True, text=True, capture_output=True)
    
    # Start LibreOffice with socket connection
    subprocess.run(['soffice', '--accept=socket,host=localhost,port=2002;urp;StarOffice.Service'])
    
    local_context = uno.getComponentContext()
    resolver = local_context.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local_context
    )
    context = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
    desktop = context.ServiceManager.createInstanceWithContext(
        "com.sun.star.frame.Desktop", context
    )
    
    # Find the spreadsheet and set cell values
    for component in desktop.Components:
        if component.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
            if component.Title == app_name:
                sheet = component.Sheets.getByName(sheet_name)
                for cell_ref, value in new_cell_values.items():
                    # Convert cell reference to column/row indices
                    col_letters = ''.join(filter(str.isalpha, cell_ref))
                    row_number = ''.join(filter(str.isdigit, cell_ref))
                    
                    col = sum((ord(char.upper()) - ord('A') + 1) * (26**idx) for idx, char in enumerate(reversed(col_letters))) - 1
                    row = int(row_number) - 1
                    
                    cell = sheet.getCellByPosition(col, row)
                    if isinstance(value, (int, float)):
                        cell.Value = value
                    elif isinstance(value, str):
                        if value.startswith("="):
                            cell.Formula = value
                        else:
                            cell.String = value
                    elif isinstance(value, bool):
                        cell.Value = 1 if value else 0
                break

set_cell_values({act.cell_values}, "{act.app_name}", "{act.sheet_name}")
"""
            return script_content
        else:
            return f"# SetCellValues not supported on platform: {self.env_controller.platform}" # type: ignore

    def _switch_applications(self, act: SwitchApplications) -> str:
        """Switch to a different application that is already open"""
        if self.env_controller is None: # Assuming env_controller is self.env_controller
            return f"# SwitchApplications not supported on platform: {self.env_controller.platform}" # type: ignore
        if self.env_controller.platform == "Ubuntu":
            # Linux: Use wmctrl to switch windows
            return f"""
import subprocess
import difflib
import pyautogui
import time

pyautogui.press('escape')
time.sleep(0.5)

output = subprocess.check_output(['wmctrl', '-lx'])
output = output.decode('utf-8').splitlines()
window_titles = [line.split(None, 4)[2] for line in output]
closest_matches = difflib.get_close_matches('{act.app_code}', window_titles, n=1, cutoff=0.1)

if closest_matches:
    closest_match = closest_matches[0]
    for line in output:
        if closest_match in line:
            window_id = line.split()[0]
            break
    else:
        return
    
    subprocess.run(['wmctrl', '-ia', window_id])
    subprocess.run(['wmctrl', '-ir', window_id, '-b', 'add,maximized_vert,maximized_horz'])
"""
        elif self.env_controller.platform == "Windows":
            # Windows: Win+D to show desktop, then type app name
            return f"""
import pyautogui
import time

pyautogui.hotkey('win', 'd', interval=0.5)
time.sleep(0.5)
pyautogui.typewrite('{act.app_code}')
time.sleep(1.0)
pyautogui.press('enter')
time.sleep(1.0)
"""
        else:
            return f"# SwitchApplications not supported on platform: {self.env_controller.platform}"

    def _open(self, act: Open) -> str:
        """Open an application or file"""
        if self.env_controller is None: # Assuming env_controller is self.env_controller
            return f"# Open not supported on platform: {self.env_controller.platform}" # type: ignore
        if self.env_controller.platform == "Ubuntu":
            # Linux: Win key to open application menu
            return f"""
import pyautogui
import time

pyautogui.press('super')
time.sleep(0.5)
pyautogui.write('{act.app_or_filename}')
time.sleep(1.0)
pyautogui.hotkey('enter')
time.sleep(0.5)
"""
        elif self.env_controller.platform == "Windows":
            # Windows: Win+R to open Run dialog
            return f"""
import pyautogui
import time

pyautogui.hotkey('win', 'r', interval=0.5)
time.sleep(0.5)
pyautogui.typewrite('{act.app_or_filename}')
time.sleep(1.0)
pyautogui.press('enter')
time.sleep(1.0)
"""
        else:
            return f"# Open not supported on platform: {self.env_controller.platform}"
