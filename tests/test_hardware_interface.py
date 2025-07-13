# run_actions_demo.py
from time import sleep
from gui_agents.s2.agents.hardware_interface import HardwareInterface
from gui_agents.s2.agents.Action import (
    Click, TypeText, Drag, Hotkey, Wait, Open
)

# -------------------------------------------------------------
dry_run = False          # ← True 时只打印，不执行
backend_kwargs = dict(   # 传给 PyAutoGUIBackend 的额外参数
    platform="win32",    # "darwin" / "linux" / "win32"，自动检测可删掉
    default_move_duration=0.05,
)

# 1. 构建动作序列
plan = [
    # Click(xy=(400, 300), element_description="点击输入框", num_clicks=1),
    # TypeText(text="Hello Action!", element_description="输入文字", press_enter=True),
    # Wait(time=0.5),
    # Drag(start=(400, 300), end=(800, 300), hold_keys=[],
    #      starting_description="拖起点", ending_description="拖终点"),
    # Hotkey(keys=["ctrl", "s"]),
    Open(app_or_filename='Maps')
]

# 2. 创建硬件接口
hwi = HardwareInterface(backend="pyautogui", **backend_kwargs)

# 3. 执行
if dry_run:
    print("Dry-run 模式，仅打印 Action：")
    for a in plan:
        print(a)
else:
    print("开始执行 Action 序列…")
    hwi.dispatch(plan)
    print("执行完毕")
