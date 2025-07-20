from desktop_env.desktop_env import DesktopEnv
from screenshot_converter import process_vmware_screenshot

example = {
    "id": "94d95f96-9699-4208-98ba-3c3119edf9c2",
    "instruction": "I want to install Spotify on my current system. Could you please help me?",
    "config": [
        {
            "type": "execute",
            "parameters": {
                "command": [
                    "python",
                    "-c",
                    "import pyautogui; import time; pyautogui.click(960, 540); time.sleep(0.5);"
                ]
            }
        }
    ],
    "evaluator": {
        "func": "check_include_exclude",
        "result": {
            "type": "vm_command_line",
            "command": "which spotify"
        },
        "expected": {
            "type": "rule",
            "rules": {
                "include": ["spotify"],
                "exclude": ["not found"]
            }
        }
    }
}

env = DesktopEnv(path_to_vm="/Users/lxguo/Documents/Code/lybicguiagents/vmware_vm_data/Ubuntu0/Ubuntu0.vmx", provider_name="vmware", action_space="pyautogui")

env.reset(task_config=example)

obs = env._get_obs()  # Get the initial observation
    
print(f"+="*40)
print(type(obs["screenshot"]))
print(type(obs["instruction"]))
print(f"+="*40)

# Convert screenshot bytes to 1920x1080 image using the converter
result = process_vmware_screenshot(obs["screenshot"])

if result["success"]:
    print(f"Screenshot conversion successful!")
    print(f"Resized to: {result['resized_size']}")
    print(f"Saved as: {result['saved_file']}")
    print(f"Image bytes length: {result['image_bytes_length']}")
    
    # You can access the PIL Image object if needed
    pil_image = result["image_object"]
    print(f"PIL Image mode: {pil_image.mode}")
else:
    print(f"Screenshot conversion failed: {result['message']}")

# Test completed successfully
print("\nTest completed! Screenshot converted and saved successfully.")

obs, reward, done, info = env.step("pyautogui.rightClick()")