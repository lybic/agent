"""
极简 Translator 单元测试
-----------------------
- 不依赖任何 schema / 额外包
- 打印 translate() 输出，方便人工目视验证
"""

import pytest

from gui_agents.agents.translator import translate, TranslateError
# from  import translate, TranslateError


# ---------- 正向用例 ----------
@pytest.mark.parametrize(
    "src, exp",
    [
        (
            "import pyautogui; pyautogui.click(10, 20)",
            [{"action": "click", "coordinate": [10, 20]}],
        ),
        (
            "import pyautogui; pyautogui.doubleClick(30, 40)",
            [{"action": "doubleClick", "coordinate": [30, 40]}],
        ),
    ],
)
def test_translate_print(src, exp):
    cmds = translate(src)

    # 1. 打印到终端供人工查看
    print(f"\nsource: {src}\ncommands: {cmds}")

    # 2. 基本断言（可按需增删）
    assert cmds == exp
    assert isinstance(cmds, list)
    assert all(isinstance(c, dict) for c in cmds)

    # pytest -q 时仍能看到打印内容
    # captured = capsys.readouterr()
    # assert "commands:" in captured.out


# ---------- 负向用例 ----------
def test_translate_illegal_function():
    with pytest.raises(TranslateError):
        translate("import pyautogui; pyautogui.screenshot()")  # 未支持的方法
