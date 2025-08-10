import logging
import re
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
import platform

from gui_agents.agents.grounding import ACI
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
from PIL import Image
import io
from gui_agents.agents.execution_monitor import ExecutionMonitor, Directive, StepResult
from gui_agents.agents.reflector import Reflector

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
        # Patch controls (defaults per spec)
        patch_enabled: bool = True,
        max_patches_per_step: int = 2,
        max_patches_per_subtask: Optional[int] = 5,
        scroll_delta_default: int = 120,
        wait_ms_default: int = 800,

    ):
        self.platform = platform
        self.Tools_dict = Tools_dict

        self.generator_agent = Tools()
        self.generator_agent.register_tool("subtask_planner", Tools_dict["subtask_planner"]["provider"], Tools_dict["subtask_planner"]["model"])

        self.dag_translator_agent = Tools()
        self.dag_translator_agent.register_tool("dag_translator", self.Tools_dict["dag_translator"]["provider"], self.Tools_dict["dag_translator"]["model"])

        self.narrative_summarization_agent = Tools()
        self.narrative_summarization_agent.register_tool("narrative_summarization", self.Tools_dict["narrative_summarization"]["provider"], self.Tools_dict["narrative_summarization"]["model"])

        self.episode_summarization_agent = Tools()
        self.episode_summarization_agent.register_tool("episode_summarization", self.Tools_dict["episode_summarization"]["provider"], self.Tools_dict["episode_summarization"]["model"])

        self.local_kb_path = local_kb_path

        self.embedding_engine = Tools()
        self.embedding_engine.register_tool("embedding", self.Tools_dict["embedding"]["provider"], self.Tools_dict["embedding"]["model"])
        KB_Tools_dict = {
            "embedding": self.Tools_dict["embedding"],
            "query_formulator": self.Tools_dict["query_formulator"],
            "context_fusion": self.Tools_dict["context_fusion"],
            "narrative_summarization": self.Tools_dict["narrative_summarization"],
            "episode_summarization": self.Tools_dict["episode_summarization"],
        }


        self.knowledge_base = KnowledgeBase(
            embedding_engine=self.embedding_engine,
            local_kb_path=self.local_kb_path,
            platform=platform,
            Tools_dict=KB_Tools_dict,
        )

        self.global_state: GlobalState = Registry.get("GlobalStateStore") # type: ignore

        self.planner_history = []

        self.turn_count = 0
        
        # Initialize search engine based on enable_search parameter
        if enable_search:
            self.search_engine = Tools()
            self.search_engine.register_tool("websearch", self.Tools_dict["websearch"]["provider"], self.Tools_dict["websearch"]["model"])
        else:
            self.search_engine = None

        self.multi_round = multi_round

        # Execution monitor owned by Manager
        self.exec_monitor = ExecutionMonitor(window=3)

        # Reflector owned by Manager
        self.reflector = Reflector(
            tools_dict=self.Tools_dict,
            tool_name="traj_reflector",
            logger_cb=lambda op, data: self.global_state.log_operation(
                module="manager", operation=op, data=data
            ),
        )

        # ---- Patch controls/state ----
        self.patch_enabled = patch_enabled
        self.scroll_delta_default = int(scroll_delta_default)
        self.wait_ms_default = int(wait_ms_default)
        self.max_patches_per_step = int(max_patches_per_step)
        self.max_patches_per_subtask = int(max_patches_per_subtask) if max_patches_per_subtask is not None else None
        # Counters
        self._patches_used_for_step: Dict[str, int] = {}
        self._patches_used_for_subtask: Dict[str, int] = {}

        # Per-subtask step counting for periodic reflection gating
        self._current_subtask_name: Optional[str] = None
        self._steps_in_current_subtask: int = 0

        # ---- Failure Learning ----
        self.failure_history: List[Dict] = []


    # ---------------- PatchPolicy: choose(patch) -----------------
    def _choose_patch(self, step_result: StepResult, last_action: Optional[str]) -> Dict:
        """Stage-1 simple policy per spec.
        - If the last original action was not a scroll -> scroll(+delta)
        - Else -> wait(wait_ms_default)
        """
        if (last_action is None) or ("scroll(" not in last_action.lower()):
            return {"type": "SCROLL", "delta": self.scroll_delta_default, "element_description": "center of screen"}
        return {"type": "WAIT", "duration": self.wait_ms_default}

    # ---------------- PatchBudget: allow(step_id) -----------------
    def _allow_patch(self, step_id: str, subtask_name: Optional[str]) -> bool:
        # Per-step budget
        used_for_step = self._patches_used_for_step.get(step_id, 0)
        if used_for_step >= self.max_patches_per_step:
            return False
        # Per-subtask budget (optional)
        if self.max_patches_per_subtask is not None and subtask_name is not None:
            used_for_subtask = self._patches_used_for_subtask.get(subtask_name, 0)
            if used_for_subtask >= self.max_patches_per_subtask:
                return False
        return True

    def _record_patch_use(self, step_id: str, subtask_name: Optional[str]) -> None:
        self._patches_used_for_step[step_id] = self._patches_used_for_step.get(step_id, 0) + 1
        if subtask_name is not None:
            self._patches_used_for_subtask[subtask_name] = self._patches_used_for_subtask.get(subtask_name, 0) + 1

    def _patch_count_for_step(self, step_id: str) -> int:
        return self._patches_used_for_step.get(step_id, 0)

    # ---------------- Failure Pattern Learning -----------------
    def learn_from_failure(self, subtask_id: str, failure_reason: str, action_taken: str, context: Optional[Dict] = None):
        
        # Store failure information in GlobalState for easy access by Worker
        failure_info = {
            'failure_reason': failure_reason,
            'failure_action': action_taken,
            'failure_context': context,
            'timestamp': time.time(),
            'last_action': action_taken,  # 记录最后的动作
            'step_count': context.get('step_count', 0) if context else 0,  # 记录步数
            'turn_count': context.get('turn_count', 0) if context else 0,  # 记录轮数
            'platform': context.get('platform', 'unknown') if context else 'unknown'  # 记录平台
        }
        
        self.global_state.add_failed_subtask_info(subtask_id, failure_info)
        
        logger.info(f"Manager learned from failure: {failure_reason} for subtask {subtask_id}")


    # manager给worker传递数据
    def get_guidance(self) -> str:
        """Get guidance for this subtask"""
        
        return ""

    def _get_recent_actions(self) -> List[str]:
        """Get recent actions for context"""
        # For now, return a simple list based on current state
        actions = []
        if hasattr(self, '_current_subtask_name') and self._current_subtask_name:
            actions.append(f"current_subtask: {self._current_subtask_name}")
        if hasattr(self, '_steps_in_current_subtask'):
            actions.append(f"steps_in_subtask: {self._steps_in_current_subtask}")
        return actions

    def summarize_episode(self, trajectory):
        """Summarize the episode experience for lifelong learning reflection
        Args:
            trajectory: str: The episode experience to be summarized
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
                "content": subtask_summarization,
                "input": trajectory
            }
        )

        return subtask_summarization

    def summarize_narrative(self, trajectory):
        """Summarize the narrative experience for lifelong learning reflection
        Args:
            trajectory: str: The narrative experience to be summarized
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
                "content": lifelong_learning_reflection,
                "input": trajectory
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
                    "duration": formulate_query_time,
                    "input": f"The task is: {instruction}"
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
                    "duration": narrative_time,
                    "input": instruction
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
                        "duration": knowledge_time,
                        "input": f"instruction: {instruction}, search_query: {self.search_query}"
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
                            "duration": fusion_time,
                            "input": f"Task: {instruction}\nWeb search result: {retrieved_knowledge}\nSimilar task: {most_similar_task}\nExperience: {retrieved_experience}"
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
            
            # Get detailed failure information
            failed_subtasks_info = self._get_failed_subtasks_summary()
            failure_context = ""
            if failed_subtasks_info:
                failure_context = f"\n\n❌ 失败任务详细信息:\n{failed_subtasks_info}"
            
            generator_message = (
                f"⚠️ 重要：子任务 '{failed_subtask.name}' 执行失败，需要重新规划剩余轨迹。\n\n"
                f"失败原因和上下文信息已在任务描述中提供，请仔细分析失败原因并生成改进的计划。\n\n"
                f"✅ 已成功完成的子任务:\n{format_subtask_list(completed_subtasks_list)}\n"
                f"{failure_context}\n"
                f"请参考代理日志了解任务进展和上下文:\n{agent_log}"
            )
        # Re-plan on subtask completion case
        elif len(completed_subtasks_list) + len(remaining_subtasks_list) > 0:
            agent_log = agent_log_to_string(self.global_state.get_agent_log())
            generator_message = (
                "📋 任务进展更新：当前轨迹和桌面状态已提供，请根据最新情况修订后续轨迹计划。\n\n"
                f"✅ 已成功完成的子任务:\n{format_subtask_list(completed_subtasks_list)}\n"
                f"🔄 待执行的剩余子任务:\n{format_subtask_list(remaining_subtasks_list)}\n"
                f"请参考代理日志了解任务进展和上下文:\n{agent_log}"
            )
        # Initial plan case
        else:
            generator_message = "🚀 初始规划：请为当前任务生成初始执行计划。\n"
        
        generator_message = prefix_message + "\n" + generator_message
        logger.info("GENERATOR MESSAGE: %s", generator_message)
        logger.info("GENERATING HIGH LEVEL PLAN")

        subtask_planner_start = time.time()
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
                "duration": subtask_planner_time,
                "input": generator_message
            }
        )
        
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
        dag_raw = ""
        total_tokens = 0
        cost_string = ""
        dag_input = f"Instruction: {instruction}\nPlan: {plan}"

        while retry_count < max_retries and dag is None:
            if retry_count > 0:
                logger.warning(f"Retrying DAG generation, attempt {retry_count}")
                self.global_state.log_operation(
                    module="manager",
                    operation="dag_retry",
                    data={"retry_count": retry_count}
                )
            
            # Generate DAG
            dag_raw, total_tokens, cost_string = self.dag_translator_agent.execute_tool("dag_translator", {"str_input": dag_input})
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
                "retry_count": retry_count,
                "input": dag_input
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
            # Get reflector insights if available
            reflector_insights = ""
            if hasattr(self, "reflector") and self.global_state.get_agent_log():
                try:
                    recent_actions = self.global_state.get_agent_log()[-10:]  # Last 10 actions
                    if recent_actions:
                        reflector_insights = self.reflector.reflect_agent_log(
                            recent_actions, "PLANNING_CONTEXT"
                        )
                        logger.info(f"Reflector insights for planning: {reflector_insights}")
                except Exception as e:
                    logger.warning(f"Failed to get reflector insights: {e}")

            # Get comprehensive failure information
            failed_subtasks_info = self._get_failed_subtasks_summary()
            
            # Enhance instruction with failure context and reflector insights
            enhanced_instruction = Tu
            if failed_subtasks_info:
                enhanced_instruction += f"\n\n📋 失败任务信息:\n{failed_subtasks_info}"
            if reflector_insights:
                enhanced_instruction += f"\n\n🔍 Reflector分析:\n{reflector_insights}"

            planner_info, plan = self._generate_step_by_step_plan(
                observation,
                enhanced_instruction,  # Use enhanced instruction
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
            
            # Enhance subtasks with failure patterns and guidance
            enhanced_action_queue = []
            # 只为失败的任务添加reflector信息，普通任务只添加失败指导
            for subtask in action_queue:
                # 检查这个任务是否是失败的任务
                is_failed_task = any(failed.name == subtask.name for failed in self.global_state.get_failed_subtasks())
                
                if is_failed_task:
                    # 失败的任务：添加完整的context（包括reflector信息）
                    context = {
                        "previous_actions": self._get_recent_actions(),
                        "current_platform": self.platform,
                        "timestamp": time.time(),
                        "failed_subtasks_info": failed_subtasks_info,
                        "reflector_insights": reflector_insights
                    }
                    enhanced_subtask = self.enhance_subtask_with_guidance(subtask, context)
                else:
                    # 普通任务：只添加失败指导，不添加reflector信息
                    context = {
                        "previous_actions": self._get_recent_actions(),
                        "current_platform": self.platform,
                        "timestamp": time.time(),
                        "failed_subtasks_info": failed_subtasks_info,
                        # 不包含 reflector_insights
                    }
                    enhanced_subtask = self.enhance_subtask_with_guidance(subtask, context)
                
                enhanced_action_queue.append(enhanced_subtask)
            
            action_queue = enhanced_action_queue

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

    def _get_failed_subtasks_summary(self) -> str:
        """Get a comprehensive summary of failed subtasks with reasons"""
        # 获取增强的失败任务信息
        failed_subtasks = self.global_state.get_failed_subtasks()
        failed_subtasks_info = self.global_state.get_failed_subtasks_info()
        
        if not failed_subtasks and not failed_subtasks_info:
            return ""
        
        summary = []
        
        # 使用新的Node字段信息
        if failed_subtasks:
            # Get last 5 failed subtasks
            recent_failures = failed_subtasks[-5:]
            
            for failed_node in recent_failures:
                summary.append(f"• {failed_node.name}: {failed_node.info}")
                
                if failed_node.error_type:
                    summary.append(f"  错误类型: {failed_node.error_type}")
                
                if failed_node.error_message:
                    summary.append(f"  错误信息: {failed_node.error_message}")
                
                if failed_node.failure_count and failed_node.failure_count > 1:
                    summary.append(f"  失败次数: {failed_node.failure_count}")
                
                if failed_node.suggested_action:
                    summary.append(f"  建议动作: {failed_node.suggested_action}")
        
        # 同时显示旧的详细信息（如果有的话）
        if failed_subtasks_info:
            summary.append("\n📋 详细失败信息:")
            recent_failures_info = list(failed_subtasks_info.items())[-3:]  # 只显示最近3个
            
            for subtask_name, failure_info in recent_failures_info:
                failure_reason = failure_info.get('failure_reason', 'Unknown reason')
                failure_action = failure_info.get('failure_action', 'Unknown action')
                step_count = failure_info.get('step_count', 0)
                turn_count = failure_info.get('turn_count', 0)
                
                summary.append(f"• {subtask_name}: {failure_reason}")
                summary.append(f"  动作: {failure_action}, 步数: {step_count}, 轮数: {turn_count}")
                
                # 如果是 reflector replan，显示更多信息
                if failure_action == "reflector_replan":
                    context = failure_info.get('failure_context', {})
                    reason = context.get('reason', 'unknown')
                    steps_in_subtask = context.get('steps_in_subtask', 0)
                    summary.append(f"  Reflector原因: {reason}, 子任务步数: {steps_in_subtask}")
        
        return "\n".join(summary)

    def enhance_subtask_with_guidance(self, subtask: Node, context: Optional[Dict] = None) -> Node:
        """Enhance subtask with comprehensive failure guidance and context"""
        guidance = self.get_failure_guidance(subtask.name)
        
        enhanced_info = subtask.info
        
        # Add failure guidance
        if guidance:
            enhanced_info += f"\n\n📖 失败指导:\n{guidance}"
        
        # Add context information if available
        if context:
            if context.get("failed_subtasks_info"):
                enhanced_info += f"\n\n📋 失败任务上下文:\n{context['failed_subtasks_info']}"
            
            # 只有当context中明确包含reflector_insights时才添加
            if context.get("reflector_insights") and context["reflector_insights"].strip():
                enhanced_info += f"\n\n🔍 Reflector分析:\n{context['reflector_insights']}"
        
        enhanced_subtask = Node(
            name=subtask.name,
            info=enhanced_info
        )
        return enhanced_subtask

    def handle_execution_feedback(self, result: Optional[StepResult]) -> Directive:
        """Accept step execution feedback and return a directive.

        Centralizes monitoring in Manager so that Manager can decide whether to
        continue, apply a small patch, or trigger replanning.
        """
        try:
            directive = self.exec_monitor.feed(result)
            # Log directive for observability
            self.global_state.log_operation(
                module="manager",
                operation="execution_feedback",
                data={
                    "step_id": getattr(result, "step_id", None),
                    "ok": getattr(result, "ok", None),
                    "error": getattr(result, "error", None),
                    "latency_ms": getattr(result, "latency_ms", None),
                    "action": getattr(result, "action", None),
                    "is_patch": getattr(result, "is_patch", False),
                    "directive": directive.name if hasattr(directive, "name") else str(directive),
                    "patch_count_for_step": self._patch_count_for_step(getattr(result, "step_id", "")) if result else 0,
                },
            )
            # Persist the action into GlobalState actions list, similar to subtasks
            try:
                if result is not None:
                    current_node = self.global_state.get_current_subtask()
                    self.global_state.add_action({
                        "step_id": result.step_id,
                        "action": result.action,
                        "ok": result.ok,
                        "error": result.error,
                        "latency_ms": result.latency_ms,
                        "is_patch": getattr(result, "is_patch", False),
                        "subtask_name": current_node.name if current_node else None,
                        "timestamp": time.time(),
                    })
                    
                    # Learn from failures for future improvement
                    if not result.ok and result.error:
                        subtask_name = current_node.name if current_node else "unknown"
                        context = {
                            "step_id": result.step_id,
                            "action": result.action,
                            "latency_ms": result.latency_ms,
                            "is_patch": getattr(result, "is_patch", False)
                        }
                        self.learn_from_failure(
                            subtask_id=subtask_name,
                            failure_reason=result.error,
                            action_taken=result.action if result.action else "unknown_action",
                            context=context
                        )
            except Exception:
                pass
            return directive
        except Exception:
            # On any unexpected issue, default to CONTINUE
            return Directive.CONTINUE

    def handle_post_exec(self, result: Optional[StepResult]) -> Tuple[Directive, Optional[Dict]]:
        """Single entry point for post-execution handling.

        - Feeds the execution monitor
        - Logs feedback consistently
        - If directive is PATCH, respects patch budget and returns a patch action
        - If over budget on PATCH, escalates to REPLAN
        Returns: (directive, patch_action)
        """
        directive = self.handle_execution_feedback(result)

        # Periodic reflection: every 3 actions within the same subtask, if not completed yet
        try:
            current_node = self.global_state.get_current_subtask()
            subtask_name: Optional[str] = current_node.name if current_node else None
            if subtask_name != self._current_subtask_name:
                self._current_subtask_name = subtask_name
                self._steps_in_current_subtask = 0

            if result is not None:
                self._steps_in_current_subtask += 1

            trigger_periodic_reflect = (
                subtask_name is not None and
                self._steps_in_current_subtask > 0 and
                self._steps_in_current_subtask % 3 == 0
            )

            if trigger_periodic_reflect and hasattr(self, "reflector") and getattr(self, "Tools_dict", None):
                # Get all steps for current subtask, not just recent 5
                all_recent: List[StepResult] = getattr(self.exec_monitor, "get_recent", lambda n=None: [])(None)  # type: ignore
                
                # Filter steps for current subtask based on step_id pattern
                # Assuming step_id contains subtask information or we can track subtask boundaries
                current_subtask_steps = []
                if subtask_name:
                    # Get all steps since the start of current subtask
                    # We'll use a simple heuristic: get all steps from the last subtask change
                    # This is a simplified approach - in a more robust implementation,
                    # we'd track subtask boundaries more precisely
                    current_subtask_steps = all_recent[-self._steps_in_current_subtask:] if self._steps_in_current_subtask > 0 else all_recent
                else:
                    # Fallback to recent steps if no subtask name
                    current_subtask_steps = all_recent[-5:] if len(all_recent) >= 5 else all_recent
                
                recent_summary = [
                    f"step_id={r.step_id}, ok={r.ok}, error={r.error}, latency_ms={r.latency_ms}, action={r.action}"
                    for r in current_subtask_steps
                ]
                recent_text = "\n".join(recent_summary) if recent_summary else "(no recent results)"

                decision = self.reflector.reflect_manager_decision(current_subtask_steps, f"PERIODIC_{self._steps_in_current_subtask}_STEPS_IN_SUBTASK_{subtask_name}")
                
                if decision == "REPLAN":
                    directive = Directive.REPLAN
                elif decision == "PATCH":
                    directive = Directive.PATCH
                elif decision == "CONTINUE":
                    # Keep current directive (CONTINUE), no intervention needed
                    directive = Directive.CONTINUE
                elif decision == "UNKNOWN":
                    # For UNKNOWN, use a conservative approach:
                    # - If there are errors, default to PATCH first
                    # - If no errors but actions are failing, default to REPLAN
                    # - Otherwise, continue
                    has_errors = any(r.error is not None for r in current_subtask_steps)
                    has_failures = any(not r.ok for r in current_subtask_steps)
                    
                    if has_errors:
                        directive = Directive.PATCH
                        logger.info(f"Reflector returned UNKNOWN, defaulting to PATCH due to errors")
                    elif has_failures:
                        directive = Directive.REPLAN
                        logger.info(f"Reflector returned UNKNOWN, defaulting to REPLAN due to failures")
                    else:
                        directive = Directive.CONTINUE
                        logger.info(f"Reflector returned UNKNOWN, defaulting to CONTINUE")
                else:
                    # Fallback for any unexpected decision
                    directive = Directive.CONTINUE
                    logger.warning(f"Unexpected reflector decision: {decision}, defaulting to CONTINUE")

                self.global_state.log_operation(
                    module="manager",
                    operation="reflector_decision",
                    data={
                        "reason": f"PERIODIC_{self._steps_in_current_subtask}_STEPS_IN_SUBTASK_{subtask_name}",
                        "decision": directive.name,
                        "reflector_decision": decision,
                        "recent": recent_text,
                        "subtask": subtask_name,
                        "steps_in_subtask": self._steps_in_current_subtask,
                    },
                )
                
                # 如果 reflector 决定 REPLAN，直接记录到 failed_subtasks
                if decision == "REPLAN" and subtask_name:
                    failure_info = {
                        "failure_reason": f"Reflector triggered REPLAN: {recent_text}",
                        "failure_action": "reflector_replan",
                        "failure_context": {
                            "reflector_decision": decision,
                            "reason": f"PERIODIC_{self._steps_in_current_subtask}_STEPS_IN_SUBTASK_{subtask_name}",
                            "steps_in_subtask": self._steps_in_current_subtask,
                            "recent_actions": recent_text
                        },
                        "step_count": len(current_subtask_steps),
                        "turn_count": self.turn_count,
                        "platform": getattr(self, "platform", "unknown")
                    }
                    self.global_state.add_failed_subtask_info(subtask_name, failure_info)
                    
                    # 同时使用新的方法创建增强的失败任务记录
                    self.global_state.add_failed_subtask_with_info(
                        name=subtask_name,
                        info=f"Reflector triggered REPLAN after {self._steps_in_current_subtask} steps",
                        error_type="REFLECTOR_REPLAN",
                        error_message=failure_info["failure_reason"],
                        suggested_action="replan_subtask"
                    )
        except Exception as e:
            logger.warning(f"Periodic reflector gating failed: {e}")

        if directive == Directive.PATCH:
            should_patch, patch_action, over_budget = self.maybe_get_patch(result)
            if over_budget:
                # Treat as REPLAN when patch budget is exceeded
                return Directive.REPLAN, None
            if should_patch and patch_action is not None:
                # Return patch action to caller to inject
                return Directive.PATCH, patch_action
            # If no patch selected, just continue with current directive
            return directive, None

        return directive, None

    # Orchestrated manager loop hook (called from AgentS2.predict): returns (should_patch, patch_action, exceeded_budget)
    def maybe_get_patch(self, step_result: Optional[StepResult]) -> Tuple[bool, Optional[Dict], bool]:
        if (not self.patch_enabled) or (step_result is None):
            return False, None, False
        # The caller should only invoke this when a PATCH directive has already been issued.
        # Avoid double-feeding the monitor here.

        # Budgeting
        current_node = self.global_state.get_current_subtask()
        subtask_name: Optional[str] = current_node.name if current_node else None
        if not self._allow_patch(step_result.step_id, subtask_name):
            # Over budget -> request REPLAN
            self.global_state.log_operation(
                module="manager",
                operation="directive_patch_over_budget",
                data={
                    "step_id": step_result.step_id,
                    "patch_count_for_step": self._patch_count_for_step(step_result.step_id),
                    "max_patches_per_step": self.max_patches_per_step,
                },
            )
            return False, None, True
        # Choose and return patch (do not read from worker; rely on the last executed action)
        patch_action = self._choose_patch(step_result, step_result.action)
        self._record_patch_use(step_result.step_id, subtask_name)
        self.global_state.log_operation(
            module="manager",
            operation="directive_patch_chosen",
            data={
                "step_id": step_result.step_id,
                "patch_action": patch_action,
                "patch_count_for_step": self._patch_count_for_step(step_result.step_id),
            },
        )
        return True, patch_action, False