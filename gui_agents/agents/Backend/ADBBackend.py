# ---------------------------------------------------------------------------
# 2) Android device backend (ADB)
# ---------------------------------------------------------------------------
from gui_agents.agents.Action import (
    Action,
    Click,
    Drag,
    TypeText,
    Scroll,
    Hotkey,
    Wait,
)

from gui_agents.agents.Backend.Backend import Backend
import time
import subprocess

class ADBBackend(Backend):
    """Very light‑weight ADB backend (tap / swipe / text / keyevent)."""

    _supported = {Click, Drag, TypeText, Hotkey, Wait}

    def __init__(self, serial: str | None = None):
        self.serial = serial  # specify target device; None = default

    # ------------------------------------------------------------------
    def execute(self, action: Action) -> None:
        if not self.supports(type(action)):
            raise NotImplementedError

        prefix = ["adb"]
        if self.serial:
            prefix += ["-s", self.serial]
        prefix.append("shell")

        if isinstance(action, Click):
            cmd = prefix
            # cmd = prefix + ["input", "tap", str(action.xy[0]), str(action.xy[1])]
        elif isinstance(action, Drag):
            cmd = prefix + [
                "input", "swipe",
                # str(action.start[0]), str(action.start[1]),
                # str(action.end[0]), str(action.end[1]),
                # str(int(action.duration * 1000)), # type: ignore
            ]
        elif isinstance(action, TypeText):
            text = action.text.replace(" ", "%s")  # escape spaces
            cmd = prefix + ["input", "text", text]
            # if action.press_enter:
            #     subprocess.run(prefix + ["input", "keyevent", "ENTER"], check=True)
            #     return
        elif isinstance(action, Hotkey):
            # Map first key for demo purposes
            key = action.keys[0].upper()
            cmd = prefix + ["input", "keyevent", key]
        elif isinstance(action, Wait):
            time.sleep(action.seconds) # type: ignore
            return
        else:
            raise NotImplementedError

        subprocess.run(cmd, check=True)
