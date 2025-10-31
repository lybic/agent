#!/usr/bin/env python3
"""
Test script for agent cancellation functionality in gui_agents/agents directory.
"""

import asyncio
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Dict, List

# Add the project root to Python path
project_root = Path(__file__).parent
os.environ["PYTHONPATH"] = str(project_root)

from gui_agents.agents.agent_s import AgentS2, AgentSFast, load_config
from gui_agents.agents.global_state import GlobalState
from gui_agents.store.registry import Registry
from gui_agents.utils.common_utils import Node
from PIL import Image
import io

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AgentCancellationTest:
    """Test class for agent cancellation functionality"""

    def __init__(self):
        self.test_results = []

    def create_mock_observation(self) -> Dict:
        """Create a mock observation for testing"""
        # Create a simple 100x100 black image
        img = Image.new('RGB', (100, 100), color='black')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        return {
            "screenshot": img_bytes.getvalue(),
            "termination_flag": "not_terminated"
        }

    def create_test_global_state(self):
        """Create a test GlobalState instance"""
        import tempfile
        import shutil

        # Create temporary directories for testing
        temp_dir = tempfile.mkdtemp()

        global_state = GlobalState(
            screenshot_dir=os.path.join(temp_dir, "screenshots"),
            tu_path=os.path.join(temp_dir, "tu.json"),
            search_query_path=os.path.join(temp_dir, "search_query.json"),
            completed_subtasks_path=os.path.join(temp_dir, "completed_subtasks.json"),
            failed_subtasks_path=os.path.join(temp_dir, "failed_subtasks.json"),
            remaining_subtasks_path=os.path.join(temp_dir, "remaining_subtasks.json"),
            termination_flag_path=os.path.join(temp_dir, "termination_flag.json"),
            running_state_path=os.path.join(temp_dir, "running_state.json"),
            agent_log_path=os.path.join(temp_dir, "agent_log.json"),
            display_info_path=os.path.join(temp_dir, "display.json"),
        )

        # Register the global state
        Registry.register("GlobalStateStore", global_state)

        return global_state, temp_dir

    def cleanup_test_directory(self, temp_dir: str):
        """Clean up test directory"""
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup test directory {temp_dir}: {e}")

    def test_agent_s2_cancellation(self):
        """Test AgentS2 cancellation functionality"""
        logger.info("=== Testing AgentS2 Cancellation ===")

        try:
            # Create test environment
            global_state, temp_dir = self.create_test_global_state()

            # Create AgentS2 instance
            agent = AgentS2(
                platform="windows",
                screen_size=[1920, 1080],
                memory_root_path=temp_dir,
                enable_takeover=False,
                enable_search=False,  # Disable search for simplicity
            )

            # Set a task ID for streaming
            task_id = str(uuid.uuid4())
            agent.set_task_id(task_id)

            # Create mock observation
            observation = self.create_mock_observation()

            # Test 1: Normal prediction (should work)
            logger.info("Test 1: Normal prediction without cancellation")
            instruction = "Click on the test element"
            info, actions = agent.predict(instruction, observation)
            assert actions is not None, "Actions should not be None"
            logger.info("✓ Normal prediction works")

            # Test 2: Prediction with cancellation
            logger.info("Test 2: Prediction with cancellation")
            global_state.set_running_state("cancelled")
            info, actions = agent.predict(instruction, observation)
            assert info["subtask_status"] == "cancelled", "Subtask status should be cancelled"
            assert len(actions) == 1 and actions[0]["type"] == "DONE", "Should return DONE action"
            logger.info("✓ Prediction correctly cancelled")

            # Reset for next test
            global_state.set_running_state("running")

            # Test 3: Multi-step cancellation during prediction loop
            logger.info("Test 3: Multi-step cancellation during prediction")
            # This test simulates cancellation happening during the prediction loop
            original_should_send_action = hasattr(agent, 'should_send_action')
            if original_should_send_action:
                agent.should_send_action = False

                # Set cancellation after a short delay
                def cancel_after_delay():
                    time.sleep(0.1)  # Small delay
                    global_state.set_running_state("cancelled")

                import threading
                cancel_thread = threading.Thread(target=cancel_after_delay)
                cancel_thread.start()

                info, actions = agent.predict(instruction, observation)
                assert info["subtask_status"] == "cancelled", "Prediction should be cancelled"
                cancel_thread.join()

            self.test_results.append(("AgentS2 Cancellation", True, "All tests passed"))

        except Exception as e:
            logger.error(f"AgentS2 cancellation test failed: {e}")
            self.test_results.append(("AgentS2 Cancellation", False, str(e)))

        finally:
            # Cleanup
            if 'temp_dir' in locals():
                self.cleanup_test_directory(temp_dir)

    def test_agent_s_fast_cancellation(self):
        """Test AgentSFast cancellation functionality"""
        logger.info("=== Testing AgentSFast Cancellation ===")

        try:
            # Create test environment
            global_state, temp_dir = self.create_test_global_state()

            # Create AgentSFast instance
            agent = AgentSFast(
                platform="windows",
                screen_size=[1920, 1080],
                memory_root_path=temp_dir,
                enable_takeover=False,
                enable_search=False,  # Disable search for simplicity
                enable_reflection=False,  # Disable reflection for simplicity
            )

            # Set a task ID for streaming
            task_id = str(uuid.uuid4())
            agent.set_task_id(task_id)

            # Create mock observation
            observation = self.create_mock_observation()

            # Test 1: Normal prediction (should work)
            logger.info("Test 1: Normal prediction without cancellation")
            instruction = "Click on the test element"
            info, actions = agent.predict(instruction, observation)
            assert actions is not None, "Actions should not be None"
            logger.info("✓ Normal prediction works")

            # Test 2: Prediction with cancellation
            logger.info("Test 2: Prediction with cancellation")
            global_state.set_running_state("cancelled")
            info, actions = agent.predict(instruction, observation)
            assert info["reflection"] == "Task was cancelled", "Reflection should indicate cancellation"
            assert len(actions) == 1 and actions[0]["type"] == "DONE", "Should return DONE action"
            logger.info("✓ Prediction correctly cancelled")

            self.test_results.append(("AgentSFast Cancellation", True, "All tests passed"))

        except Exception as e:
            logger.error(f"AgentSFast cancellation test failed: {e}")
            self.test_results.append(("AgentSFast Cancellation", False, str(e)))

        finally:
            # Cleanup
            if 'temp_dir' in locals():
                self.cleanup_test_directory(temp_dir)

    def test_manager_worker_cancellation(self):
        """Test Manager and Worker cancellation functionality"""
        logger.info("=== Testing Manager and Worker Cancellation ===")

        try:
            # Create test environment
            global_state, temp_dir = self.create_test_global_state()

            # Load tools configuration
            tools_config, tools_dict = load_config()

            # Create Manager instance
            from gui_agents.agents.manager import Manager
            manager = Manager(
                Tools_dict=tools_dict,
                local_kb_path=temp_dir,
                platform="windows",
                enable_search=False,  # Disable search for simplicity
            )

            # Create Worker instance
            from gui_agents.agents.worker import Worker
            worker = Worker(
                Tools_dict=tools_dict,
                local_kb_path=temp_dir,
                platform="windows",
                enable_reflection=False,  # Disable reflection for simplicity
                enable_search=False,  # Disable search for simplicity
            )

            # Create mock observation
            observation = self.create_mock_observation()

            # Test 1: Manager cancellation
            logger.info("Test 1: Manager cancellation")
            global_state.set_running_state("cancelled")

            planner_info, action_queue = manager.get_action_queue(
                Tu="Test instruction",
                observation=observation,
                running_state="running"
            )

            assert "cancelled" in planner_info, "Manager should return cancelled info"
            assert len(action_queue) == 0, "Action queue should be empty when cancelled"
            logger.info("✓ Manager correctly cancelled")

            # Reset for next test
            global_state.set_running_state("running")

            # Test 2: Worker cancellation
            logger.info("Test 2: Worker cancellation")
            global_state.set_running_state("cancelled")

            executor_info = worker.generate_next_action(
                Tu="Test instruction",
                search_query="test query",
                subtask="Test subtask",
                subtask_info="Test subtask info",
                future_tasks=[],
                done_task=[],
                obs=observation
            )

            assert executor_info["reflection"] == "Task was cancelled", "Worker reflection should indicate cancellation"
            assert executor_info["executor_plan"] == "agent.done()", "Worker should return done action"
            logger.info("✓ Worker correctly cancelled")

            self.test_results.append(("Manager/Worker Cancellation", True, "All tests passed"))

        except Exception as e:
            logger.error(f"Manager/Worker cancellation test failed: {e}")
            self.test_results.append(("Manager/Worker Cancellation", False, str(e)))

        finally:
            # Cleanup
            if 'temp_dir' in locals():
                self.cleanup_test_directory(temp_dir)

    def test_grounding_cancellation(self):
        """Test Grounding cancellation functionality"""
        logger.info("=== Testing Grounding Cancellation ===")

        try:
            # Create test environment
            global_state, temp_dir = self.create_test_global_state()

            # Load tools configuration
            tools_config, tools_dict = load_config()

            # Create Grounding instance
            from gui_agents.agents.grounding import Grounding
            grounding = Grounding(
                Tools_dict=tools_dict,
                platform="windows",
                width=1920,
                height=1080,
            )

            # Create mock observation
            observation = self.create_mock_observation()

            # Test 1: Normal coordinate generation (might fail without proper setup, but that's ok)
            logger.info("Test 1: Normal coordinate generation")
            try:
                coords = grounding.generate_coords("test element", observation)
                logger.info(f"Normal coordinate generation returned: {coords}")
            except Exception as e:
                logger.warning(f"Normal coordinate generation failed (expected in test env): {e}")

            # Test 2: Cancelled coordinate generation
            logger.info("Test 2: Cancelled coordinate generation")
            global_state.set_running_state("cancelled")

            coords = grounding.generate_coords("test element", observation)
            assert coords == [0, 0], "Should return default coordinates when cancelled"
            logger.info("✓ Grounding correctly cancelled")

            self.test_results.append(("Grounding Cancellation", True, "All tests passed"))

        except Exception as e:
            logger.error(f"Grounding cancellation test failed: {e}")
            self.test_results.append(("Grounding Cancellation", False, str(e)))

        finally:
            # Cleanup
            if 'temp_dir' in locals():
                self.cleanup_test_directory(temp_dir)

    def run_all_tests(self):
        """Run all cancellation tests"""
        logger.info("Starting agent cancellation tests...")

        # Run all test methods
        self.test_agent_s2_cancellation()
        time.sleep(1)

        self.test_agent_s_fast_cancellation()
        time.sleep(1)

        self.test_manager_worker_cancellation()
        time.sleep(1)

        self.test_grounding_cancellation()

        # Summary
        passed = sum(1 for _, success, _ in self.test_results if success)
        total = len(self.test_results)
        logger.info(f"\n=== Test Summary ===")
        logger.info(f"Passed: {passed}/{total}")

        for test_name, success, message in self.test_results:
            status = "✓" if success else "✗"
            logger.info(f"{status} {test_name}: {message}")

        if passed == total:
            logger.info("✓ All agent cancellation tests passed!")
            return True
        else:
            logger.error(f"✗ {total - passed} tests failed")
            return False

async def main():
    """Main function to run the tests"""
    test = AgentCancellationTest()
    success = test.run_all_tests()

    if success:
        logger.info("Agent cancellation functionality test completed successfully!")
        exit(0)
    else:
        logger.error("Agent cancellation functionality test failed!")
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())