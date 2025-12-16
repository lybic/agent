#!/usr/bin/env python3
"""
RESTful API server for Lybic GUI Agent using FastAPI.
Implements similar functionality to grpc_app.py with HTTP/REST interface.
"""
import os
from pathlib import Path
import logging
import asyncio
import time
import uuid
import datetime
import platform
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load environment variables
env_path = Path(os.path.dirname(os.path.abspath(__file__))) / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    parent_env_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / '.env'
    if parent_env_path.exists():
        load_dotenv(dotenv_path=parent_env_path)
    else:
        print("Warning: no .env file found")

# Configure logging
logger = logging.getLogger(__name__)
level = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=level,
    format='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger.info("Initializing RESTful Agent server")

# Import FastAPI and related
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

# Import GUI agent components
from lybic import LybicClient, LybicAuth, Sandbox
import gui_agents.cli_app as cli_app
from gui_agents.agents.stream_manager import stream_manager
from gui_agents.agents.agent_s import load_config, AgentSFast, UIAgent
from gui_agents import Registry, GlobalState, AgentS2, HardwareInterface, __version__
from gui_agents.utils.analyze_display import analyze_display_json
from gui_agents.storage import create_storage, TaskData
from gui_agents.metrics import get_metrics_instance
from gui_agents.utils.conversation_utils import (
    extract_all_conversation_history_from_agent,
    restore_all_conversation_history_to_agent
)

class LybicAuthentication(BaseModel):
    """Lybic authentication credentials"""
    api_key: str = Field(..., description="Lybic API key")
    org_id: str = Field(..., description="Lybic organization ID")
    api_endpoint: Optional[str] = Field(None, description="Lybic API endpoint (optional)")


class LLMConfig(BaseModel):
    """LLM configuration for specific model"""
    model_name: str = Field(..., description="Model name (e.g., gpt-4, claude-3-5-sonnet-20241022)")
    provider: Optional[str] = Field(None, description="Provider name (e.g., openai, anthropic, google)")
    api_key: Optional[str] = Field(None, description="API key for this model")
    api_endpoint: Optional[str] = Field(None, description="API endpoint for this model")


class StageModelConfig(BaseModel):
    """Stage-specific model configurations for different agent components"""
    web_search_engine: Optional[str] = Field(None, description="Web search engine to use")
    context_fusion_model: Optional[LLMConfig] = Field(None, description="Context fusion model config")
    subtask_planner_model: Optional[LLMConfig] = Field(None, description="Subtask planner model config")
    traj_reflector_model: Optional[LLMConfig] = Field(None, description="Trajectory reflector model config")
    memory_retrival_model: Optional[LLMConfig] = Field(None, description="Memory retrieval model config")
    grounding_model: Optional[LLMConfig] = Field(None, description="Grounding model config")
    task_evaluator_model: Optional[LLMConfig] = Field(None, description="Task evaluator model config")
    action_generator_model: Optional[LLMConfig] = Field(None, description="Action generator model config")
    action_generator_with_takeover_model: Optional[LLMConfig] = Field(None, description="Action generator with takeover model config")
    fast_action_generator_model: Optional[LLMConfig] = Field(None, description="Fast action generator model config")
    fast_action_generator_with_takeover_model: Optional[LLMConfig] = Field(None, description="Fast action generator with takeover model config")
    dag_translator_model: Optional[LLMConfig] = Field(None, description="DAG translator model config")
    embedding_model: Optional[LLMConfig] = Field(None, description="Embedding model config")
    query_formulator_model: Optional[LLMConfig] = Field(None, description="Query formulator model config")
    narrative_summarization_model: Optional[LLMConfig] = Field(None, description="Narrative summarization model config")
    text_span_model: Optional[LLMConfig] = Field(None, description="Text span model config")
    episode_summarization_model: Optional[LLMConfig] = Field(None, description="Episode summarization model config")


class RunAgentRequest(BaseModel):
    """Request to run agent with streaming response"""
    instruction: str = Field(..., description="Task instruction in natural language")
    user_system_prompt: Optional[str] = Field(None, description="Custom system prompt (not implemented)")
    sandbox_id: Optional[str] = Field(None, description="Existing sandbox ID to use")
    continue_context: bool = Field(False, description="Continue from previous task context")
    task_id: Optional[str] = Field(None, description="Previous task ID for context continuation")
    authentication: Optional[LybicAuthentication] = Field(None, description="Lybic authentication")
    stage_model_config: Optional[StageModelConfig] = Field(None, description="Stage-specific model configurations")
    max_steps: int = Field(50, description="Maximum steps for task execution")
    mode: str = Field("fast", description="Agent mode: 'normal' or 'fast'")
    destroy_sandbox: bool = Field(False, description="Destroy sandbox after task completion")
    shape: str = Field("beijing-2c-4g-cpu", description="Sandbox shape/size")
    platform: str = Field("Windows", description="Platform: Windows, Ubuntu, or Android")


