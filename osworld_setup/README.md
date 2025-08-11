# OSWorld VMware Runner (osworld_setup)

A small set of scripts to run and debug OSWorld-style GUI benchmarks inside a VMware virtual machine.

## What's here

- **run.py**: Orchestrates end‑to‑end evaluation across example tasks. Spawns the VMware-backed `DesktopEnv`, runs `AgentSNormal` or `AgentSFast` based on mode selection, records videos, saves per‑step screenshots and trajectory.
- **lib_run_single.py**: Runs a single example loop. Dispatches actions via the hardware interface and logs per‑example details.
- **screenshot_converter.py**: Utility helpers to convert `obs["screenshot"]` bytes/base64 into PIL images or PNG bytes, with optional resizing.
- **test_vmware.py**: Minimal sanity check to boot a VM, take an initial observation, and run one action.

## Requirements

- VMware Fusion (macOS) or VMware Workstation (Windows/Linux)
- A VM that can be started via a `.vmx` file. Place it under `vmware_vm_data/` or provide an absolute path.
- Default VM paths based on platform:
  - Linux: `vmware_vm_data/Ubuntu0/Ubuntu0.vmx`
  - Windows: `vmware_vm_data/Windows-x86/Windows 10 x64.vmx`
- You can override with `--path_to_vm /absolute/path/to/your.vmx`.
- Ensure the VM can boot unattended and that GUI is reachable once started.

## Quick sanity check

Run from the project root so relative paths resolve correctly:

```bash
python lybicguiagents/osworld_setup/test_vmware.py
```

What it does:

- Boots the VM (path set in the file)
- Calls `env._get_obs()` and prints the types of `obs["screenshot"]` and `obs["instruction"]`
- Executes a right-click action as a smoke test

If you need to test a different VM, edit the `vm_path` in `test_vmware.py` or make it an absolute path.

## Run the benchmark

From the project root:

```bash
# Windows with normal agent mode
python osworld_setup/run.py \
  --platform windows \
  --agent_mode normal \
  --max_steps 100

# Linux with fast agent mode
python osworld_setup/run.py \
  --platform linux \
  --agent_mode fast \
  --max_steps 100

# Custom VM path
python osworld_setup/run.py \
  --platform windows \
  --agent_mode normal \
  --path_to_vm "/absolute/path/to/Windows 10 x64.vmx" \
  --result_dir ./results
```

## Agent Modes

- **normal**: Uses `AgentSNormal` - hierarchical planning with directed acyclic graph modeling for complex multi-step tasks
- **fast**: Uses `AgentSFast` - generates description-based plans with reflection, then grounds to precise coordinates for faster execution

## Platform Support

- **linux**: Automatically uses Linux VM path and test configurations
- **windows**: Automatically uses Windows VM path and test configurations

The platform parameter automatically sets:

- VM path (`--path_to_vm`)
- Test metadata path (`--test_all_meta_path`)

Useful flags:

- `--platform`: Target platform (linux or windows, default: windows)
- `--agent_mode`: Agent mode (normal or fast, default: normal)
- `--headless`: Start the VM in headless mode (if supported by your VMware setup)
- `--max_steps 50`: Cap steps per example
- `--sleep_after_execution 1.0`: Delay after each action (seconds)
- `--screen_width 1920 --screen_height 1080`: Target resolution for screenshots and agent perception
- `--test_all_meta_path`: Override default test metadata path
- `--domain <name>`: Restrict to a single domain (default runs all)

## CLI options (run.py)

- **--platform**: Target platform (`linux` | `windows`) - automatically sets VM and test paths (default: `windows`)
- **--agent_mode**: Agent execution mode (`normal` | `fast`) - selects agent type (default: `normal`)
- **--path_to_vm**: Override VM path (auto-set based on platform if not provided)
- **--headless**: Run in headless mode
- **--action_space**: Action backend (default: `pyautogui`)
- **--observation_type**: `screenshot` | `a11y_tree` | `screenshot_a11y_tree` | `som` (default: `screenshot`)
- **--screen_width/--screen_height**: Observation size (default: `1920x1080`)
- **--sleep_after_execution**: Seconds to wait after an action (default: `1.0`)
- **--max_steps**: Max steps per example (default: `50`)
- **--test_config_base_dir**: Root for example JSONs (default: `evaluation_examples`)
- **--domain**: Single domain to run (default: `all`)
- **--test_all_meta_path**: Override test metadata path (auto-set based on platform if not provided)
- **--result_dir**: Output directory (default: `./results`)
- **--kb_name**: Knowledge base name (default: `kb_s2`)

## Example Usage

```bash
# Windows platform with normal agent
python osworld_setup/run.py --platform windows --agent_mode normal --test_all_meta_path evaluation_examples/test_tiny_windows.json --max_steps 100

# Windows platform with fast agent
python osworld_setup/run.py --platform windows --agent_mode fast --test_all_meta_path evaluation_examples/test_tiny_windows.json --max_steps 100

# Linux platform with normal agent
python osworld_setup/run.py --platform linux --agent_mode normal --test_all_meta_path evaluation_examples/test_tiny.json --max_steps 100

# Linux platform with fast agent
python osworld_setup/run.py --platform linux --agent_mode fast --test_all_meta_path evaluation_examples/test_tiny.json --max_steps 100
```

## Outputs

- Logs under `runtime/vmrun_<timestamp>/`
  - Per‑run logs (`vmrun_normal.log`, `vmrun_debug.log`, etc.)
  - Per‑example subfolders with detailed logs (`example.log`, `example_debug.log`), cached screenshots, and state JSONs
- Results under `<result_dir>/<action_space>/<observation_type>/<domain>/<example_id>/`:
  - `step_<n>_<timestamp>.png`: Raw frame per step
  - `traj.jsonl`: Step‑by‑step actions, rewards, and info
  - `recording.mp4`: Screen recording
  - `result.txt`: Final scalar metric for the example

## Screenshot conversion utilities

Examples using `screenshot_converter.py`:

```python
from lybicguiagents.osworld_setup.screenshot_converter import (
    convert_screenshot_to_image, save_screenshot_as_png, screenshot_to_bytes,
)

# Convert obs["screenshot"] (bytes or base64) to PIL.Image at 1920x1080
image = convert_screenshot_to_image(obs["screenshot"], target_size=(1920, 1080))

# Save as PNG
save_screenshot_as_png(obs["screenshot"], filename="screenshot.png", target_size=(1920, 1080))

# Get PNG bytes
png_bytes = screenshot_to_bytes(obs["screenshot"], target_size=(1920, 1080), format="PNG")
```

## Tips & troubleshooting

- **Cannot boot VM / path not found**: Pass `--path_to_vm` with an absolute path to your `.vmx` file.
- **Blank or invalid screenshot**: Give the VM more time to settle, or increase `--sleep_after_execution`. Make sure VMware Tools/Display drivers are installed inside the guest OS.
- **No outputs**: Check `runtime/vmrun_*` logs for exceptions. Ensure the project is installed (`pip install -e .`) and run from the repository root.
- **Headless mode**: Not all VMware setups support headless reliably; try without `--headless` if you see startup errors.
