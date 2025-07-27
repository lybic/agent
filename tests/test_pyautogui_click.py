from gui_agents.agents.Action import Click
from gui_agents.agents.hardware_interface import HardwareInterface
import time

if __name__ == "__main__":
    # 初始化HardwareInterface，使用pyautogui后端
    hwi = HardwareInterface(backend="pyautogui")
    # 获取屏幕分辨率
    import pyautogui
    # 构造点击操作
    # click_action = Click(x=565, y=1905, element_description ='')
    click_action = {
        "type": "Click",
        "x": 282, # int
        "y": 952, # int
        "element_description": "", # str
        "button": 1,
        "holdKey": []
    }
    # 执行点击
    try:
        hwi.dispatchDict(click_action)
        print(f"已在屏幕中央({565},{1905})点击一次。")
    except Exception as e:
        print(f"点击失败: {e}") 

import pyautogui

# 屏幕分辨率
screen_width, screen_height = pyautogui.size()
print(f"屏幕分辨率: {screen_width}x{screen_height}")

# 截图分辨率
img = pyautogui.screenshot()
print(f"截图分辨率: {img.width}x{img.height}")

scale_x = screen_width / img.width
scale_y = screen_height / img.height

# 例如要点击(565, 1905)的物理坐标
real_x = int(565 * scale_x)
real_y = int(1905 * scale_y)

print(f"映射后点击坐标: ({real_x}, {real_y})")
# 然后用real_x, real_y去点击 