class SubmitTaskRequest(BaseModel):
    """Request to submit task asynchronously"""
    instruction: str = Field(..., description="Task instruction in natural language")
    user_system_prompt: Optional[str] = Field(None, description="Custom system prompt (not implemented)")
    sandbox_id: Optional[str] = Field(None, description="Existing sandbox ID to use")
    max_steps: int = Field(50, description="Maximum steps for task execution")
    continue_context: bool = Field(False, description="Continue from previous task context")
    task_id: Optional[str] = Field(None, description="Previous task ID for context continuation")
    authentication: Optional[LybicAuthentication] = Field(None, description="Lybic authentication")
    stage_model_config: Optional[StageModelConfig] = Field(None, description="Stage-specific model configurations")
    mode: str = Field("fast", description="Agent mode: 'normal' or 'fast'")
    destroy_sandbox: bool = Field(False, description="Destroy sandbox after task completion")
    shape: str = Field("beijing-2c-4g-cpu", description="Sandbox shape/size")
    platform: str = Field("Windows", description="Platform: Windows, Ubuntu, or Android")


class CancelRequest(BaseModel):
    """Request to cancel a task"""
    task_id: Optional[str] = Field(None, description="Task ID to cancel")
    authentication: Optional[LybicAuthentication] = Field(None, description="Lybic authentication (not used)")


class CreateSandboxRequest(BaseModel):
    """Request to create a sandbox"""
    name: str = Field("sandbox", description="The name of the sandbox")
    maxLifeSeconds: int = Field(3600, ge=1, le=86400, description="Maximum life time in seconds")
    projectId: Optional[str] = Field(None, description="Project ID to use")
    shape: str = Field(..., description="Specs and datacenter of the sandbox")
    authentication: Optional[LybicAuthentication] = Field(None, description="Lybic authentication")


class TaskStatusResponse(BaseModel):
    """Task status response"""
    task_id: str
    status: str
    message: str
    result: Optional[Dict[str, Any]] = None
    sandbox: Optional[Dict[str, Any]] = None
    execution_statistics: Optional[Dict[str, Any]] = None


class AgentInfoResponse(BaseModel):
    """Agent server info response"""
    version: str
    max_concurrent_tasks: int
    log_level: str
    domain: str


