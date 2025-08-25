# pytest -s tests/test_hardware_interface_pyautogui.py
import platform
from time import sleep
import time
from gui_agents.maestro.hardware_interface import HardwareInterface
from gui_agents.maestro.Action import (
    Click, Hotkey, Screenshot, Wait, TypeText
)
import os
from desktop_env.desktop_env import DesktopEnv

current_platform = platform.system()

# if current_platform == "Ubuntu":
#     path_to_vm = os.path.join("vmware_vm_data", "Ubuntu0", "Ubuntu0.vmx")
#     test_config_base_dir = os.path.join("evaluation_examples", "examples")
#     test_all_meta_path = os.path.join("evaluation_examples", "test_tiny.json")
# elif current_platform == "Windows":
#     path_to_vm = os.path.join("vmware_vm_data", "Windows0", "Windows0.vmx")
#     test_config_base_dir = os.path.join("evaluation_examples", "examples_windows")
#     test_all_meta_path = os.path.join("evaluation_examples", "test_tiny_windows.json")
# else:
#     raise ValueError(f"USE_PRECREATE_VM={current_platform} is not supported. Please use Ubuntu or Windows.")

# -------------------------------------------------------------
dry_run = False          # ← True when only print, not execute


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
    #   "app_or_filename": "VS Code"
    # }

    # {
    #   "type": "SwitchApplications",
    #   "app_code": "VS Code"
    # }

    # {
    #   "type": "SetCellValues",
    #   "cell_values": [
    #     {
    #       "A1": "test1"
    #     }
    #   ],
    #   "app_name": "Sheet1.xlsx",
    #   "sheet_name": "Sheet1"
    # }

    {
      "type": "Hotkey",
      "keys": [
        "command",
        "space"
      ],
      "duration": 80
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

plan2 = [

    {
      "type": "TypeText",
      "text": "Finder"
    }

]

# 2. Create hardware interface
# hwi = HardwareInterface(backend="lybic", **backend_kwargs)

# env = DesktopEnv(
#     provider_name="vmware",
#     path_to_vm=path_to_vm,
#     action_space="pyautogui",
#     require_a11y_tree=False,
# )
# env.reset()

backend_kwargs = dict(   # Extra parameters passed to PyAutoGUIBackend
    # env_controller=env,
)
# hwi = HardwareInterface(
#     backend="pyautogui_vmware", 
#     platform = "Ubuntu",
#     **backend_kwargs
# )

current_platform = platform.system()

hwi = HardwareInterface(
    backend="pyautogui", 
    platform = current_platform,
    **backend_kwargs
)

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
    time.sleep(2)
    res = hwi.dispatchDict(plan2)

    # print(res)

    print("Execution completed")
