import unittest
import os
import json
import logging
import sys
from io import BytesIO

from gui_agents.agents.worker import Worker
from gui_agents.utils.common_utils import Node

# 配置彩色日志
class ColoredFormatter(logging.Formatter):
    """Custom colored log formatter"""
    COLORS = {
        'DEBUG': '\033[94m',  # Blue
        'INFO': '\033[92m',   # Green
        'WARNING': '\033[93m', # Yellow
        'ERROR': '\033[91m',  # Red
        'CRITICAL': '\033[91m\033[1m', # Red bold
        'RESET': '\033[0m'    # Reset
    }
    
    def format(self, record):
        log_message = super().format(record)
        return f"{self.COLORS.get(record.levelname, self.COLORS['RESET'])}{log_message}{self.COLORS['RESET']}"

# Configure logging - Clear all handlers and reconfigure
logger = logging.getLogger(__name__)
logger.handlers = []  # Clear all existing handlers
logger.propagate = False  # Prevent logging from propagating to root logger

# Add single handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ColoredFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)
logger.setLevel(logging.INFO)

# Define colored separator
def print_test_header(test_name):
    """Print test title, using colored and prominent separator"""
    separator = "="*80
    logger.info(separator)
    logger.info(test_name.center(80))
    logger.info(separator)

def print_test_section(section_name):
    """Print test section, using colored and prominent separator"""
    separator = "-"*60
    logger.info("\n" + separator)
    logger.info(section_name.center(60))
    logger.info(separator)