# Service implementation (similar to grpc_app.py AgentServicer)
class RestfulAgentService:
    """RESTful Agent Service implementation"""
    
    def __init__(self, max_concurrent_task_num: int = 1, log_dir: str = "runtime"):
        self.max_concurrent_task_num = max_concurrent_task_num
        self.tasks = {}  # Runtime-only data (agent, queue, future)
        self.storage = create_storage()  # Persistent task data storage
        self.task_lock = asyncio.Lock()
        self.log_dir = log_dir
        self.metrics = get_metrics_instance()
        
        # Track task timing for metrics
        self.task_start_times = {}
        self.task_created_times = {}
        
        # Global authentication (can be overridden per request)
        self.global_auth = self._load_global_auth()
    
    def _load_global_auth(self) -> Optional[LybicAuthentication]:
        """Load global authentication from environment"""
        api_key = os.environ.get("LYBIC_API_KEY")
        org_id = os.environ.get("LYBIC_ORG_ID")
        api_endpoint = os.environ.get("LYBIC_API_ENDPOINT", "https://api.lybic.cn/")
        
        if api_key and org_id:
            return LybicAuthentication(
                api_key=api_key,
                org_id=org_id,
                api_endpoint=api_endpoint
            )
        return None
    
    def _setup_task_state(self, task_id: str) -> tuple:
        """Setup global state and registry for task execution"""
        datetime_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        timestamp_dir = Path(self.log_dir) / f"{datetime_str}_{task_id[:8]}"
        cache_dir = timestamp_dir / "cache" / "screens"
        state_dir = timestamp_dir / "state"

        cache_dir.mkdir(parents=True, exist_ok=True)
        state_dir.mkdir(parents=True, exist_ok=True)

        # Create task-specific registry
        task_registry = Registry()

        # Register global state
        global_state = GlobalState(
            screenshot_dir=str(cache_dir),
            tu_path=str(state_dir / "tu.json"),
            search_query_path=str(state_dir / "search_query.json"),
            completed_subtasks_path=str(state_dir / "completed_subtasks.json"),
            failed_subtasks_path=str(state_dir / "failed_subtasks.json"),
            remaining_subtasks_path=str(state_dir / "remaining_subtasks.json"),
            termination_flag_path=str(state_dir / "termination_flag.json"),
            running_state_path=str(state_dir / "running_state.json"),
            display_info_path=str(timestamp_dir / "display.json"),
            agent_log_path=str(timestamp_dir / "agent_log.json")
        )

        registry_key = "GlobalStateStore"
        task_registry.register_instance(registry_key, global_state)

        logger.info(f"Created task-specific registry for task {task_id}")

        return task_registry, timestamp_dir
    
    def _backend_kwargs_get_agent_backend(self, backend_kwargs) -> str:
        """Determine backend type from platform"""
        arg = backend_kwargs.get("platform", "windows").lower()
        if arg == 'windows' or arg == 'ubuntu':
            return 'lybic'
        elif arg == 'android':
            return 'lybic_mobile'
        raise ValueError(f"Unsupported platform for backend: {arg}")
    
    async def _make_agent(self, mode: str, stage_model_config: Optional[StageModelConfig] = None, platform: str = "Windows") -> UIAgent:
        """
        Create agent with stage-specific model configurations.
        
        Parameters:
            mode: Agent mode ('normal' or 'fast')
            stage_model_config: Optional stage-specific model configurations
            platform: Target platform (Windows, Ubuntu, Android)
            
        Returns:
            UIAgent: Configured agent instance
        """
        tools_config, tools_dict = load_config()
        
        # Apply stage model configurations if provided
        if stage_model_config:
            logger.info("Applying stage model configurations to this task")
            
            def apply_config(tool_name: str, llm_config: Optional[LLMConfig]) -> None:
                """Apply LLM configuration to a tool."""
                if tool_name not in tools_dict or not llm_config or not llm_config.model_name:
                    return

                tool_cfg = tools_dict[tool_name]
                if llm_config.provider:
                    tool_cfg['provider'] = llm_config.provider

                tool_cfg['model_name'] = llm_config.model_name
                tool_cfg['model'] = llm_config.model_name

                # Override api_key and endpoint if provided
                if llm_config.api_key:
                    tool_cfg['api_key'] = llm_config.api_key
                    logger.info(f"Override api_key for tool '{tool_name}'")
                if llm_config.api_endpoint:
                    tool_cfg['base_url'] = llm_config.api_endpoint
                    tool_cfg['endpoint_url'] = llm_config.api_endpoint
                    logger.info(f"Override base_url for tool '{tool_name}': {llm_config.api_endpoint}")

                logger.info(f"Override tool '{tool_name}' with model '{llm_config.model_name}'")

            # Web search provider override (bocha/exa)
            if stage_model_config.web_search_engine and 'websearch' in tools_dict:
                tools_dict['websearch']['provider'] = stage_model_config.web_search_engine
                logger.info(f"Override websearch provider to '{stage_model_config.web_search_engine}'")

            # Optional: apply action_generator_model as a common default to all LLM-based tools
            if stage_model_config.action_generator_model:
                common_llm_config = stage_model_config.action_generator_model
                for tool_name in tools_dict.keys():
                    if tool_name not in ['websearch', 'embedding', 'grounding']:
                        apply_config(tool_name, common_llm_config)

            # Stage-specific overrides
            stage_field_to_tool = {
                'context_fusion_model': 'context_fusion',
                'subtask_planner_model': 'subtask_planner',
                'traj_reflector_model': 'traj_reflector',
                'memory_retrival_model': 'memory_retrival',
                'grounding_model': 'grounding',
                'task_evaluator_model': 'evaluator',
                'action_generator_model': 'action_generator',
                'action_generator_with_takeover_model': 'action_generator_with_takeover',
                'fast_action_generator_model': 'fast_action_generator',
                'fast_action_generator_with_takeover_model': 'fast_action_generator_with_takeover',
                'dag_translator_model': 'dag_translator',
                'embedding_model': 'embedding',
                'query_formulator_model': 'query_formulator',
                'narrative_summarization_model': 'narrative_summarization',
                'text_span_model': 'text_span',
                'episode_summarization_model': 'episode_summarization',
            }
            for field_name, tool_name in stage_field_to_tool.items():
                apply_config(tool_name, getattr(stage_model_config, field_name, None))
            
            # Merge changes from tools_dict back into tools_config
            for tool_entry in tools_config['tools']:
                tool_name = tool_entry['tool_name']
                if tool_name in tools_dict:
                    modified_data = tools_dict[tool_name]
                    for key, value in modified_data.items():
                        if key in ['provider', 'model_name', 'api_key', 'base_url', 'model', 'endpoint_url']:
                            tool_entry[key] = value
        
        # Determine platform string for agent
        platform_str = "windows" if platform.lower() in ["windows", "ubuntu"] else "android"
        
        # Create agent based on mode
        if mode.lower() == "normal":
            return AgentS2(
                platform=platform_str,
                screen_size=[1280, 720],
                enable_takeover=False,
                enable_search=False,
                tools_config=tools_config,
            )
        else:  # fast mode
            return AgentSFast(
                platform=platform_str,
                screen_size=[1280, 720],
                enable_takeover=False,
                enable_search=False,
                tools_config=tools_config,
            )
    
    async def _make_backend_kwargs(self, request) -> Dict[str, Any]:
        """Build backend kwargs from request"""
        backend_kwargs = {}
        
        # Get authentication
        auth = request.authentication or self.global_auth
        if not auth:
            raise HTTPException(status_code=401, detail="Lybic backend requires valid authentication (org_id and api_key)")
        
        lybic_auth = LybicAuth(
            org_id=auth.org_id,
            api_key=auth.api_key,
            endpoint=auth.api_endpoint or "https://api.lybic.cn/"
        )
        
        # Handle continue_context: get sandbox from previous task
        previous_sandbox_id = None
        if request.continue_context and request.task_id:
            previous_task = await self.storage.get_task(request.task_id)
            if not previous_task:
                raise HTTPException(status_code=400, detail=f"Previous task {request.task_id} not found")
            
            if previous_task.sandbox_info and previous_task.sandbox_info.get("id"):
                previous_sandbox_id = previous_task.sandbox_info["id"]
                logger.info(f"Retrieved sandbox_id {previous_sandbox_id} from previous task {request.task_id}")
                
                # Validate sandbox exists and is not expired
                try:
                    await self._get_sandbox_pb(previous_sandbox_id, lybic_auth)
                except Exception as e:
                    from lybic.exceptions import LybicAPIError
                    if isinstance(e, LybicAPIError):
                        error_msg = str(e)
                        if "SANDBOX_EXPIRED" in error_msg or "expired" in error_msg.lower():
                            raise HTTPException(status_code=400, detail=f"Sandbox {previous_sandbox_id} from task {request.task_id} is expired")
                        elif "not found" in error_msg.lower():
                            raise HTTPException(status_code=400, detail=f"Sandbox {previous_sandbox_id} from task {request.task_id} not found")
                    raise HTTPException(status_code=400, detail=f"Failed to access sandbox {previous_sandbox_id} from task {request.task_id}: {str(e)}")
                
                # Validate sandbox_id consistency if both are provided
                if request.sandbox_id and request.sandbox_id != previous_sandbox_id:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Sandbox ID mismatch: request has {request.sandbox_id} but task {request.task_id} used {previous_sandbox_id}"
                    )
        
        # Handle sandbox creation or retrieval
        sid = request.sandbox_id or previous_sandbox_id or ""
        platform_str = request.platform
        sandbox_pb = None
        
        if sid:
            logger.info(f"Using existing sandbox with id: {sid}")
            sandbox_pb = await self._get_sandbox_pb(sid, lybic_auth)
        else:
            sandbox_pb = await self._create_sandbox(request.shape, lybic_auth)
            sid = sandbox_pb.id
        
        backend_kwargs["sandbox"] = sandbox_pb
        backend_kwargs["platform"] = platform_str
        backend_kwargs["precreate_sid"] = sid
        backend_kwargs['org_id'] = auth.org_id
        backend_kwargs['api_key'] = auth.api_key
        backend_kwargs['endpoint'] = auth.api_endpoint or "https://api.lybic.cn/"
        backend_kwargs["mode"] = request.mode
        
        return backend_kwargs
    
    async def _create_sandbox(self, shape: str, lybic_auth: LybicAuth):
        """Create a sandbox via Lybic API"""
        async with LybicClient(lybic_auth) as lybic_client:
            result = await lybic_client.sandbox.create(shape=shape)
            sandbox = await lybic_client.sandbox.get(result.id)

        # Create simple namespace object to mimic protobuf
        class SandboxInfo:
            def __init__(self, id, shape_name):
                self.id = id
                self.shapeName = shape_name
        
        sandbox_info = SandboxInfo(
            id=sandbox.sandbox.id,
            shape_name=sandbox.sandbox.shapeName
        )
        
        # Record metric
        self.metrics.record_sandbox_created(shape)
        
        return sandbox_info
    
    async def _get_sandbox_pb(self, sid: str, lybic_auth: LybicAuth):
        """Get sandbox details"""
        async with LybicClient(lybic_auth) as lybic_client:
            sandbox = await lybic_client.sandbox.get(sid)
        
        class SandboxInfo:
            def __init__(self, id, shape_name):
                self.id = id
                self.shapeName = shape_name
        
        return SandboxInfo(
            id=sandbox.sandbox.id,
            shape_name=sandbox.sandbox.shapeName
        )
    
    def _sandbox_to_dict(self, sandbox) -> dict:
        """Convert sandbox object to dictionary"""
        if not sandbox:
            return {}
        
        return {
            "id": sandbox.id if hasattr(sandbox, 'id') else "",
            "shape_name": sandbox.shapeName if hasattr(sandbox, 'shapeName') else "",
        }
    
    async def _run_task(self, task_id: str, backend_kwargs):
        """Execute agent task (similar to grpc_app._run_task)"""
        task_start_time = time.time()

        async with self.task_lock:
            await self.storage.update_task(task_id, {"status": "running"})
            
            if task_id in self.task_created_times:
                queue_wait = task_start_time - self.task_created_times[task_id]
                self.metrics.record_task_queue_wait(queue_wait)
            
            self.task_start_times[task_id] = task_start_time
            
            task_info = self.tasks.get(task_id)
            if not task_info:
                raise ValueError(f"Task {task_id} not found in runtime data")
            
            agent = task_info["agent"]
            steps = task_info["max_steps"]
            query = task_info["query"]
            destroy_sandbox = task_info.get("destroy_sandbox", False)
            mode = task_info.get("mode", "fast")

            await stream_manager.register_task(task_id)
            
            active_count = await self.storage.count_active_tasks()
            self.metrics.record_task_active(active_count)
            self.metrics.record_task_utilization(active_count, self.max_concurrent_task_num)

        try:
            await stream_manager.add_message(task_id, "starting", "Task starting")

            task_registry, timestamp_dir = self._setup_task_state(task_id)
            await self.storage.update_task(task_id, {"timestamp_dir": str(timestamp_dir)})

            if hasattr(agent, 'set_task_id'):
                agent.set_task_id(task_id)

            hwi = HardwareInterface(backend=self._backend_kwargs_get_agent_backend(backend_kwargs), **backend_kwargs)

            Registry.set_task_registry(task_id, task_registry)
            agent.reset()
            Registry.remove_task_registry(task_id)

            # Run agent
            if mode and mode.lower() == "normal":
                await asyncio.to_thread(cli_app.run_agent_normal, agent, query, hwi, steps, False, destroy_sandbox, task_id=task_id, task_registry=task_registry)
            else:
                await asyncio.to_thread(cli_app.run_agent_fast, agent, query, hwi, steps, False, destroy_sandbox, task_id=task_id, task_registry=task_registry)

            final_state = "completed"

            await self.storage.update_task(task_id, {
                "final_state": final_state,
                "status": "finished"
            })
            
            await self._collect_execution_statistics(task_id)
            await self._save_conversation_history(task_id, agent)

            if final_state == "completed":
                await stream_manager.add_message(task_id, "finished", "Task completed successfully")
            else:
                await stream_manager.add_message(task_id, "finished", f"Task finished with status: {final_state}")

        except asyncio.CancelledError:
            logger.info(f"Task {task_id} was canceled")
            await self.storage.update_task(task_id, {"status": "canceled"})
            await stream_manager.add_message(task_id, "canceled", "Task was canceled")
            self.metrics.record_task_created("canceled")
        except Exception as e:
            logger.exception(f"Error during task execution for {task_id}: {e}")
            await self.storage.update_task(task_id, {"status": "error"})
            await stream_manager.add_message(task_id, "error", f"An error occurred: {e}")
            self.metrics.record_task_created("failed")
        finally:
            logger.info(f"Task {task_id} processing finished.")

            async with self.task_lock:
                if task_id in self.task_start_times:
                    duration = time.time() - self.task_start_times[task_id]
                    self.metrics.record_task_execution_duration(duration)
                    del self.task_start_times[task_id]

                if task_id in self.task_created_times:
                    del self.task_created_times[task_id]

                if task_id in self.tasks:
                    del self.tasks[task_id]

            active_count = await self.storage.count_active_tasks()
            self.metrics.record_task_active(active_count)
            self.metrics.record_task_utilization(active_count, self.max_concurrent_task_num)
            
            await stream_manager.unregister_task(task_id)
    
    async def _collect_execution_statistics(self, task_id: str):
        """Collect execution statistics from display.json"""
        try:
            task_data = await self.storage.get_task(task_id)
            if not task_data or not task_data.timestamp_dir:
                logger.warning(f"No timestamp_dir found for task {task_id}")
                return
            
            display_json_path = Path(task_data.timestamp_dir) / "display.json"
            
            # Wait for file to be written
            max_wait_time = 10
            wait_interval = 0.5
            waited_time = 0
            
            while waited_time < max_wait_time:
                if display_json_path.exists():
                    try:
                        size1 = display_json_path.stat().st_size
                        await asyncio.sleep(wait_interval)
                        size2 = display_json_path.stat().st_size
                        
                        if size1 == size2 and size1 > 0:
                            logger.info(f"Display.json file complete (size: {size1} bytes)")
                            break
                        elif size1 == size2 and size1 == 0:
                            waited_time += wait_interval
                            continue
                        else:
                            waited_time += wait_interval
                            continue
                    except OSError:
                        await asyncio.sleep(wait_interval)
                        waited_time += wait_interval
                        continue
                else:
                    await asyncio.sleep(wait_interval)
                    waited_time += wait_interval
            
            if display_json_path.exists():
                logger.info(f"Collecting execution statistics from: {display_json_path}")
                result = analyze_display_json(str(display_json_path))
                
                if result:
                    execution_statistics = {
                        "steps": result.get("fast_action_count", 0),
                        "duration_seconds": result.get("total_duration", 0),
                        "input_tokens": result.get("total_input_tokens", 0),
                        "output_tokens": result.get("total_output_tokens", 0),
                        "total_tokens": result.get("total_tokens", 0),
                        "cost": result.get("total_cost", 0.0),
                        "currency_symbol": result.get("currency_symbol", "￥")
                    }
                    
                    await self.storage.update_task(task_id, {
                        "execution_statistics": execution_statistics
                    })
                    
                    self.metrics.record_tokens(
                        execution_statistics["input_tokens"],
                        execution_statistics["output_tokens"]
                    )
                    self.metrics.record_cost(
                        execution_statistics["cost"],
                        execution_statistics["currency_symbol"]
                    )
                    self.metrics.record_task_steps(execution_statistics["steps"])
                    
                    logger.info(f"Execution statistics collected for task {task_id}")
                    
        except Exception as e:
            logger.error(f"Error collecting execution statistics for task {task_id}: {e}")
    
    async def _save_conversation_history(self, task_id: str, agent):
        """Extract and save conversation history"""
        try:
            logger.info(f"Extracting conversation history for task {task_id}")
            conversation_history = extract_all_conversation_history_from_agent(agent)
            
            if conversation_history:
                await self.storage.update_task(task_id, {
                    "conversation_history": conversation_history
                })
                total_messages = sum(len(history) for history in conversation_history.values())
                logger.info(f"Saved conversation history for task {task_id}: {total_messages} messages")
            else:
                logger.warning(f"No conversation history extracted for task {task_id}")
                
        except Exception as e:
            logger.error(f"Error saving conversation history for task {task_id}: {e}")
    
    async def _restore_conversation_history(self, previous_task_id: str, agent):
        """Restore conversation history from previous task"""
        try:
            logger.info(f"Restoring conversation history from previous task {previous_task_id}")
            previous_task_data = await self.storage.get_task(previous_task_id)
            
            if not previous_task_data:
                logger.warning(f"Previous task {previous_task_id} not found")
                return
            
            if not previous_task_data.conversation_history:
                logger.warning(f"No conversation history found for previous task {previous_task_id}")
                return
            
            restore_all_conversation_history_to_agent(agent, previous_task_data.conversation_history)
            total_messages = sum(len(history) for history in previous_task_data.conversation_history.values())
            logger.info(f"Restored conversation history: {total_messages} messages")
                
        except Exception as e:
            logger.error(f"Error restoring conversation history from task {previous_task_id}: {e}")


