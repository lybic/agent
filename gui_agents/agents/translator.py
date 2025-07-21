# translator.py
"""
把 pyautogui-风格脚本翻译成统一命令(JSON list)，
格式完全遵循 computer-use schema。
"""

from __future__ import annotations
import ast, json
from typing import List, Dict


class TranslateError(RuntimeError):
    ...


class _CommandBuilder(ast.NodeVisitor):
    """
    只处理最常见的 GUI 原子操作：
        click / moveTo / doubleClick / rightClick / middleClick /
        dragTo / scroll / typewrite / press / hotkey / wait
    若遇到条件、循环等逻辑，直接抛错（Grounding 层应先拆平）。
    """
    def __init__(self) -> None:
        super().__init__()
        self.cmds: List[Dict] = []

    # ---------- 节点访问 ----------
    def visit_Expr(self, node):         # pyautogui.xxx(...)
        if not isinstance(node.value, ast.Call):
            raise TranslateError("只允许函数调用级指令")
        self._handle_call(node.value)
        self.generic_visit(node)

    # ---------- 核心：把函数调用映射到 command ----------
    def _handle_call(self, call: ast.Call):
        if not isinstance(call.func, ast.Attribute):
            raise TranslateError("不支持复杂表达式")
        lib, fn = self._split_attr(call.func) # type: ignore
        if lib != "pyautogui":
            raise TranslateError("只允许 pyautogui 调用")

        # 取位置与关键字实参
        kw = {k.arg: self._literal(v) for k, v in zip(call.keywords, [k.value for k in call.keywords])}
        pos = [self._literal(a) for a in call.args]

        # ---------- mapping ----------
        if fn in {"click", "doubleClick", "rightClick", "middleClick"}:
            x, y = pos[:2] if len(pos) >= 2 else (kw.get("x"), kw.get("y"))
            self._append_click(fn, x, y, kw)

        elif fn == "moveTo":
            x, y = pos[:2] if len(pos) >= 2 else (kw.get("x"), kw.get("y"))
            self.cmds.append({"action": "move", "coordinate": [x, y]})

        elif fn == "dragTo":
            x, y = pos[:2] if len(pos) >= 2 else (kw.get("x"), kw.get("y"))
            # startCoordinate 需由调用方补充；这里用 None 占位
            self.cmds.append({"action": "leftClickDrag",
                              "startCoordinate": None,
                              "coordinate": [x, y]})

        elif fn == "scroll":
            clicks = pos[0] if pos else kw.get("clicks")
            direction = "up" if clicks > 0 else "down"
            coordinate = [kw.get("x", 0), kw.get("y", 0)]
            self.cmds.append({"action": "scroll",
                              "scrollAmount": abs(clicks),
                              "scrollDirection": direction,
                              "coordinate": coordinate})

        elif fn in {"typewrite", "write"}:
            text = pos[0] if pos else kw.get("message")
            self.cmds.append({"action": "type", "text": text})

        elif fn in {"press", "hotkey"}:
            keys = [self._literal(a) for a in call.args]
            key_combo = "+".join(keys)
            self.cmds.append({"action": "keyPress", "text": key_combo})

        elif fn == "sleep":
            secs = pos[0] if pos else kw.get("seconds", 1)
            self.cmds.append({"action": "wait", "duration": secs})

        else:
            raise TranslateError(f"暂不支持函数 {fn}")

    # ---------- 工具 ----------
    def _append_click(self, fn, x, y, kw):
        # 单击 / 双击 / 不同按键
        clicks = kw.get("clicks", 1)
        button = kw.get("button", "left")
        action = {
            ("click", 1, "left"): "click",
            ("click", 2, "left"): "doubleClick",
            ("doubleClick", 1, "left"): "doubleClick",
            ("rightClick", 1, "right"): "rightClick",
            ("middleClick", 1, "middle"): "middleClick",
        }.get((fn, clicks, button))
        if not action:
            raise TranslateError(f"无法映射 {fn} clicks={clicks} button={button}")
        self.cmds.append({"action": action, "coordinate": [x, y]})

    def _split_attr(self, attr: ast.Attribute):
        parts = []
        while isinstance(attr, ast.Attribute):
            parts.insert(0, attr.attr)
            attr = attr.value # type: ignore
            if isinstance(attr, ast.Name):
                parts.insert(0, attr.id)
            else:
                raise TranslateError("不支持复杂表达式")
        return parts[0], parts[1]

    def _literal(self, node):
        if isinstance(node, ast.Constant):
            return node.value
        raise TranslateError("只允许字面量参数")

# ---------- 对外 API ----------
def translate(py_code: str) -> List[Dict]:
    tree = ast.parse(py_code)
    builder = _CommandBuilder()
    builder.visit(tree)
    return builder.cmds


# ---------------- demo ----------------
# if __name__ == "__main__":
#     sample = "import pyautogui; pyautogui.click(769, 1006, clicks=1, button='left');"
#     cmds = translate(sample)
#     print(json.dumps(cmds, indent=2, ensure_ascii=False))
