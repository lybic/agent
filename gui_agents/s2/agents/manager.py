import logging
import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
import platform

from gui_agents.s2.agents.grounding import ACI
from gui_agents.s2.core.knowledge import KnowledgeBase
from gui_agents.s2.utils.common_utils import (
    Dag,
    Node,   
    calculate_tokens,
    # call_llm_safe,
    parse_dag,
)
from gui_agents.s2.tools.tools import Tools
from PIL import Image
import io

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
    ):
        # TODO: move the prompt to Procedural Memory
        # super().__init__(engine_params, platform)
        self.platform = platform
        self.Tools_dict = Tools_dict

        # Initialize the planner
        # sys_prompt = PROCEDURAL_MEMORY.COMBINED_MANAGER_PROMPT

        # self.generator_agent = self._create_agent(sys_prompt)

        self.generator_agent = Tools()
        self.generator_agent.register_tool("subtask_planner", Tools_dict["subtask_planner"]["provider"], Tools_dict["subtask_planner"]["model"])

        # self.generator_agent.tool["subtask_planner"].lmmagent.add_system_prompt(PROCEDURAL_MEMORY.COMBINED_MANAGER_PROMPT)

        # Initialize the remaining modules
        # self.dag_translator_agent = self._create_agent(
        #     PROCEDURAL_MEMORY.DAG_TRANSLATOR_PROMPT
        # )

        self.dag_translator_agent = Tools()
        self.dag_translator_agent.register_tool("dag_translator", self.Tools_dict["dag_translator"]["provider"], self.Tools_dict["dag_translator"]["model"])

        # Stop at 2025.07.10 01:29
        # TODO: how to plug in knowledge base?

        self.local_kb_path = local_kb_path

        self.embedding_engine = Tools()
        self.embedding_engine.register_tool("embedding", self.Tools_dict["embedding"]["provider"], self.Tools_dict["embedding"]["model"])
        KB_Tools_dict = {
            "embedding": self.Tools_dict["embedding"],
            "query_formulator": self.Tools_dict["query_formulator"],
            "context_fusion": self.Tools_dict["context_fusion"],
        }


        self.knowledge_base = KnowledgeBase(
            embedding_engine=self.embedding_engine,
            local_kb_path=self.local_kb_path,
            platform=platform,
            Tools_dict=KB_Tools_dict,
        )

        self.planner_history = []

        self.turn_count = 0
        # self.search_engine = search_engine
        self.search_engine = Tools()
        self.search_engine.register_tool("websearch", self.Tools_dict["websearch"]["provider"], self.Tools_dict["websearch"]["model"])

        self.multi_round = multi_round

    def _generate_step_by_step_plan(
        self,
        observation: Dict,
        instruction: str,
        failed_subtask: Optional[Node] = None,
        completed_subtasks_list: List[Node] = [],
        remaining_subtasks_list: List[Node] = [],
    ) -> Tuple[Dict, str]:

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

        # Perform Retrieval only at the first planning step
        if self.turn_count == 0:

            self.search_query = self.knowledge_base.formulate_query(
                instruction, observation
            )

            most_similar_task = ""
            retrieved_experience = ""
            integrated_knowledge = ""
            # Retrieve most similar narrative (task) experience
            most_similar_task, retrieved_experience = (
                self.knowledge_base.retrieve_narrative_experience(instruction)
            )
            logger.info(
                "SIMILAR TASK EXPERIENCE: %s",
                most_similar_task + "\n" + retrieved_experience.strip(),
            )

            # Retrieve knowledge from the web if search_engine is provided
            if self.search_engine is not None:
                retrieved_knowledge = self.knowledge_base.retrieve_knowledge(
                    instruction=instruction,
                    search_query=self.search_query,
                    search_engine=self.search_engine,
                )
                logger.info("RETRIEVED KNOWLEDGE: %s", retrieved_knowledge)

                if retrieved_knowledge is not None:
                    # Fuse the retrieved knowledge and experience
                    integrated_knowledge = self.knowledge_base.knowledge_fusion(
                        observation=observation,
                        instruction=instruction,
                        web_knowledge=retrieved_knowledge,
                        similar_task=most_similar_task,
                        experience=retrieved_experience,
                    )
                    logger.info("INTEGRATED KNOWLEDGE: %s", integrated_knowledge)

            integrated_knowledge = integrated_knowledge or retrieved_experience

            # Add the integrated knowledge to the task instruction in the system prompt
            if integrated_knowledge:
                instruction += f"\nYou may refer to some retrieved knowledge if you think they are useful.{integrated_knowledge}"

            # self.generator_agent.add_system_prompt(
            #     self.generator_agent.system_prompt.replace(
            #         "TASK_DESCRIPTION", instruction
            #     )
            # )

        # Re-plan on failure case
        if failed_subtask:
            generator_message = (
                f"The subtask {failed_subtask} cannot be completed. Please generate a new plan for the remainder of the trajectory.\n\n"
                f"Successfully Completed Subtasks:\n{format_subtask_list(completed_subtasks_list)}\n"
            )
        # Re-plan on subtask completion case
        elif len(completed_subtasks_list) + len(remaining_subtasks_list) > 0:
            generator_message = (
                "The current trajectory and desktop state is provided. Please revise the plan for the following trajectory.\n\n"
                f"Successfully Completed Subtasks:\n{format_subtask_list(completed_subtasks_list)}\n"
                f"Future Remaining Subtasks:\n{format_subtask_list(remaining_subtasks_list)}\n"
            )
        # Initial plan case
        else:
            generator_message = "Please generate the initial plan for the task.\n"

        logger.info("GENERATOR MESSAGE: %s", generator_message)

        # self.generator_agent.add_message(
        #     generator_message,
        #     image_content=observation.get("screenshot", None),
        #     role="user",
        # )

        logger.info("GENERATING HIGH LEVEL PLAN")

        # plan = call_llm_safe(self.generator_agent)

        plan = self.generator_agent.execute_tool("subtask_planner", {"str_input": generator_message, "img_input": observation.get("screenshot", None)})

        if plan == "":
            raise Exception("Plan Generation Failed - Fix the Prompt")

        logger.info("HIGH LEVEL STEP BY STEP PLAN: %s", plan)

        # self.generator_agent.add_message(plan, role="assistant")
        self.planner_history.append(plan)
        self.turn_count += 1

        # # Set Cost based on GPT-4o
        # input_tokens, output_tokens = calculate_tokens(self.generator_agent.messages)
        # cost = input_tokens * (0.0050 / 1000) + output_tokens * (0.0150 / 1000)

        planner_info = {
            "search_query": self.search_query,
            "goal_plan": plan,
            # "num_input_tokens_plan": input_tokens,
            # "num_output_tokens_plan": output_tokens,
            # "goal_plan_cost": cost,
        }

        assert type(plan) == str

        return planner_info, plan

    def _generate_dag(self, instruction: str, plan: str) -> Tuple[Dict, Dag]:
        # For the re-planning case, remove the prior input since this should only translate the new plan
        # self.dag_translator_agent.reset()

        # Add initial instruction and plan to the agent's message history
        # self.dag_translator_agent.add_message(
        #     f"Instruction: {instruction}\nPlan: {plan}", role="user"
        # )

        logger.info("GENERATING DAG")

        # Generate DAG
        # dag_raw = call_llm_safe(self.dag_translator_agent)
        dag_raw = self.dag_translator_agent.execute_tool("dag_translator", {"str_input": f"Instruction: {instruction}\nPlan: {plan}"})

        dag = parse_dag(dag_raw)

        logger.info("Generated DAG: %s", dag_raw)

        # self.dag_translator_agent.add_message(dag_raw, role="assistant")

        # input_tokens, output_tokens = calculate_tokens(
        #     self.dag_translator_agent.messages
        # )

        # # Set Cost based on GPT-4o
        # cost = input_tokens * (0.0050 / 1000) + output_tokens * (0.0150 / 1000)

        dag_info = {
            "dag": dag_raw,
            # "num_input_tokens_dag": input_tokens,
            # "num_output_tokens_dag": output_tokens,
            # "dag_cost": cost,
        }

        assert type(dag) == Dag

        return dag_info, dag

    def _topological_sort(self, dag: Dag) -> List[Node]:
        """Topological sort of the DAG using DFS
        dag: Dag: Object representation of the DAG with nodes and edges
        """

        def dfs(node_name, visited, stack):
            visited[node_name] = True
            for neighbor in adj_list[node_name]:
                if not visited[neighbor]:
                    dfs(neighbor, visited, stack)
            stack.append(node_name)

        # Convert edges to adjacency list
        adj_list = defaultdict(list)
        for u, v in dag.edges:
            adj_list[u.name].append(v.name)

        visited = {node.name: False for node in dag.nodes}
        stack = []

        for node in dag.nodes:
            if not visited[node.name]:
                dfs(node.name, visited, stack)

        # Return the nodes in topologically sorted order
        sorted_nodes = [
            next(n for n in dag.nodes if n.name == name) for name in stack[::-1]
        ]
        return sorted_nodes

    def get_action_queue(
        self,
        Tu: str,
        Screenshot: Image.Image,
        Running_state: str,
        Failed_subtask: Optional[Node] = None,
        Completed_subtasks_list: List[Node] = [],
        Remaining_subtasks_list: List[Node] = [],
    ):
        """Generate the action list based on the instruction
        instruction:str: Instruction for the task
        """
        
        Screenshot = Screenshot.resize((1920, 1080), Image.LANCZOS)

        # Save the screenshot to a BytesIO object
        buffered = io.BytesIO()
        Screenshot.save(buffered, format="PNG")

        # Get the byte value of the screenshot
        screenshot_bytes = buffered.getvalue()
        # Convert to base64 string.
        observation = {}
        observation["screenshot"] = screenshot_bytes

        planner_info, plan = self._generate_step_by_step_plan(
            observation,
            Tu,
            Failed_subtask,
            Completed_subtasks_list,
            Remaining_subtasks_list,
        )

        # Generate the DAG
        dag_info, dag = self._generate_dag(Tu, plan)

        # Topological sort of the DAG
        action_queue = self._topological_sort(dag)

        planner_info.update(dag_info)

        return planner_info, action_queue
