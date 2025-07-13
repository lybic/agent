from unittest.mock import patch, call

from gui_agents.s2.agents.hardware_interface import HardwareInterface
# pytest -s tests/test_hardware_interface.py

# 构造一串典型命令序列
COMMANDS = [
    {"action": "click", "coordinate": [10, 20]},
    {"action": "doubleClick", "coordinate": [30, 40]},
    {"action": "move", "coordinate": [50, 60]},
    {"action": "type", "text": "test"},
    {"action": "keyPress", "text": "ctrl+s"},
    {"action": "wait", "duration": 0.1},
]


@patch("gui_agents.s2.agents.hardware_interface.pyautogui")
def test_run_success(mock_gui):
    """确保 HardwareInterface 能逐条调度到 pyautogui"""
    hi = HardwareInterface(backend="pyautogui")
    result = hi.run(COMMANDS)

    # 每条都 ok
    assert all(r["ok"] for r in result)

    # pyautogui 的调用顺序应与 COMMANDS 保持一致
    exp_calls = [
        call.click(10, 20),
        call.doubleClick(30, 40),
        call.moveTo(50, 60),
        call.typewrite("test"),
        call.hotkey("ctrl", "s"),
    ]
    mock_gui.assert_has_calls(exp_calls, any_order=False)


@patch("gui_agents.s2.agents.hardware_interface.pyautogui.click", side_effect=RuntimeError("click failed"))
def test_run_partial_failure(mock_click):
    """若其中一步失败，结果应正确标注错误而不抛异常"""
    hi = HardwareInterface(backend="pyautogui")
    commands = [{"action": "click", "coordinate": [1, 1]}]
    result = hi.run(commands)

    assert result == [{"ok": False, "error": "click failed"}]
