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
    Open,
    SwitchApp
)

from gui_agents.s2.agents.Backend import Backend
import time


class PyAutoGUIBackend(Backend):
    """Pure local desktop backend powered by *pyautogui*.

    Pros  : zero dependency besides Python & pyautogui.
    Cons  : Requires an active, visible desktop session (won't work headless).
    """

    _supported = {Click, Drag, TypeText, Scroll, Hotkey, HoldAndPress, Wait, Open, SwitchApp}

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
        elif isinstance(action, Open):
            self._open_app(action)
        elif isinstance(action, SwitchApp):
            self._switch_app(action)
        elif isinstance(action, Wait):
            time.sleep(action.time)
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
            clicks=act.num_clicks,
            button=act.button_type.name.lower(),
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

    # ----- NEW: application helpers -----------------------------------------
    def _switch_app(self, act: SwitchApp) -> None:
        """跨平台切换到已打开的指定应用窗口"""
        code = act.app_code
        if self.platform.startswith("darwin"):          # macOS
            self.pag.hotkey("command", "space")
            time.sleep(0.5)
            self.pag.typewrite(code)
            self.pag.press("enter")
            time.sleep(1.0)

        elif self.platform.startswith("linux"):         # X11 + wmctrl
            try:
                output = subprocess.check_output(["wmctrl", "-lx"]).decode("utf-8").splitlines()
                titles = [line.split(None, 4)[2] for line in output]
                matches = difflib.get_close_matches(code, titles, n=1, cutoff=0.1)
                if matches:
                    target = matches[0]
                    win_id = next((line.split()[0] for line in output if target in line), None)
                    if win_id:
                        subprocess.run(["wmctrl", "-ia", win_id])
                        subprocess.run(["wmctrl", "-ir", win_id, "-b", "add,maximized_vert,maximized_horz"])
            except FileNotFoundError:
                # wmctrl 未安装时退化到 Alt+Tab
                self.pag.keyDown("alt")
                self.pag.press("tab")
                self.pag.keyUp("alt")

        else:                                           # Assume Windows
            self.pag.hotkey("win", "d")
            time.sleep(0.5)
            self.pag.typewrite(code)
            self.pag.press("enter")
            time.sleep(1.0)

    def _open_app(self, act: Open) -> None:
        """在当前系统中打开应用 / 文件"""
        target = act.app_or_filename
        if self.platform.startswith("darwin"):
            self.pag.hotkey("command", "space")
            time.sleep(0.4)
            self.pag.write(target)
            self.pag.press("enter")
        elif self.platform.startswith("linux"):
            # Alt+F2 launcher（大部分桌面环境适用）
            self.pag.hotkey("alt", "f2")
            time.sleep(0.4)
            self.pag.write(target)
            self.pag.press("enter")
        else:  # Windows
            self.pag.hotkey("win")
            time.sleep(0.5)
            self.pag.write(target)
            time.sleep(1.0)
            self.pag.press("enter")
            time.sleep(0.5)
