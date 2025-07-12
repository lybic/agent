# hardware_interface.py
"""
执行 Translator 产出的 command list。
目前支持 backend='pyautogui'；未来只需在 _exec_* 方法里换成 lybic_api 调用。
"""

from __future__ import annotations
import time, pyautogui
from typing import List, Dict, Callable


class HardwareInterfaceError(RuntimeError): ...


class HardwareInterface:
    def __init__(self, backend: str = "pyautogui"):
        backend = backend.lower()
        if backend not in {"pyautogui", "lybic"}:
            raise HardwareInterfaceError(f"Unsupported backend: {backend}")
        self.backend = backend
        self._dispatch: Dict[str, Callable[[Dict], None]] = {
            "click": self._exec_click,
            "doubleClick": self._exec_double,
            "rightClick": self._exec_right,
            "middleClick": self._exec_middle,
            "move": self._exec_move,
            "leftClickDrag": self._exec_drag,
            "scroll": self._exec_scroll,
            "type": self._exec_type,
            "keyPress": self._exec_key,
            "wait": self._exec_wait,
        }

    # ---------- 对外 ----------
    def run(self, commands: List[Dict]) -> List[Dict]:
        """
        顺序执行整个 command list
        returns 每条指令的 {"ok":bool, "error":str|None}
        """
        results = []
        for cmd in commands:
            try:
                self._dispatch[cmd["action"]](cmd)
                results.append({"ok": True, "error": None})
            except Exception as e:
                results.append({"ok": False, "error": str(e)})
        return results

    # ---------- backend=pyautogui 的具体实现 ----------
    def _exec_click(self, c):   pyautogui.click(*c["coordinate"])
    def _exec_double(self, c):  pyautogui.doubleClick(*c["coordinate"])
    def _exec_right(self, c):   pyautogui.rightClick(*c["coordinate"])
    def _exec_middle(self, c):  pyautogui.middleClick(*c["coordinate"])
    def _exec_move(self, c):    pyautogui.moveTo(*c["coordinate"])
    def _exec_drag(self, c):    pyautogui.dragTo(*c["coordinate"])
    def _exec_scroll(self, c):  pyautogui.scroll(
                                    c["scrollAmount"] * (1 if c["scrollDirection"]=="up" else -1),
                                    *c["coordinate"])
    def _exec_type(self, c):    pyautogui.typewrite(c["text"])
    def _exec_key(self, c):     pyautogui.hotkey(*c["text"].split("+"))
    def _exec_wait(self, c):    time.sleep(c["duration"])
