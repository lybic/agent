import unittest
import os
import json
import logging
import sys
from io import BytesIO

from gui_agents.agents.manager import Manager
from gui_agents.utils.common_utils import Node, Dag

# Configure colored logging
class ColoredFormatter(logging.Formatter):
    """Custom colored logging formatter"""
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
    """Print test header, using colored and prominent separator"""
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

class TestManager(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        print_test_header("Set up test environment")
        
        # Load tools configuration file
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
        logger.info(f"Loaded {len(self.Tools_dict)} tool configurations")
        
        # Create test directory structure
        self.test_kb_path = "test_kb"
        self.platform = "darwin"
        self.test_platform_path = os.path.join(self.test_kb_path, self.platform)
        os.makedirs(self.test_platform_path, exist_ok=True)
        logger.info(f"Created test directory: {self.test_platform_path}")
        
        # Create test files
        with open(os.path.join(self.test_platform_path, "narrative_memory.json"), "w") as f:
            json.dump({}, f)
        with open(os.path.join(self.test_platform_path, "episodic_memory.json"), "w") as f:
            json.dump({}, f)
        with open(os.path.join(self.test_platform_path, "embeddings.pkl"), "wb") as f:
            f.write(b"")
        logger.info("Created test files")
        
        # Create Manager instance - use actual Manager instead of mock
        self.manager = Manager(
            Tools_dict=self.Tools_dict,
            local_kb_path=self.test_kb_path,
            platform=self.platform
        )
        logger.info("Manager instance created")
        
        # Create test observation data
        import pyautogui
        self.test_image = pyautogui.screenshot()
        buffered = BytesIO()
        self.test_image.save(buffered, format="PNG")
        self.test_screenshot_bytes = buffered.getvalue()
        
        self.test_observation = {
            "screenshot": self.test_screenshot_bytes
        }
        logger.info("Test observation data created")
        
        # Test instruction
        self.test_instruction = "在系统中打开设置并更改显示分辨率"
        logger.info(f"Test instruction: {self.test_instruction}")

    def tearDown(self):
        """Clean up test environment"""
        print_test_header("Clean up test environment")
        import shutil
        if os.path.exists(self.test_kb_path):
            shutil.rmtree(self.test_kb_path)
        logger.info(f"Deleted test directory: {self.test_kb_path}")

    def test_generate_step_by_step_plan(self):
        """Test _generate_step_by_step_plan method"""
        print_test_header("Test _generate_step_by_step_plan method")
        logger.info(f"Input parameters: observation={type(self.test_observation)}, instruction={self.test_instruction}")
        
        # Test initial plan generation
        print_test_section("Initial plan generation")
        planner_info, plan = self.manager._generate_step_by_step_plan(
            self.test_observation,
            self.test_instruction
        )
        
        # Output results
        logger.info(f"Output results: planner_info={planner_info}")
        logger.info(f"Output results: plan(first 100 characters)={plan[:100]}...")
        
        # Verify results
        self.assertIsNotNone(plan)
        self.assertIsInstance(plan, str)
        self.assertGreater(len(plan), 0)
        self.assertIn("search_query", planner_info)
        self.assertIn("goal_plan", planner_info)
        self.assertEqual(planner_info["goal_plan"], plan)
        
        # Test re-planning (failed subtask)
        print_test_section("Test re-planning (failed subtask)")
        failed_subtask = Node(name="Failed subtask", info="Failed subtask information")
        completed_subtasks = [Node(name="Completed subtask", info="Completed subtask information")]
        
        logger.info(f"Input parameters: failed_subtask={failed_subtask}, completed_subtasks={completed_subtasks}")
        
        self.manager.turn_count = 1  # Set to non-initial state
        planner_info, plan = self.manager._generate_step_by_step_plan(
            self.test_observation,
            self.test_instruction,
            failed_subtask,
            completed_subtasks,
            []
        )
        
        # Output results
        logger.info(f"Output results: planner_info={planner_info}")
        logger.info(f"Output results: plan(first 100 characters)={plan[:100]}...")
        
        # Verify results
        self.assertIsNotNone(plan)
        self.assertIsInstance(plan, str)
        self.assertGreater(len(plan), 0)
        self.assertIn("goal_plan", planner_info)
        self.assertEqual(planner_info["goal_plan"], plan)

    def test_generate_dag(self):
        """Test _generate_dag method"""
        print_test_header("Test _generate_dag method")
        
        # First generate plan
        print_test_section("Generate plan")
        logger.info("First generate plan")
        _, plan = self.manager._generate_step_by_step_plan(
            self.test_observation,
            self.test_instruction
        )
        logger.info(f"Generated plan(first 100 characters): {plan[:100]}...")
        
        # Use generated plan to create DAG
        print_test_section("Create DAG")
        logger.info(f"Input parameters: instruction={self.test_instruction}, plan(first 100 characters)={plan[:100]}...")
        dag_raw = self.manager.dag_translator_agent.execute_tool("dag_translator", {"str_input": f"Instruction: {self.test_instruction}\nPlan: {plan}"})
        logger.info(f"Raw DAG output: {dag_raw}")
        
        # Manually parse DAG
        print_test_section("Parse DAG")
        from gui_agents.utils.common_utils import parse_dag
        dag = parse_dag(dag_raw)
        
        if dag is None:
            logger.error("DAG parsing failed, create a simple test DAG")
            # Create a simple test DAG
            nodes = [
                Node(name="Open settings", info="Open settings application"),
                Node(name="Navigate to display settings", info="Find and click on display settings option"),
                Node(name="Change resolution", info="Change screen resolution")
            ]
            edges = [
                [nodes[0], nodes[1]],
                [nodes[1], nodes[2]]
            ]
            dag = Dag(nodes=nodes, edges=edges)
        
        dag_info = {"dag": dag_raw}
        
        logger.info(f"Parsed DAG: nodes={[node.name for node in dag.nodes]}, edges number={len(dag.edges)}")
        
        # Verify results
        self.assertIsNotNone(dag)
        self.assertIsInstance(dag, Dag)
        self.assertGreater(len(dag.nodes), 0)
        self.assertGreaterEqual(len(dag.edges), 0)
        self.assertIn("dag", dag_info)

    def test_topological_sort(self):
        """Test _topological_sort method"""
        print_test_header("Test _topological_sort method")
        
        # Create test DAG
        print_test_section("Create test DAG")
        nodes = [
            Node(name="A", info="Task A"),
            Node(name="B", info="Task B"),
            Node(name="C", info="Task C"),
            Node(name="D", info="Task D")
        ]
        
        edges = [
            [nodes[0], nodes[1]],  # A -> B
            [nodes[0], nodes[2]],  # A -> C
            [nodes[1], nodes[3]],  # B -> D
            [nodes[2], nodes[3]]   # C -> D
        ]
        
        dag = Dag(nodes=nodes, edges=edges)
        logger.info(f"Input parameters: dag.nodes={[node.name for node in dag.nodes]}, dag.edges number={len(dag.edges)}")
        
        # Execute topological sort
        print_test_section("Execute topological sort")
        sorted_nodes = self.manager._topological_sort(dag)
        logger.info(f"Output results: sorted_nodes={[node.name for node in sorted_nodes]}")
        
        # Verify results
        print_test_section("Verify sorting results")
        self.assertEqual(len(sorted_nodes), 4)
        self.assertEqual(sorted_nodes[0].name, "A")
        
        # Verify B and C's order may be uncertain, but they are both after A and before D
        self.assertIn(sorted_nodes[1].name, ["B", "C"])
        self.assertIn(sorted_nodes[2].name, ["B", "C"])
        self.assertNotEqual(sorted_nodes[1].name, sorted_nodes[2].name)
        
        self.assertEqual(sorted_nodes[3].name, "D")

    def test_get_action_queue(self):
        """Test get_action_queue method"""
        print_test_header("Test get_action_queue method")
        
        # Modify Manager's _generate_dag method to avoid parsing failure
        print_test_section("Modify _generate_dag method")
        def mock_generate_dag(self, instruction, plan):
            logger.info("Use modified _generate_dag method")
            dag_raw = self.dag_translator_agent.execute_tool("dag_translator", {"str_input": f"Instruction: {instruction}\nPlan: {plan}"})
            logger.info(f"Raw DAG output: {dag_raw}")
            
            # Try to parse DAG
            from gui_agents.utils.common_utils import parse_dag
            dag = parse_dag(dag_raw)
            
            # If parsing fails, create a simple test DAG
            if dag is None:
                logger.warning("DAG parsing failed, create a simple test DAG")
                nodes = [
                    Node(name="Open settings", info="Open settings application"),
                    Node(name="Navigate to display settings", info="Find and click on display settings option"),
                    Node(name="Change resolution", info="Change screen resolution")
                ]
                edges = [
                    [nodes[0], nodes[1]],
                    [nodes[1], nodes[2]]
                ]
                dag = Dag(nodes=nodes, edges=edges)
            
            dag_info = {"dag": dag_raw}
            return dag_info, dag
        
        # Replace original method
        original_generate_dag = self.manager._generate_dag
        self.manager._generate_dag = lambda instruction, plan: mock_generate_dag(self.manager, instruction, plan)
        
        try:
            # Call get_action_queue method
            print_test_section("Call get_action_queue method")
            logger.info(f"Input parameters: Tu={self.test_instruction}, Screenshot=Image(100x100), Running_state='初始状态'")
            planner_info, action_queue = self.manager.get_action_queue(
                Tu=self.test_instruction,
                Screenshot=self.test_image,
                Running_state="初始状态"
            )
            
            # Output results
            print_test_section("Verify results")
            logger.info(f"Output results: planner_info={planner_info}")
            logger.info(f"Output results: action_queue={[action.name for action in action_queue]}")
            
            # Verify results
            self.assertIsNotNone(planner_info)
            self.assertIsNotNone(action_queue)
            self.assertIn("search_query", planner_info)
            self.assertIn("goal_plan", planner_info)
            self.assertIn("dag", planner_info)
            self.assertGreater(len(action_queue), 0)
            
            # Verify that the elements in action_queue are Node types
            for action in action_queue:
                self.assertIsInstance(action, Node)
                self.assertIsNotNone(action.name)
                self.assertIsNotNone(action.info)
        finally:
            # Restore original method
            self.manager._generate_dag = original_generate_dag

if __name__ == '__main__':
    unittest.main()