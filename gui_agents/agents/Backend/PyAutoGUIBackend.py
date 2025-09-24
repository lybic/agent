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
    Screenshot,
    SetCellValues,
    SwitchApplications,
    Open,
)

from gui_agents.agents.Backend.Backend import Backend
import time


class PyAutoGUIBackend(Backend):
    """Pure local desktop backend powered by *pyautogui*.

    Pros  : zero dependency besides Python & pyautogui.
    Cons  : Requires an active, visible desktop session (won't work headless).
    """

    _supported = {
        Click, DoubleClick, Move, Scroll, Drag, TypeText, Hotkey, Wait,
        Screenshot, SetCellValues, SwitchApplications, Open
    }

    # ¶ PyAutoGUI sometimes throws exceptions if mouse is moved to a corner.
    def __init__(self,
                 default_move_duration: float = 0.0,
                 platform: str | None = None):
        import pyautogui as pag  # local import to avoid hard requirement
        pag.FAILSAFE = False
        self.pag = pag
        self.default_move_duration = default_move_duration
        # ↙️ Critical patch: save platform identifier
        self.platform = (platform or sys.platform).lower()

    # ------------------------------------------------------------------
    def execute(self, action: Action) -> None:
        if not self.supports(type(action)):
            raise NotImplementedError(
                f"{type(action).__name__} not supported by PyAutoGUIBackend")

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
            return screenshot  # type: ignore
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
            button=button_str,  # type: ignore
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
        self.pag.moveTo(x=act.x, y=act.y)
        for k in act.holdKey or []:
            self.pag.keyUp(k)

    def _scroll(self, act: Scroll) -> None:
        self.pag.moveTo(x=act.x, y=act.y)
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

        else:  # Windows / Linux
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

    # ---- new helpers -------------------------------------------------------
    def _set_cell_values(self, act: SetCellValues) -> None:
        # Linux only; other platforms raise
        if self.platform.startswith("win"):
            raise RuntimeError(
                "SetCellValues is not supported on Windows in agents3 backend")

        try:
            import uno  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "LibreOffice UNO (pyuno) is required on Linux to SetCellValues"
            ) from e

        # Connect to running soffice with UNO socket; do not spawn here to keep backend side-effects minimal
        local_context = uno.getComponentContext()
        resolver = local_context.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", local_context)
        context = resolver.resolve(
            "uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext"
        )
        desktop = context.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", context)

        # Helper: detect Calc docs and pick by title
        def identify(component):
            try:
                if component.supportsService(
                        "com.sun.star.sheet.SpreadsheetDocument"):
                    return "Calc"
            except Exception:
                return None
            return None

        documents = []
        for i, component in enumerate(desktop.Components):
            try:
                title = component.Title
            except Exception:
                title = ""
            t = identify(component)
            documents.append((i, component, title, t))

        spreadsheet_docs = [d for d in documents if d[3] == "Calc"]
        if not spreadsheet_docs:
            raise RuntimeError("No LibreOffice Calc document found via UNO")

        target = next((d for d in spreadsheet_docs if d[2] == act.app_name),
                      spreadsheet_docs[0])
        spreadsheet = target[1]
        try:
            sheet = spreadsheet.Sheets.getByName(act.sheet_name)
        except Exception as e:
            raise RuntimeError(
                f"Sheet '{act.sheet_name}' not found in '{act.app_name}'"
            ) from e

        # Apply cell values
        def cell_ref_to_indices(cell_ref: str):
            column_letters = ''.join(ch for ch in cell_ref if ch.isalpha())
            row_number = ''.join(ch for ch in cell_ref if ch.isdigit())
            col = sum((ord(c.upper()) - ord('A') + 1) * (26**idx)
                      for idx, c in enumerate(reversed(column_letters))) - 1
            row = int(row_number) - 1
            return col, row

        for ref, value in act.cell_values.items():
            try:
                col, row = cell_ref_to_indices(ref)
            except Exception:
                continue
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
            elif value is None:
                cell.clearContents(0)
            else:
                cell.String = str(value)

    def _switch_applications(self, act: SwitchApplications) -> None:
        # Use platform-specific flows similar to s2.5 but via pyautogui/OS tools
        if self.platform.startswith("darwin"):
            self.pag.hotkey('command', 'space')
            time.sleep(0.5)
            self.pag.typewrite(act.app_code)
            self.pag.press('enter')
            time.sleep(1.0)
        elif self.platform.startswith("linux"):
            # Use wmctrl to focus window with closest title
            try:
                out = subprocess.check_output(['wmctrl', '-lx'
                                              ]).decode('utf-8').splitlines()
            except Exception:
                # fallback: Super key to open launcher
                self.pag.hotkey('win')
                time.sleep(0.5)
                self.pag.typewrite(act.app_code)
                time.sleep(1.0)
                self.pag.press('enter')
                return
            import difflib
            titles = [line.split(None, 4)[2] for line in out]
            matches = difflib.get_close_matches(act.app_code,
                                                titles,
                                                n=1,
                                                cutoff=0.1)
            if matches:
                match = matches[0]
                window_id = None
                for line in out:
                    if match in line:
                        window_id = line.split()[0]
                        break
                if window_id:
                    subprocess.run(['wmctrl', '-ia', window_id])
                    subprocess.run([
                        'wmctrl', '-ir', window_id, '-b',
                        'add,maximized_vert,maximized_horz'
                    ])
            else:
                # open via launcher
                self.pag.hotkey('win')
                time.sleep(0.5)
                self.pag.typewrite(act.app_code)
                time.sleep(1.0)
                self.pag.press('enter')
        else:
            # Windows or others: keep minimal behavior
            self.pag.hotkey('win')
            time.sleep(0.5)
            self.pag.typewrite(act.app_code)
            self.pag.press('enter')

    def _open(self, act: Open) -> None:
        if self.platform.startswith("linux"):
            self.pag.hotkey('win')
            time.sleep(0.5)
            self.pag.write(act.app_or_filename)
            time.sleep(1.0)
            self.pag.hotkey('enter')
            time.sleep(0.5)
        elif self.platform.startswith("darwin"):
            self.pag.hotkey('command', 'space')
            time.sleep(0.5)
            self.pag.typewrite(act.app_or_filename)
            self.pag.press('enter')
            time.sleep(1.0)
        else:
            # try generic behavior
            self.pag.hotkey('win')
            time.sleep(0.5)
            self.pag.typewrite(act.app_or_filename)
            self.pag.press('enter')
