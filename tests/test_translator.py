"""
Simple Translator unit test
-----------------------
- No dependency on any schema / extra package
- Print translate() output, for manual visual verification
"""

import pytest

from gui_agents.agents.translator import translate, TranslateError
# from  import translate, TranslateError


# ---------- Positive test case ----------
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

    # 1. Print to terminal for manual viewing
    print(f"\nsource: {src}\ncommands: {cmds}")

    # 2. Basic assertions (can be added or removed as needed)
    assert cmds == exp
    assert isinstance(cmds, list)
    assert all(isinstance(c, dict) for c in cmds)

    # pytest -q still能看到打印内容
    # captured = capsys.readouterr()
    # assert "commands:" in captured.out


# ---------- Negative test case ----------
def test_translate_illegal_function():
    with pytest.raises(TranslateError):
        translate("import pyautogui; pyautogui.screenshot()")  # Unsupported method
