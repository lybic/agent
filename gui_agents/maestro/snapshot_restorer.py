#!/usr/bin/env python3
"""
Snapshot Restore Tool - Restore snapshots and create GlobalState
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

# Add project root directory to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from gui_agents.maestro.simple_snapshot import SimpleSnapshot
from gui_agents.maestro.new_global_state import NewGlobalState
from gui_agents.maestro.controller.main_controller import MainController
from desktop_env.desktop_env import DesktopEnv


def _build_env_from_config(env_config: Dict[str, Any]) -> Optional[DesktopEnv]:
    """Rebuild DesktopEnv based on env configuration in snapshot. Returns None on failure."""
    try:
        if not env_config or not env_config.get("present"):
            return None

        provider_name = env_config.get("provider_name", "vmware")
        path_to_vm = env_config.get("path_to_vm")
        action_space = env_config.get("action_space", "pyautogui")
        headless = bool(env_config.get("headless", False))
        require_a11y_tree = bool(env_config.get("require_a11y_tree", False))
        os_type_value = env_config.get("os_type") or os.getenv("USE_PRECREATE_VM", "Windows")

        if not path_to_vm:
            # Cannot build when missing required VM path
            return None

        env = DesktopEnv(
            provider_name=provider_name,
            path_to_vm=path_to_vm,
            action_space=action_space,
            headless=headless,
            require_a11y_tree=require_a11y_tree,
            os_type=os_type_value,
        )
        # Call reset if needed to ensure internal state is ready
        try:
            env.reset()
        except Exception:
            pass
        return env
    except Exception:
        return None


def restore_snapshot_and_create_globalstate(runtime_dir: str, snapshot_id: Optional[str] = None, target_dir: Optional[str] = None):
    """
    Restore snapshot and create GlobalState
    
    Args:
        runtime_dir: Runtime directory path
        snapshot_id: Snapshot ID, if None then list all snapshots for selection
        target_dir: Target restore directory, if None then auto-generate
    """
    # Create snapshot system
    snapshot_system = SimpleSnapshot(runtime_dir)
    
    # If no snapshot ID specified, list all snapshots for selection
    if snapshot_id is None:
        snapshots = snapshot_system.list_snapshots()
        if not snapshots:
            print("❌ No snapshots found")
            return None, None, {}
        
        print("📋 Available snapshots:")
        for i, snapshot in enumerate(snapshots):
            print(f"  {i+1}. {snapshot['snapshot_id']}")
            print(f"     Description: {snapshot['description']}")
            print(f"     Type: {snapshot['type']}")
            print(f"     Time: {snapshot['timestamp']}")
            print()

    
    print(f"🔄 Restoring snapshot: {snapshot_id}")
    
    # Restore snapshot
    restore_result = snapshot_system.restore_snapshot(
        str(snapshot_id), target_dir
    )

    target_path = restore_result.get('target_directory')
    
    if not restore_result or not target_path:
        print("❌ Snapshot restore failed")
        return None, None, {}
    
    print(f"✅ Snapshot restore successful!")
    print(f"   Target directory: {target_path}")
    
    # Create GlobalState object
    try:
        # Build paths
        state_dir = Path(target_path) / "state"
        cache_dir = Path(target_path) / "cache"
        screens_dir = cache_dir / "screens"
        display_path = Path(target_path) / "display.json"
        
        # Ensure directories exist
        state_dir.mkdir(exist_ok=True)
        screens_dir.mkdir(parents=True, exist_ok=True)
        
        # Create GlobalState
        global_state = NewGlobalState(
            screenshot_dir=str(screens_dir),
            state_dir=str(state_dir),
            display_info_path=str(display_path)
        )
        
        print(f"🎉 GlobalState created successfully!")
        print(f"   Screenshot directory: {screens_dir}")
        print(f"   State directory: {state_dir}")
        print(f"   Display file: {display_path}")
        
        # Display configuration parameters
        config_params = restore_result.get("config_params", {})
        if config_params:
            print(f"\n📋 Snapshot configuration parameters:")
            print(f"   Platform: {config_params.get('platform', 'N/A')}")
            print(f"   Backend: {config_params.get('backend', 'N/A')}")
            print(f"   Max steps: {config_params.get('max_steps', 'N/A')}")
            print(f"   Search enabled: {config_params.get('enable_search', 'N/A')}")
            print(f"   Takeover enabled: {config_params.get('enable_takeover', 'N/A')}")
            print(f"   RAG enabled: {config_params.get('enable_rag', 'N/A')}")
        
        return global_state, target_path, config_params
        
    except Exception as e:
        print(f"❌ Failed to create GlobalState: {e}")
        return None, target_path, {}


def restore_maincontroller_from_globalstate(runtime_dir: str, snapshot_id: Optional[str] = None, target_dir: Optional[str] = None) -> Optional[Tuple[MainController, str, Dict[str, Any]]]:
    """
    Restore snapshot -> Build GlobalState -> Build MainController (skip initialization), and return controller, restore directory and configuration
    """
    global_state, target_path, config_params = restore_snapshot_and_create_globalstate(runtime_dir, snapshot_id, target_dir)
    if global_state is None:
        return None

    # Extract controller-related settings from configuration parameters (provide reasonable defaults)
    platform_value = config_params.get("platform", sys.platform)
    backend_value = config_params.get("backend", "pyautogui")
    enable_search_value = bool(config_params.get("enable_search", False))
    enable_takeover_value = bool(config_params.get("enable_takeover", False))
    enable_rag_value = bool(config_params.get("enable_rag", False))
    max_steps_value = int(config_params.get("max_steps", 50))
    env_password_value = config_params.get("env_password", "")

    # Protective check: target_path needs to be available
    if not target_path:
        print("❌ Unable to determine restore directory target_path")
        return None

    # Restore environment information: prioritize env configuration from snapshot
    env: Optional[DesktopEnv] = None
    try:
        env_config = config_params.get("env") or {}
        env = _build_env_from_config(env_config)
    except Exception as e:
        print(f"⚠️ Environment restore failed (will continue running without environment): {e}")
        env = None

    controller = MainController(
        platform=platform_value,
        enable_takeover=enable_takeover_value,
        enable_search=enable_search_value,
        enable_rag=enable_rag_value,
        backend=backend_value,
        user_query=(global_state.get_task().objective if hasattr(global_state, 'get_task') else ""),
        max_steps=max_steps_value,
        env=env,
        env_password=env_password_value,
        log_dir=str(Path(target_path)),
        datetime_str=Path(target_path).name,
        enable_snapshots=True,
        global_state=global_state,
        initialize_controller=False
    )

    print("✅ MainController restored from snapshot, ready to execute main loop")
    return controller, target_path, config_params



def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Snapshot restore tool")
    parser.add_argument("runtime_dir", help="Runtime directory path")
    parser.add_argument("--snapshot", "-s", help="Snapshot ID")
    parser.add_argument("--target", "-t", help="Target restore directory")
    parser.add_argument("--run", action="store_true", help="Run main loop immediately after restore")
    
    args = parser.parse_args()
    
    # Check if runtime directory exists
    if not Path(args.runtime_dir).exists():
        print(f"❌ Runtime directory does not exist: {args.runtime_dir}")
        return
    
    if args.run:
        result = restore_maincontroller_from_globalstate(args.runtime_dir, args.snapshot, args.target)
        if result is not None:
            controller, target_path, _ = result
            controller.execute_main_loop()
        return
    
    # Only restore snapshot and create GlobalState
    global_state, target_path, _ = restore_snapshot_and_create_globalstate(
        args.runtime_dir, args.snapshot, args.target
    )
    
    if global_state:
        print(f"\n🎯 Usage instructions:")
        print(f"   1. GlobalState object has been created and can be used directly")
        print(f"   2. Restored directory: {target_path}")
        print(f"   3. You can call global_state.get_task() and other methods to read information")
        print(f"   4. All state files have been restored to: {target_path}/state/")
        print(f"   5. Screenshots have been restored to: {target_path}/cache/screens/")
        print(f"   6. Call restore_maincontroller_from_globalstate(...).execute_main_loop() to continue execution")


if __name__ == "__main__":
    main()