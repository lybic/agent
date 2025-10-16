import logging
import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
import platform

from gui_agents.core.knowledge import KnowledgeBase
from gui_agents.agents.global_state import GlobalState
from gui_agents.store.registry import Registry
from gui_agents.utils.common_utils import (
    Dag,
    Node,
    parse_dag,
    agent_log_to_string,
)
from gui_agents.tools.tools import Tools
from gui_agents.agents.stream_manager import stream_manager

logger = logging.getLogger("desktopenv.agent")

NUM_IMAGE_TOKEN = 1105  # Value set of screen of size 1920x1080 for openai vision

class Manager:
    def __init__(
        self,
        Tools_dict: Dict,
        # engine_params: Dict,
        local_kb_path: str,
        multi_round: bool = False,
        platform: str = platform.system().lower(),
        enable_search: bool = True,
    ):
        """
        Initialize the Manager which orchestrates planning, knowledge retrieval/fusion, DAG generation, topological sorting, and action queue creation for task-driven agents.
        
        Parameters:
            Tools_dict (Dict): Mapping of tool names to their configuration dictionaries; used to register and configure internal Tools instances (e.g., 'subtask_planner', 'dag_translator', 'embedding', 'websearch').
            local_kb_path (str): Filesystem path to the local knowledge base storage used by the KnowledgeBase.
            multi_round (bool): When True, enable multi-round interaction/stateful planning behavior across turns.
            platform (str): Target platform identifier (defaults to current system name); forwarded to KnowledgeBase and tools where applicable.
            enable_search (bool): When True, register and enable a web search tool ('websearch'); otherwise search functionality is disabled.
        """
        self.platform = platform
        self.Tools_dict = Tools_dict

        def _register(tools_instance, tool_name):
            """
            Register a tool with the provided tools manager using settings from Tools_dict.
            
            Parameters:
                tools_instance: An object exposing register_tool(name, provider, model, **kwargs) used to register the tool.
                tool_name (str): Key to look up the tool's configuration in Tools_dict; provider, model, and supported authentication keys
                    (e.g., 'api_key', 'base_url', 'endpoint_url', 'azure_endpoint', 'api_version') will be extracted and passed to register_tool.
            
            """
            config = Tools_dict.get(tool_name, {}).copy()
            provider = config.pop("provider", None)
            model = config.pop("model", None)

            auth_keys = ['api_key', 'base_url', 'endpoint_url', 'azure_endpoint', 'api_version']
            auth_params = {}
            for key in auth_keys:
                if key in config:
                    auth_params[key] = config[key]
                    logger.info(f"Manager._register: Setting {key} for tool '{tool_name}'")

            all_params = {**config, **auth_params}

            logger.info(f"Manager._register: Registering tool '{tool_name}' with provider '{provider}', model '{model}'")
            tools_instance.register_tool(tool_name, provider, model, **all_params)

        self.generator_agent = Tools()
        _register(self.generator_agent, "subtask_planner")

        self.dag_translator_agent = Tools()
        _register(self.dag_translator_agent, "dag_translator")

        self.narrative_summarization_agent = Tools()
        _register(self.narrative_summarization_agent, "narrative_summarization")

        self.episode_summarization_agent = Tools()
        _register(self.episode_summarization_agent, "episode_summarization")

        self.local_kb_path = local_kb_path

        self.embedding_engine = Tools()
        _register(self.embedding_engine, "embedding")
        
        KB_Tools_dict = {
            "embedding": self.Tools_dict.get("embedding"),
            "query_formulator": self.Tools_dict.get("query_formulator"),
            "context_fusion": self.Tools_dict.get("context_fusion"),
            "narrative_summarization": self.Tools_dict.get("narrative_summarization"),
            "episode_summarization": self.Tools_dict.get("episode_summarization"),
        }


        self.knowledge_base = KnowledgeBase(
            embedding_engine=self.embedding_engine,
            local_kb_path=self.local_kb_path,
            platform=platform,
            Tools_dict=KB_Tools_dict,
        )

        # GlobalState will be initialized in reset() method when task_id is available
        self.global_state: GlobalState = None  # type: ignore

        self.planner_history = []

        self.turn_count = 0
        self.task_id = None  # Will be set by agent

        # Initialize search engine based on enable_search parameter
        if enable_search:
            self.search_engine = Tools()
            _register(self.search_engine, "websearch")
        else:
            self.search_engine = None

        self.multi_round = multi_round

    def set_task_id(self, task_id: str) -> None:
        """Set the task identifier and update global state reference"""
        self.task_id = task_id
        # Update global state reference with task-specific registry
        self.global_state = Registry.get_from_context("GlobalStateStore", task_id)  # type: ignore

    def _send_stream_message(self, task_id: str, stage: str, message: str) -> None:
        """
        Enqueue a stream message for the given task if a task ID is provided.
        
        Parameters:
            task_id (str): Identifier of the task stream; no message is sent if empty.
            stage (str): Stage label for the message.
            message (str): Message content to enqueue.
        """
        if not task_id:
            return

        stream_manager.add_message_threadsafe(task_id, stage, message)

    def summarize_episode(self, trajectory):
        """
        Create a concise summary of the provided episode trajectory for lifelong learning and reflection.
        
        Parameters:
            trajectory (str): Serialized episode experience or trajectory to summarize.
        
        Returns:
            subtask_summarization (str): A short summary highlighting key subtasks, lessons, or reflections from the episode.
        """

        # Create Reflection on whole trajectories for next round trial, keep earlier messages as exemplars
        subtask_summarization, total_tokens, cost_string = self.episode_summarization_agent.execute_tool("episode_summarization", {"str_input": trajectory})
        logger.info(f"Episode summarization tokens: {total_tokens}, cost: {cost_string}")

        self.global_state.log_operation(
            module="manager",
            operation="episode_summarization",
            data={
                "tokens": total_tokens,
                "cost": cost_string,
                "content": subtask_summarization
            }
        )

        self._send_stream_message(self.task_id, "summarization", f"Episode summarization: {subtask_summarization}")

        return subtask_summarization

    def summarize_narrative(self, trajectory):
        """
        Produce a concise reflective summary of a narrative trajectory to inform lifelong learning.
        
        Parameters:
            trajectory: Narrative content (e.g., episode transcript or sequence of subtasks) to be summarized.
        
        Returns:
            A string containing a reflective summary that captures key insights, lessons learned, and recommendations for future rounds.
        """
        # Create Reflection on whole trajectories for next round trial
        lifelong_learning_reflection, total_tokens, cost_string = self.narrative_summarization_agent.execute_tool("narrative_summarization", {"str_input": trajectory})
        logger.info(f"Narrative summarization tokens: {total_tokens}, cost: {cost_string}")
        
        self.global_state.log_operation(
            module="manager",
            operation="narrative_summarization",
            data={
                "tokens": total_tokens,
                "cost": cost_string,
                "content": lifelong_learning_reflection
            }
        )

        return lifelong_learning_reflection
    
    def _generate_step_by_step_plan(
        self,
        observation: Dict,
        instruction: str,
        failed_subtask: Optional[Node] = None,
        completed_subtasks_list: List[Node] = [],
        remaining_subtasks_list: List[Node] = [],
    ) -> Tuple[Dict, str]:

        """
        Generate a high-level, step-by-step plan for the given task, optionally incorporating retrieved knowledge and the current subtask state.
        
        Parameters:
            observation (Dict): Current environment/desktop state; may include a 'screenshot' key with image data used for planning.
            instruction (str): Natural-language task description to plan for.
            failed_subtask (Optional[Node]): If provided, indicates a subtask that failed and triggers replanning for the remainder.
            completed_subtasks_list (List[Node]): Ordered list of subtasks already completed; used to inform replanning.
            remaining_subtasks_list (List[Node]): Ordered list of subtasks still expected; used to inform replanning.
        
        Returns:
            planner_info (Dict): Metadata about the planning step (includes at least 'search_query' and 'goal_plan').
            plan (str): The generated high-level plan as a human-readable string.
        
        Side effects:
            - May perform retrieval and knowledge fusion on the first planning turn.
            - Records operations to global_state, appends the plan to self.planner_history, increments self.turn_count, and sends stream messages when self.task_id is set.
        
        Raises:
            Exception: If plan generation produces an empty plan.
        """
        import time
        step_start = time.time()
        # Converts a list of DAG Nodes into a natural langauge list
        def format_subtask_list(subtasks: List[Node]) -> str:
            res = ""
            for idx, node in enumerate(subtasks):
                res += f"{idx+1}. **{node.name}**:\n"
                bullets = re.split(r"(?<=[.!?;]) +", node.info)
                for bullet in bullets:
                    res += f"   - {bullet}\n"
                res += "\n"
            return res
        prefix_message = ""
        # Perform Retrieval only at the first planning step
        if self.turn_count == 0:
            formulate_query_start = time.time()
            self.search_query, total_tokens, cost_string = self.knowledge_base.formulate_query(
                instruction, observation
            )
            formulate_query_time = time.time() - formulate_query_start
            logger.info(f"Formulate query tokens: {total_tokens}, cost: {cost_string}")
            self.global_state.log_operation(
                module="manager",
                operation="formulate_query",
                data={
                    "tokens": total_tokens,
                    "cost": cost_string,
                    "content": self.search_query,
                    "duration": formulate_query_time
                }
            )
            self.global_state.set_search_query(self.search_query)

            most_similar_task = ""
            retrieved_experience = ""
            integrated_knowledge = ""
            # Retrieve most similar narrative (task) experience
            narrative_start = time.time()
            most_similar_task, retrieved_experience, total_tokens, cost_string = (
                self.knowledge_base.retrieve_narrative_experience(instruction)
            )
            logger.info(f"Retrieve narrative experience tokens: {total_tokens}, cost: {cost_string}")
            narrative_time = time.time() - narrative_start
            logger.info(f"[Timing] Manager.retrieve_narrative_experience execution time: {narrative_time:.2f} seconds")
            self.global_state.log_operation(
                module="manager", 
                operation="retrieve_narrative_experience",
                data={
                    "tokens": total_tokens,
                    "cost": cost_string,
                    "content": "Most similar task: " + most_similar_task + "\n" + retrieved_experience.strip(),
                    "duration": narrative_time
                }
            )
            
            logger.info(
                "SIMILAR TASK EXPERIENCE: %s",
                most_similar_task + "\n" + retrieved_experience.strip(),
            )
            
            # Retrieve knowledge from the web if search_engine is provided
            if self.search_engine is not None:
                knowledge_start = time.time()
                retrieved_knowledge, total_tokens, cost_string = self.knowledge_base.retrieve_knowledge(
                    instruction=instruction,
                    search_query=self.search_query,
                    search_engine=self.search_engine,
                )
                logger.info(f"Retrieve knowledge tokens: {total_tokens}, cost: {cost_string}")
                
                knowledge_time = time.time() - knowledge_start
                logger.info(f"[Timing] Manager.retrieve_knowledge execution time: {knowledge_time:.2f} seconds")
                self.global_state.log_operation(
                    module="manager",
                    operation="retrieve_knowledge",
                    data={
                        "tokens": total_tokens,
                        "cost": cost_string,
                        "content": retrieved_knowledge,
                        "duration": knowledge_time
                    }
                )
                
                logger.info("RETRIEVED KNOWLEDGE: %s", retrieved_knowledge)

                if retrieved_knowledge is not None:
                    # Fuse the retrieved knowledge and experience
                    fusion_start = time.time()
                    integrated_knowledge, total_tokens, cost_string = self.knowledge_base.knowledge_fusion(
                        observation=observation,
                        instruction=instruction,
                        web_knowledge=retrieved_knowledge,
                        similar_task=most_similar_task,
                        experience=retrieved_experience,
                    )
                    logger.info(f"Knowledge fusion tokens: {total_tokens}, cost: {cost_string}")
                    fusion_time = time.time() - fusion_start
                    logger.info(f"[Timing] Manager.knowledge_fusion execution time: {fusion_time:.2f} seconds")
                    self.global_state.log_operation(
                        module="manager",
                        operation="knowledge_fusion",
                        data={
                            "tokens": total_tokens,
                            "cost": cost_string,
                            "content": integrated_knowledge,
                            "duration": fusion_time
                        }
                    )
                    
                    logger.info("INTEGRATED KNOWLEDGE: %s", integrated_knowledge)

            integrated_knowledge = integrated_knowledge or retrieved_experience

            # Add the integrated knowledge to the task instruction in the system prompt
            if integrated_knowledge:
                instruction += f"\nYou may refer to some retrieved knowledge if you think they are useful.{integrated_knowledge}"
            prefix_message = f"TASK_DESCRIPTION is {instruction}"

        # Re-plan on failure case
        if failed_subtask:
            agent_log = agent_log_to_string(self.global_state.get_agent_log())
            generator_message = (
                f"The subtask {failed_subtask} cannot be completed. Please generate a new plan for the remainder of the trajectory.\n\n"
                f"Successfully Completed Subtasks:\n{format_subtask_list(completed_subtasks_list)}\n"
                f"Please refer to the agent log to understand the progress and context of the task so far.\n{agent_log}"
            )
        # Re-plan on subtask completion case
        elif len(completed_subtasks_list) + len(remaining_subtasks_list) > 0:
            agent_log = agent_log_to_string(self.global_state.get_agent_log())
            generator_message = (
                "The current trajectory and desktop state is provided. Please revise the plan for the following trajectory.\n\n"
                f"Successfully Completed Subtasks:\n{format_subtask_list(completed_subtasks_list)}\n"
                f"Future Remaining Subtasks:\n{format_subtask_list(remaining_subtasks_list)}\n"
                f"Please refer to the agent log to understand the progress and context of the task so far.\n{agent_log}"
            )
        # Initial plan case
        else:
            generator_message = "Please generate the initial plan for the task.\n"
        
        generator_message = prefix_message + "\n" + generator_message
        logger.info("GENERATOR MESSAGE: %s", generator_message)
        logger.info("GENERATING HIGH LEVEL PLAN")

        subtask_planner_start = time.time()

        # Stream subtask planning message
        self._send_stream_message(self.task_id, "planning", "Analyzing tasks and generating subtask plans...")

        plan, total_tokens, cost_string = self.generator_agent.execute_tool("subtask_planner", {"str_input": generator_message, "img_input": observation.get("screenshot", None)})
        logger.info(f"Subtask planner tokens: {total_tokens}, cost: {cost_string}")
        subtask_planner_time = time.time() - subtask_planner_start
        logger.info(f"[Timing] Manager.subtask_planner execution time: {subtask_planner_time:.2f} seconds")
        self.global_state.log_operation(
            module="manager",
            operation="subtask_planner",
            data={
                "tokens": total_tokens,
                "cost": cost_string,
                "content": plan,
                "duration": subtask_planner_time
            }
        )

        # Stream planning completion message
        if self.task_id:
            plan_preview = plan[:150] + "..." if len(plan) > 150 else plan
            self._send_stream_message(self.task_id, "planning", f"Subtask planning completed: {plan_preview}")
        
        step_time = time.time() - step_start
        logger.info(f"[Timing] Manager._generate_step_by_step_plan execution time: {step_time:.2f} seconds")
        self.global_state.log_operation(
            module="manager",
            operation="Manager._generate_step_by_step_plan",
            data={"duration": step_time}
        )

        if plan == "":
            raise Exception("Plan Generation Failed - Fix the Prompt")

        logger.info("HIGH LEVEL STEP BY STEP PLAN: %s", plan)

        self.planner_history.append(plan)
        self.turn_count += 1

        planner_info = {
            "search_query": self.search_query,
            "goal_plan": plan,
        }

        assert type(plan) == str

        return planner_info, plan

    def _generate_dag(self, instruction: str, plan: str) -> Tuple[Dict, Dag]:
        import time
        dag_start = time.time()

        logger.info("GENERATING DAG")

        # Add maximum retry count
        max_retries = 2
        retry_count = 0
        dag = None

        while retry_count < max_retries and dag is None:
            if retry_count > 0:
                logger.warning(f"Retrying DAG generation, attempt {retry_count}")
                self.global_state.log_operation(
                    module="manager",
                    operation="dag_retry",
                    data={"retry_count": retry_count}
                )
            
            # Generate DAG
            dag_raw, total_tokens, cost_string = self.dag_translator_agent.execute_tool("dag_translator", {"str_input": f"Instruction: {instruction}\nPlan: {plan}"})
            logger.info(f"DAG translator tokens: {total_tokens}, cost: {cost_string}")

            # Try to parse DAG
            dag = parse_dag(dag_raw)
            
            # If parsing fails, increment retry count
            if dag is None:
                retry_count += 1
                # If not the last attempt, wait a short time before retrying
                if retry_count < max_retries:
                    time.sleep(1)
        
        dag_time = time.time() - dag_start
        logger.info(f"[Timing] Manager._generate_dag execution time: {dag_time:.2f} seconds")

        logger.info("Generated DAG: %s", dag_raw)
        self.global_state.log_operation(
            module="manager",
            operation="generated_dag",
            data={
                "tokens": total_tokens,
                "cost": cost_string,
                "content": dag_raw,
                "duration": dag_time,
                "retry_count": retry_count
            }
        )

        dag_info = {
            "dag": dag_raw,
        }

        # If all attempts fail, create a simple default DAG
        if dag is None:
            logger.error("Unable to generate valid DAG, using default DAG")
            # Create a simple default DAG with just one "Execute Task" node
            default_node = Node(name="Execute Task", info=f"Execute instruction: {instruction}")
            dag = Dag(nodes=[default_node], edges=[])
            
            self.global_state.log_operation(
                module="manager",
                operation="default_dag_created",
                data={"content": "Using default DAG because valid DAG could not be parsed from model output"}
            )

        return dag_info, dag

    def _topological_sort(self, dag: Dag) -> List[Node]:
        """Topological sort of the DAG using DFS
        dag: Dag: Object representation of the DAG with nodes and edges
        """
        import logging
        logger = logging.getLogger("desktopenv.agent")

        # Check if DAG is empty
        if not dag.nodes:
            logger.warning("DAG has no nodes, returning empty list")
            return []

        # If there's only one node, return it directly
        if len(dag.nodes) == 1:
            logger.info("DAG has only one node, returning directly")
            return dag.nodes

        def dfs(node_name, visited, temp_visited, stack):
            # If node is already in current path, we have a cycle
            if node_name in temp_visited:
                raise ValueError(f"Cycle detected in DAG involving node: {node_name}")
            
            # If node has been visited, skip
            if visited.get(node_name, False):
                return
            
            # Mark node as part of current path
            temp_visited.add(node_name)
            visited[node_name] = True
            
            # Visit all neighbors
            for neighbor in adj_list.get(node_name, []):
                if not visited.get(neighbor, False):
                    dfs(neighbor, visited, temp_visited, stack)
            
            # Remove node from current path
            temp_visited.remove(node_name)
            stack.append(node_name)

        try:
            # Build adjacency list
            adj_list = defaultdict(list)
            for u, v in dag.edges:
                if not u or not v:
                    logger.warning(f"Skipping invalid edge: {u} -> {v}")
                    continue
                adj_list[u.name].append(v.name)

            visited = {node.name: False for node in dag.nodes}
            temp_visited = set()  # For cycle detection
            stack = []

            # Perform DFS for each unvisited node
            for node in dag.nodes:
                if not visited.get(node.name, False):
                    dfs(node.name, visited, temp_visited, stack)

            # Return topologically sorted nodes
            sorted_nodes = []
            for name in stack[::-1]:
                matching_nodes = [n for n in dag.nodes if n.name == name]
                if matching_nodes:
                    sorted_nodes.append(matching_nodes[0])
                else:
                    logger.warning(f"Could not find node named {name} in DAG node list")
            
            # Check if all nodes are included in result
            if len(sorted_nodes) != len(dag.nodes):
                logger.warning(f"Number of nodes in topological sort result ({len(sorted_nodes)}) does not match number in DAG ({len(dag.nodes)})")
            
            return sorted_nodes
            
        except Exception as e:
            logger.error(f"Error during topological sort: {e}")
            # On error, return original node list
            logger.info("Returning unsorted original node list")
            return dag.nodes

    def get_action_queue(
        self,
        Tu: str,
        observation: Dict,
        running_state: str,
        failed_subtask: Optional[Node] = None,
        completed_subtasks_list: List[Node] = [],
        remaining_subtasks_list: List[Node] = [],
    ):
        """Generate the action list based on the instruction
        instruction:str: Instruction for the task
        """
        import time
        action_queue_start = time.time()

        try:
            planner_info, plan = self._generate_step_by_step_plan(
                observation,
                Tu,
                failed_subtask,
                completed_subtasks_list,
                remaining_subtasks_list,
            )

            # Generate the DAG
            try:
                dag_info, dag = self._generate_dag(Tu, plan)
            except Exception as e:
                logger.error(f"Error generating DAG: {e}")
                # Create a simple default DAG with just one "Execute Task" node
                default_node = Node(name="Execute Task", info=f"Execute instruction: {Tu}")
                dag = Dag(nodes=[default_node], edges=[])
                dag_info = {"dag": "Failed to generate DAG, using default DAG"}
                
                self.global_state.log_operation(
                    module="manager",
                    operation="dag_generation_error",
                    data={"error": str(e), "content": "Using default DAG due to error in DAG generation"}
                )

            # Topological sort of the DAG
            try:
                action_queue = self._topological_sort(dag)
            except Exception as e:
                logger.error(f"Error during topological sort of DAG: {e}")
                # If topological sort fails, use node list directly
                action_queue = dag.nodes
                
                self.global_state.log_operation(
                    module="manager",
                    operation="topological_sort_error",
                    data={"error": str(e), "content": "Topological sort failed, using node list directly"}
                )

            planner_info.update(dag_info)
            
            if action_queue:
                logger.info(f"NEXT SUBTASK: {action_queue[0]}")
                self.global_state.log_operation(
                    module="manager",
                    operation="next_subtask",
                    data={"content": str(action_queue[0])}
                )
                
                if len(action_queue) > 1:
                    logger.info(f"REMAINING SUBTASKS: {action_queue[1:]}")
                    self.global_state.log_operation(
                        module="manager",
                        operation="remaining_subtasks",
                        data={"content": str(action_queue[1:])}
                    )
            
            action_queue_time = time.time() - action_queue_start
            logger.info(f"[Timing] manager.get_action_queue execution time: {action_queue_time:.2f} seconds")
            self.global_state.log_operation(
                module="manager",
                operation="manager.get_action_queue",
                data={"duration": action_queue_time}
            )

            return planner_info, action_queue
            
        except Exception as e:
            # Handle any unhandled exceptions in the entire process
            logger.error(f"Unhandled exception in get_action_queue function: {e}")
            
            # Create a simple default task node
            default_node = Node(name="Execute Task", info=f"Execute instruction: {Tu}")
            action_queue = [default_node]
            planner_info = {"error": str(e), "fallback": "Using default task node"}
            
            self.global_state.log_operation(
                module="manager",
                operation="get_action_queue_error",
                data={"error": str(e), "content": "Unhandled exception occurred, using default task node"}
            )
            
            action_queue_time = time.time() - action_queue_start
            logger.info(f"[Timing] manager.get_action_queue (error path) execution time: {action_queue_time:.2f} seconds")
            
            return planner_info, action_queue