# Create service instance
service: Optional[RestfulAgentService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    global service
    
    # Startup
    max_tasks = int(os.environ.get("TASK_MAX_TASKS", 5))
    service = RestfulAgentService(max_concurrent_task_num=max_tasks, log_dir=cli_app.log_dir)
    
    # Configure stream manager
    stream_manager.set_loop(asyncio.get_running_loop())
    
    # Initialize metrics if enabled
    metrics = get_metrics_instance()
    if metrics.enabled:
        prometheus_port = int(os.environ.get("PROMETHEUS_PORT", 8000))
        metrics.start_http_server(prometheus_port)
        metrics.update_service_info(
            version=__version__,
            max_concurrent_tasks=max_tasks,
            log_level=level,
            domain=platform.node()
        )
    
    logger.info(f"RESTful Agent server started with {max_tasks} max concurrent tasks")
    
    yield
    
    # Shutdown
    logger.info("Shutting down RESTful Agent server")


# Create FastAPI app
app = FastAPI(
    title="Lybic GUI Agent RESTful API",
    description="RESTful API for GUI automation using Lybic GUI Agent",
    version=__version__,
    lifespan=lifespan
)

# Store log_dir on app for access in lifespan
cli_app.log_dir = os.environ.get("LOG_DIR", "runtime")


# API Endpoints
@app.get("/api/agent/info", response_model=AgentInfoResponse)
async def get_agent_info():
    """Get agent server info"""
    return AgentInfoResponse(
        version=__version__,
        max_concurrent_tasks=service.max_concurrent_task_num,
        log_level=level,
        domain=platform.node()
    )


@app.post("/api/agent/run")
async def run_agent(request: RunAgentRequest):
    """Run agent with streaming response (Server-Sent Events)"""
    task_id = str(uuid.uuid4())
    logger.info(f"Received /api/agent/run request, assigning task_id: {task_id}")
    
    service.metrics.record_grpc_request("RunAgent")
    
    task_created = False
    task_future = None
    
    try:
        async with service.task_lock:
            active_tasks = await service.storage.count_active_tasks()
            if active_tasks >= service.max_concurrent_task_num:
                service.metrics.record_grpc_error("RunAgent", "RESOURCE_EXHAUSTED")
                raise HTTPException(
                    status_code=503,
                    detail=f"Max concurrent tasks ({service.max_concurrent_task_num}) reached"
                )
            
            # Create agent
            agent = await service._make_agent(request.mode, request.stage_model_config, request.platform)
            
            # Restore conversation history if requested
            if request.continue_context and request.task_id:
                await service._restore_conversation_history(request.task_id, agent)
            
            # Prepare backend kwargs
            backend_kwargs = await service._make_backend_kwargs(request)
            
            # Store task data
            sandbox_info = service._sandbox_to_dict(backend_kwargs["sandbox"])
            task_data = TaskData(
                task_id=task_id,
                status="pending",
                query=request.instruction,
                max_steps=request.max_steps,
                sandbox_info=sandbox_info,
                request_data=request.model_dump()
            )
            await service.storage.create_task(task_data)
            
            service.metrics.record_task_created("pending")
            service.task_created_times[task_id] = time.time()
            
            # Store runtime data
            service.tasks[task_id] = {
                "agent": agent,
                "queue": None,
                "future": None,
                "query": request.instruction,
                "max_steps": request.max_steps,
                "destroy_sandbox": request.destroy_sandbox,
                "mode": request.mode,
            }
            task_created = True
            
            # Remove sandbox object from backend_kwargs before passing to _run_task
            # The sandbox info has been stored in task_data, and keeping it in backend_kwargs
            # can cause serialization issues in some backend implementations
            del backend_kwargs["sandbox"]
            
            # Start task
            task_future = asyncio.create_task(service._run_task(task_id, backend_kwargs))
            service.tasks[task_id]["future"] = task_future
    
    except Exception as e:
        logger.exception(f"Error initializing task {task_id}: {e}")
        if task_created:
            async with service.task_lock:
                service.tasks.pop(task_id, None)
                service.task_created_times.pop(task_id, None)
        service.metrics.record_grpc_error("RunAgent", "INTERNAL")
        raise HTTPException(status_code=500, detail=f"Failed to initialize task: {e}")
    
    # Stream events
    async def event_generator():
        try:
            async for msg in stream_manager.get_message_stream(task_id):
                yield {
                    "event": msg.stage,
                    "data": {
                        "task_id": task_id,
                        "stage": msg.stage,
                        "message": msg.message,
                        "timestamp": msg.timestamp
                    }
                }
        except asyncio.CancelledError:
            logger.info(f"Stream for task {task_id} canceled by client")
            if task_future:
                task_future.cancel()
                try:
                    global_state: GlobalState = Registry.get_from_context("GlobalStateStore", task_id)
                    if global_state:
                        global_state.set_running_state("canceled")
                except Exception as e:
                    logger.error(f"Error setting cancellation flag: {e}")
        except Exception as e:
            logger.exception(f"Error in event stream for task {task_id}")
    
    return EventSourceResponse(event_generator())


@app.post("/api/agent/submit")
async def submit_task(request: SubmitTaskRequest):
    """Submit task asynchronously and return task_id"""
    task_id = str(uuid.uuid4())
    logger.info(f"Received /api/agent/submit request, assigning task_id: {task_id}")
    
    service.metrics.record_grpc_request("SubmitTask")
    
    task_created = False
    
    try:
        async with service.task_lock:
            active_tasks = await service.storage.count_active_tasks()
            if active_tasks >= service.max_concurrent_task_num:
                service.metrics.record_grpc_error("SubmitTask", "RESOURCE_EXHAUSTED")
                raise HTTPException(
                    status_code=503,
                    detail=f"Max concurrent tasks ({service.max_concurrent_task_num}) reached"
                )
            
            # Create agent
            agent = await service._make_agent(request.mode, request.stage_model_config, request.platform)
            
            # Restore conversation history if requested
            if request.continue_context and request.task_id:
                await service._restore_conversation_history(request.task_id, agent)
            
            # Prepare backend kwargs
            backend_kwargs = await service._make_backend_kwargs(request)
            
            # Store task data
            sandbox_info = service._sandbox_to_dict(backend_kwargs["sandbox"])
            task_data = TaskData(
                task_id=task_id,
                status="pending",
                query=request.instruction,
                max_steps=request.max_steps,
                sandbox_info=sandbox_info,
                request_data=request.model_dump()
            )
            await service.storage.create_task(task_data)
            
            service.metrics.record_task_created("pending")
            service.task_created_times[task_id] = time.time()
            
            # Store runtime data
            service.tasks[task_id] = {
                "agent": agent,
                "queue": None,
                "future": None,
                "query": request.instruction,
                "max_steps": request.max_steps,
                "destroy_sandbox": request.destroy_sandbox,
                "mode": request.mode,
            }
            task_created = True
            
            # Remove sandbox object from backend_kwargs before passing to _run_task
            # The sandbox info has been stored in task_data, and keeping it in backend_kwargs
            # can cause serialization issues in some backend implementations
            del backend_kwargs["sandbox"]
            
            # Start task
            task_future = asyncio.create_task(service._run_task(task_id, backend_kwargs))
            service.tasks[task_id]["future"] = task_future
        
        return {"task_id": task_id, "status": "pending"}
    
    except Exception as e:
        logger.exception(f"Error initializing task {task_id}: {e}")
        if task_created:
            async with service.task_lock:
                service.tasks.pop(task_id, None)
                service.task_created_times.pop(task_id, None)
        service.metrics.record_grpc_error("SubmitTask", "INTERNAL")
        raise HTTPException(status_code=500, detail=f"Failed to initialize task: {e}")


@app.get("/api/agent/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Query task status"""
    logger.info(f"Received status query for task_id: {task_id}")
    
    service.metrics.record_grpc_request("QueryTaskStatus")
    
    task_data = await service.storage.get_task(task_id)
    
    if not task_data:
        service.metrics.record_grpc_error("QueryTaskStatus", "NOT_FOUND")
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    status = task_data.status
    final_state = task_data.final_state
    
    # Map status
    if status == "finished":
        status_str = "completed" if final_state == "completed" else "finished"
        message = f"Task finished with status: {final_state}" if final_state else "Task finished"
    elif status == "error":
        status_str = "failed"
        message = "Task failed with an exception"
    elif status == "cancelled":
        status_str = "cancelled"
        message = "Task was cancelled"
    else:
        status_str = status
        message = "Task is running" if status == "running" else "Task is pending"
    
    # Build response
    response = TaskStatusResponse(
        task_id=task_id,
        status=status_str,
        message=message,
        sandbox=task_data.sandbox_info,
        execution_statistics=task_data.execution_statistics
    )
    
    return response


@app.post("/api/agent/cancel")
async def cancel_task(request: CancelRequest):
    """Cancel a running task"""
    task_id = request.task_id
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id is required")
    
    logger.info(f"Received cancel request for task_id: {task_id}")
    
    service.metrics.record_grpc_request("CancelTask")
    
    task_data = await service.storage.get_task(task_id)
    
    if not task_data:
        service.metrics.record_grpc_error("CancelTask", "NOT_FOUND")
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    status = task_data.status
    
    async with service.task_lock:
        task_info = service.tasks.get(task_id)
        task_future = task_info.get("future") if task_info else None
    
    if status in ["finished", "error"]:
        return {
            "task_id": task_id,
            "success": False,
            "message": f"Task {task_id} is already {status} and cannot be cancelled"
        }
    elif status == "cancelled":
        return {
            "task_id": task_id,
            "success": True,
            "message": f"Task {task_id} was already cancelled"
        }
    elif status in ["pending", "running"] and task_future:
        try:
            task_future.cancel()
            await service.storage.update_task(task_id, {"status": "cancelled"})
            
            global_state: GlobalState = Registry.get_from_context("GlobalStateStore", task_id)
            if global_state:
                global_state.set_running_state("cancelled")
            
            await stream_manager.add_message(task_id, "cancelled", "Task was cancelled by user request")
            
            logger.info(f"Task {task_id} successfully cancelled")
            return {
                "task_id": task_id,
                "success": True,
                "message": f"Task {task_id} has been successfully cancelled"
            }
        except Exception as e:
            logger.error(f"Failed to cancel task {task_id}: {e}")
            return {
                "task_id": task_id,
                "success": False,
                "message": f"Failed to cancel task {task_id}: {e}"
            }
    else:
        return {
            "task_id": task_id,
            "success": False,
            "message": f"Task {task_id} is in state '{status}' and cannot be cancelled"
        }


@app.get("/api/agent/tasks")
async def list_tasks(limit: int = 100, offset: int = 0):
    """List all tasks"""
    logger.info(f"Listing tasks with limit={limit}, offset={offset}")
    
    try:
        all_tasks = await service.storage.list_tasks()
        
        # Apply pagination
        paginated_tasks = all_tasks[offset:offset + limit]
        
        # Convert to response format
        tasks_list = []
        for task in paginated_tasks:
            tasks_list.append({
                "task_id": task.task_id,
                "status": task.status,
                "instruction": task.query,
                "created_at": task.created_at if hasattr(task, 'created_at') else None,
                "final_state": task.final_state,
            })
        
        return {
            "tasks": tasks_list,
            "total": len(all_tasks),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list tasks: {e}")


@app.post("/api/sandbox/create")
async def create_sandbox(request: CreateSandboxRequest):
    """Create a sandbox"""
    logger.info(f"Creating sandbox with shape: {request.shape}")
    
    try:
        auth = request.authentication or service.global_auth
        if not auth:
            raise HTTPException(
                status_code=400,
                detail="Authentication required (api_key and org_id)"
            )
        
        lybic_auth = LybicAuth(
            org_id=auth.org_id,
            api_key=auth.api_key,
            endpoint=auth.api_endpoint or "https://api.lybic.cn/"
        )
        
        sandbox = await service._create_sandbox(request.shape, lybic_auth)
        
        return {
            "sandbox_id": sandbox.id,
            "shape": sandbox.shapeName,
            "status": "created"
        }
    except Exception as e:
        logger.error(f"Error creating sandbox: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create sandbox: {e}")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Lybic GUI Agent RESTful API",
        "version": __version__,
        "docs": "/docs",
        "openapi": "/openapi.json"
    }


def main():
    """Entry point for the RESTful server"""
    import uvicorn
    
    # Validate backend compatibility
    has_display, pyautogui_available, _ = cli_app.check_display_environment()
    compatible_backends, incompatible_backends = cli_app.get_compatible_backends(has_display, pyautogui_available)
    cli_app.validate_backend_compatibility('lybic', compatible_backends, incompatible_backends)
    
    # Get configuration from environment
    host = os.environ.get("RESTFUL_HOST", "0.0.0.0")
    port = int(os.environ.get("RESTFUL_PORT", 8080))
    
    logger.info(f"Starting RESTful Agent server on {host}:{port}")
    
    uvicorn.run(
        "gui_agents.restful_app:app",
        host=host,
        port=port,
        log_level=level.lower(),
        access_log=True
    )


if __name__ == '__main__':
    main()