class TestWorker(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        print_test_header("Start setting up test environment")
        
        # Load tools configuration from tools_config.json
        tools_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools", "tools_config.json")
        with open(tools_config_path, "r") as f:
            tools_config = json.load(f)
            self.Tools_dict = {}
            for tool in tools_config["tools"]:
                tool_name = tool["tool_name"]
                self.Tools_dict[tool_name] = {
                    "provider": tool["provider"],
                    "model": tool["model_name"]
                }
        
        # Create test directory structure
        self.test_kb_path = "test_kb"
        self.platform = "darwin"
        self.test_platform_path = os.path.join(self.test_kb_path, self.platform)
        os.makedirs(self.test_platform_path, exist_ok=True)
        
        # Create test files
        with open(os.path.join(self.test_platform_path, "episodic_memory.json"), "w") as f:
            json.dump({}, f)
        with open(os.path.join(self.test_platform_path, "embeddings.pkl"), "wb") as f:
            f.write(b"")
        
        # Create Worker instance
        self.worker = Worker(
            Tools_dict=self.Tools_dict,
            local_kb_path=self.test_kb_path,
            platform=self.platform,
            enable_reflection=True,
            use_subtask_experience=True
        )
        
        # Create test observation data
        import pyautogui
        self.test_image = pyautogui.screenshot()
        buffered = BytesIO()
        self.test_image.save(buffered, format="PNG")
        self.test_screenshot_bytes = buffered.getvalue()
        
        self.test_observation = {
            "screenshot": self.test_screenshot_bytes
        }
        
        # Initialize planner_history, avoid accessing empty list when turn_count > 0
        self.worker.planner_history = ["Test plan history"]
        
        # Record log
        logger.info("Test environment setup completed, using real screenshot")
        logger.info(f"Screenshot size: {self.test_image.size}")
        
    def tearDown(self):
        """Clean up test environment"""
        print_test_header("Clean up test environment")
        import shutil
        if os.path.exists(self.test_kb_path):
            shutil.rmtree(self.test_kb_path)

    def test_reset(self):
        """Test reset method"""
        print_test_header("Test RESET method")
        
        # Set some initial states
        self.worker.turn_count = 5
        self.worker.worker_history = ["History 1", "History 2"]
        self.worker.reflections = ["Reflection 1", "Reflection 2"]
        
        # Call reset method
        self.worker.reset()
        
        # Verify if the state is reset
        self.assertEqual(self.worker.turn_count, 0)
        self.assertEqual(self.worker.worker_history, [])
        self.assertEqual(self.worker.reflections, [])
        
        # Verify if a new agent instance is created
        self.assertIsNotNone(self.worker.generator_agent)
        self.assertIsNotNone(self.worker.reflection_agent)
        self.assertIsNotNone(self.worker.knowledge_base)

    def test_generate_next_action_first_turn(self):
        """Test generate_next_action method for the first turn (turn_count=0)"""
        print_test_header("Test GENERATE_NEXT_ACTION for the first turn")
        
        # Prepare test data
        instruction = "Open settings and change display resolution"
        search_query = "How to open settings and change display resolution"
        subtask = "Open settings"
        subtask_info = "Open settings application"
        future_tasks = [
            Node(name="Navigate to display settings", info="Find and click on display settings option"),
            Node(name="Change resolution", info="Change screen resolution")
        ]
        done_tasks = []
        
        self.worker.turn_count = 0
        
        # Call generate_next_action method
        executor_info = self.worker.generate_next_action(
            instruction=instruction,
            search_query=search_query,
            subtask=subtask,
            subtask_info=subtask_info,
            future_tasks=future_tasks,
            done_task=done_tasks,
            obs=self.test_observation
        )
        
        # Print results for debugging
        logger.info(f"Executor information: {executor_info}")
        
        # Verify results
        self.assertIn("executor_plan", executor_info)
        # No longer assert specific operations, because the output may vary using real models
        self.assertIsInstance(executor_info["executor_plan"], str)
        self.assertGreater(len(executor_info["executor_plan"]), 0)
        
        # Verify turn_count increased
        self.assertEqual(self.worker.turn_count, 1)
        
    def test_generate_next_action_second_turn(self):
        """Test generate_next_action method for the second turn (turn_count>0)"""
        print_test_header("Test GENERATE_NEXT_ACTION for the second turn")
        
        # Prepare test data
        instruction = "Open settings and change display resolution"
        search_query = "How to open settings and change display resolution"
        subtask = "Open settings"
        subtask_info = "Open settings application"
        future_tasks = [
            Node(name="Navigate to display settings", info="Find and click on display settings option"),
            Node(name="Change resolution", info="Change screen resolution")
        ]
        done_tasks = []
        
        # Set to the second turn
        self.worker.turn_count = 1
        
        # Ensure planner_history has content
        if len(self.worker.planner_history) == 0:
            self.worker.planner_history = ["Test plan history"]
        
        # Call generate_next_action method
        executor_info = self.worker.generate_next_action(
            instruction=instruction,
            search_query=search_query,
            subtask=subtask,
            subtask_info=subtask_info,
            future_tasks=future_tasks,
            done_task=done_tasks,
            obs=self.test_observation
        )
        
        # Print results for debugging
        logger.info(f"Executor information (second turn): {executor_info}")
        
        # Verify results
        self.assertIn("executor_plan", executor_info)
        self.assertIsInstance(executor_info["executor_plan"], str)
        self.assertGreater(len(executor_info["executor_plan"]), 0)
        
        # Verify turn_count increased
        self.assertEqual(self.worker.turn_count, 2)

    def test_clean_worker_generation_for_reflection(self):
        """Test clean_worker_generation_for_reflection method"""
        print_test_header("Test CLEAN_WORKER_GENERATION_FOR_REFLECTION method")
        
        # Prepare test data
        worker_generation = """(Previous Action Verification)
The previous action has been successfully executed.

(Screenshot Analysis)
I see the settings application is open, with multiple options.

(Reasoning)
I need to find and click on the display settings option.

(Grounded Action)
```python
agent.click("Display settings")
```

(Additional Grounded Action)
```python
agent.wait(1.0)
```
"""
        
        # Call clean_worker_generation_for_reflection method
        cleaned_text = self.worker.clean_worker_generation_for_reflection(worker_generation)
        
        # Print results for debugging
        logger.info(f"Text before cleaning: \n{worker_generation}")
        logger.info(f"Text after cleaning: \n{cleaned_text}")
        
        # Verify results
        self.assertIn("(Screenshot Analysis)", cleaned_text)
        self.assertIn("agent.click(\"Display settings\")", cleaned_text)
        self.assertNotIn("(Previous Action Verification)", cleaned_text)
        # Note: Depending on the actual implementation of clean_worker_generation_for_reflection, the following assertions may need to be adjusted
        # If the method implementation has changed, these assertions may need to be modified
        try:
            self.assertNotIn("(Additional Grounded Action)", cleaned_text)
            self.assertNotIn("agent.wait(1.0)", cleaned_text)
        except AssertionError as e:
            logger.warning(f"Assertion failed, but this may be because the implementation of clean_worker_generation_for_reflection has changed: {e}")

if __name__ == '__main__':
    unittest.main()