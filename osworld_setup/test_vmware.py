import os
from desktop_env.desktop_env import DesktopEnv

# To ensure the relative path works correctly, this script should be executed from the root of the project directory.
# For example: python osworld_setup/test_vmware.py
# The path is relative to the project root.

# # Step 1. put zip in the vmware_vm_data/, and use this code. When the VMware is running this system, then stop python and the virtual machine
# env = DesktopEnv(provider_name="vmware", os_type="Windows", action_space="pyautogui")

# Step 2. use this code when the zip is already unziped to vmware_vm_data/Windows0 with .vmx file exists
# vm_path = os.path.join("vmware_vm_data", "Windows-x86", "Windows 10 x64.vmx")
vm_path = os.path.join("vmware_vm_data", "Ubuntu0", "Ubuntu0.vmx")
env = DesktopEnv(path_to_vm=vm_path, provider_name="vmware", action_space="pyautogui")

env.reset()

obs = env._get_obs()  # Get the initial observation
    
print(f"+="*40)
print(type(obs["screenshot"]))
print(type(obs["instruction"]))
print(f"+="*40)

obs, reward, done, info = env.step("pyautogui.rightClick()")