# pytest -s tests/test_hardware_interface.py
import platform
from time import sleep
import time
from gui_agents.maestro.hardware_interface import HardwareInterface
from gui_agents.maestro.Action import (
    Click, Hotkey, Screenshot, Wait, TypeText
)



current_platform = platform.system().lower()

# -------------------------------------------------------------
dry_run = False          # ← True when only print, not execute
backend_kwargs = dict(   # Extra parameters passed to PyAutoGUIBackend
    platform=current_platform,    # "darwin" / "linux" / "win32", automatically detect can be removed
    default_move_duration=0.05,
)

# # 1. Build action sequence
# plan = [
#     Click(x=10, y=300, element_description=''),
#     # TypeText(text="Hello Action!"),
#     # Wait(time=0.5),
#     # Drag(start=(400, 300), end=(800, 300), hold_keys=[],
#     #      starting_description="拖起点", ending_description="拖终点"),
#     # Hotkey(keys=["ctrl", "s"]),
#     # Open(app_or_filename='maps')
#     # Screenshot()
#     # Hotkey(keys=["command", "space"]),
#     # TypeText(text="测试", element_description="", press_enter=True)
# ]

plan = [
    # {
    #   "type": "Open",
    #   "app_or_filename": "Finder"
    # }
    {
      "type": "SwitchApplications",
      "app_code": "Finder"
    }
    # {'type': 'Hotkey', 'keys': ['left'], 'duration': 80}
    # {
    #     "type": "Click",
    #     "x": 50,
    #     "y": 400,
    #     "button": 1,
    #     "holdKey": []
    # },
    # {
    #     "type": "TypeText",
    #     "text": "hello",
    # },
    # {'type': 'Click', 'xy': [154, 64], 'element_description': 'The Chromium browser icon on the desktop, which is a circular icon with red, green, yellow, and blue colors', 'num_clicks': 2, 'button_type': 'left', 'hold_keys': []}
]

# 2. Create hardware interface
# hwi = HardwareInterface(backend="lybic", **backend_kwargs)
hwi = HardwareInterface(backend="pyautogui", **backend_kwargs)

# 3. Execute
if dry_run:
    print("Dry-run mode, only print Action:")
    for a in plan:
        print(a)
else:
    print("Start executing Action sequence…")
    time.sleep(2)
    # hwi.dispatch(plan)
    res = hwi.dispatchDict(plan)
    # print(res)

    print("Execution completed")
