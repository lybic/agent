# pytest -s tests/test_hardware_interface.py
import platform
from time import sleep
import time
from gui_agents.s2.agents.hardware_interface import HardwareInterface
from gui_agents.s2.agents.Action import (
    Click, TypeText, Drag, Hotkey, Wait, Open
)



current_platform = platform.system().lower()

# -------------------------------------------------------------
dry_run = False          # ← True 时只打印，不执行
backend_kwargs = dict(   # 传给 PyAutoGUIBackend 的额外参数
    platform=current_platform,    # "darwin" / "linux" / "win32"，自动检测可删掉
    default_move_duration=0.05,
)

# # 1. 构建动作序列
# plan = [
#     # Click(xy=(400, 300), element_description="点击输入框", num_clicks=1),
#     # TypeText(text="Hello Action!", element_description="输入文字", press_enter=True),
#     # Wait(time=0.5),
#     # Drag(start=(400, 300), end=(800, 300), hold_keys=[],
#     #      starting_description="拖起点", ending_description="拖终点"),
#     # Hotkey(keys=["ctrl", "s"]),
#     # Open(app_or_filename='maps')
#     Hotkey(keys=["command", "space"]),
#     TypeText(text="测试", element_description="", press_enter=True)
# ]

plan = [
    {'type': 'Click', 'xy': [154, 64], 'element_description': 'The Chromium browser icon on the desktop, which is a circular icon with red, green, yellow, and blue colors', 'num_clicks': 2, 'button_type': 'left', 'hold_keys': []}
]

# 2. 创建硬件接口
hwi = HardwareInterface(backend="pyautogui_vmware", **backend_kwargs)

# 3. 执行
if dry_run:
    print("Dry-run 模式，仅打印 Action：")
    for a in plan:
        print(a)
else:
    print("开始执行 Action 序列…")
    # hwi.dispatch(plan)
    res = hwi.dispatchDict(plan)
    print(res)

    print("执行完毕")
