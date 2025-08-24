# ---------------------------------------------------------------------------
# 1) Desktop automation backend (PyAutoGUI)
# ---------------------------------------------------------------------------
import os
import subprocess, difflib
import sys
import pyperclip
from PIL import Image
from numpy import imag
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
    Screenshot,
    SetCellValues,
    SwitchApplications,
    Open
)

from gui_agents.maestro.Backend.Backend import Backend
import time


class PyAutoGUIBackend(Backend):
    """Pure local desktop backend powered by *pyautogui*.

    Pros  : zero dependency besides Python & pyautogui.
    Cons  : Requires an active, visible desktop session (won't work headless).
    """

    _supported = {Click, DoubleClick, Move, Scroll, Drag, TypeText, Hotkey, Wait, Screenshot, SetCellValues, SwitchApplications, Open}

    # ¶ PyAutoGUI sometimes throws exceptions if mouse is moved to a corner.
    def __init__(self, default_move_duration: float = 0.0, platform: str | None = None, **kwargs):
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
        elif isinstance(action, SetCellValues):
            self._set_cell_values(action)
        elif isinstance(action, SwitchApplications):
            self._switch_applications(action)
        elif isinstance(action, Open):
            self._open(action)
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

    def _set_cell_values(self, act: SetCellValues) -> None:
        """Set cell values in LibreOffice Calc (Linux only)"""
        if self.platform.startswith("linux"):
            # Use subprocess to execute LibreOffice automation
            import subprocess
            import tempfile
            import os
            
            # Create a temporary Python script with the cell values
            script_content = f"""
import uno
import subprocess

def set_cell_values(new_cell_values, app_name, sheet_name):
    # Clean up previous TCP connections
    subprocess.run('echo "password" | sudo -S ss --kill --tcp state TIME-WAIT sport = :2002', 
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
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(script_content)
                temp_script = f.name
            
            try:
                subprocess.run(['python3', temp_script], check=True)
            finally:
                os.unlink(temp_script)
        else:
            raise NotImplementedError(f"SetCellValues not supported on platform: {self.platform}")

    def _switch_applications(self, act: SwitchApplications) -> None:
        """Switch to a different application that is already open"""
        if self.platform.startswith("darwin"):
            # macOS: Command+Space to open Spotlight, then type app name
            self.pag.hotkey("command", "space", interval=0.5)
            time.sleep(0.5)
            self.pag.typewrite(act.app_code)
            time.sleep(1.0)
            self.pag.press("enter")
            time.sleep(1.0)
        elif self.platform.startswith("linux"):
            # Linux: Use wmctrl to switch windows
            import subprocess
            import difflib
            
            self.pag.press("escape")
            time.sleep(0.5)
            
            try:
                output = subprocess.check_output(['wmctrl', '-lx']).decode('utf-8').splitlines()
                window_titles = [line.split(None, 4)[2] for line in output]
                closest_matches = difflib.get_close_matches(act.app_code, window_titles, n=1, cutoff=0.1)
                
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
            except (subprocess.SubprocessError, IndexError):
                # Fallback to Alt+Tab if wmctrl fails
                self.pag.hotkey("alt", "tab")
        elif self.platform.startswith("win"):
            # Windows: Win+D to show desktop, then type app name
            self.pag.hotkey("win", "d", interval=0.5)
            time.sleep(0.5)
            self.pag.typewrite(act.app_code)
            time.sleep(1.0)
            self.pag.press("enter")
            time.sleep(1.0)
        else:
            raise NotImplementedError(f"SwitchApplications not supported on platform: {self.platform}")

    def _open(self, act: Open) -> None:
        """Open an application or file"""
        if self.platform.startswith("darwin"):
            # macOS: Command+Space to open Spotlight
            self.pag.hotkey("command", "space", interval=0.5)
            time.sleep(0.5)
            self.pag.typewrite(act.app_or_filename)
            time.sleep(1.0)
            self.pag.press("enter")
            time.sleep(0.5)
        elif self.platform.startswith("linux"):
            # Linux: Win key to open application menu
            self.pag.press("super")
            time.sleep(0.5)
            self.pag.typewrite(act.app_or_filename)
            time.sleep(1.0)
            self.pag.press("enter")
            time.sleep(0.5)
        elif self.platform.startswith("win"):
            # Windows: Win+R to open Run dialog
            self.pag.hotkey("win", "r", interval=0.5)
            time.sleep(0.5)
            self.pag.typewrite(act.app_or_filename)
            time.sleep(1.0)
            self.pag.press("enter")
            time.sleep(1.0)
        else:
            raise NotImplementedError(f"Open not supported on platform: {self.platform}")