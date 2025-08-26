#!/usr/bin/env python3
"""
Debug helper: restore MainController from a snapshot and optionally run it.
"""

import argparse
import logging
from typing import Optional

from gui_agents.maestro.snapshot_restorer import (
    restore_maincontroller_from_globalstate,
)

logger = logging.getLogger(__name__)


def run_main_controller_from_snapshot(
    runtime_dir: str,
    snapshot_id: Optional[str] = None,
    target_dir: Optional[str] = None,
):
    """
    Restore a MainController from an existing snapshot and optionally run it.

    Args:
        runtime_dir: Path to the runtime directory (e.g., "runtime/20250826_141730")
        snapshot_id: Snapshot ID (e.g., "snapshot_20250826_141736"); if None, interactive selection
        target_dir: Restore target directory; if None, it will be generated automatically
        auto_run: Whether to immediately execute the main loop

    Returns:
        The restored MainController if successful; otherwise None.
    """
    controller = restore_maincontroller_from_globalstate(
        runtime_dir=runtime_dir,
        snapshot_id=snapshot_id,
        target_dir=target_dir,
    )

    if controller is None:
        logger.error("Failed to restore MainController from snapshot")
        return None

    logger.info("MainController restored from snapshot successfully")

    controller.execute_main_loop()

    # if auto_run:
    #     logger.info("Starting main loop execution…")
    #     controller.execute_main_loop()
    #     logger.info("Main loop execution finished")

    return controller


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MainController from snapshot")
    parser.add_argument("runtime_dir", type=str, help="Path to runtime directory")
    parser.add_argument("--snapshot", "-s", type=str, default=None, help="Snapshot ID")
    parser.add_argument("--target", "-t", type=str, default=None, help="Restore target directory")
    parser.add_argument("--no-run", action="store_true", help="Do not auto-run main loop")
    return parser.parse_args()


if __name__ == "__main__":
    # args = _parse_args()

    target_dir=None
    runtime_dir = "runtime/20250826_141730"
    snapshot_id = "snapshot_20250826_141736"

    run_main_controller_from_snapshot(
        runtime_dir=runtime_dir,
        snapshot_id=snapshot_id,
        target_dir=target_dir,
    ) 