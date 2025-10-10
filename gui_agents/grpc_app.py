# !/usr/bin/env python3
import os
from pathlib import Path
import logging
import datetime

from dotenv import load_dotenv

from gui_agents.agents.agent_s import load_config
from gui_agents.proto.pb.agent_pb2 import LLMConfig

env_path = Path(os.path.dirname(os.path.abspath(__file__))) / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    parent_env_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / '.env'
    if parent_env_path.exists():
        load_dotenv(dotenv_path=parent_env_path)
    else:
        print("No .env file found")

logger = logging.getLogger(__name__)
level = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=level,
    format='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger.info("Initializing Agent server")

import asyncio
import platform
from concurrent import futures
import grpc
import uuid

import gui_agents.cli_app as app
from gui_agents import Registry, GlobalState, AgentS2, HardwareInterface
# from gui_agents.rag import RagManager

has_display, pyautogui_available, env_error = app.check_display_environment()
compatible_backends, incompatible_backends = app.get_compatible_backends(has_display, pyautogui_available)
is_compatible, recommended_backend, warning = app.validate_backend_compatibility(
        'lybic', compatible_backends, incompatible_backends)
timestamp_dir = os.path.join(app.log_dir, app.datetime_str)
cache_dir = os.path.join(timestamp_dir, "cache", "screens")
state_dir = os.path.join(timestamp_dir, "state")

os.makedirs(cache_dir, exist_ok=True)
os.makedirs(state_dir, exist_ok=True)

from lybic import LybicClient, LybicAuth, Sandbox
from gui_agents.proto import agent_pb2, agent_pb2_grpc
from gui_agents.agents.stream_manager import stream_manager, StreamMessage

Registry.register(
    "GlobalStateStore",
    GlobalState(
        screenshot_dir=cache_dir,
        tu_path=os.path.join(state_dir, "tu.json"),
        search_query_path=os.path.join(state_dir, "search_query.json"),
        completed_subtasks_path=os.path.join(state_dir,
                                             "completed_subtasks.json"),
        failed_subtasks_path=os.path.join(state_dir,
                                          "failed_subtasks.json"),
        remaining_subtasks_path=os.path.join(state_dir,
                                             "remaining_subtasks.json"),
        termination_flag_path=os.path.join(state_dir,
                                           "termination_flag.json"),
        running_state_path=os.path.join(state_dir, "running_state.json"),
        display_info_path=os.path.join(timestamp_dir, "display.json"),
        agent_log_path=os.path.join(timestamp_dir, "agent_log.json")
    )
)



class AgentServicer(agent_pb2_grpc.AgentServicer):
    """
    Implements the Agent gRPC service.
    """

    def __init__(self, max_concurrent_task_num = 1):
        self.max_concurrent_task_num = max_concurrent_task_num
        self.tasks = {}
        self.global_common_config = agent_pb2.CommonConfig(id="global")
        self.task_lock = asyncio.Lock()
        self.lybic_client: LybicClient | None = None
        self.sandbox: Sandbox | None = None

    async def GetAgentTaskStream(self, request, context):
        """
        Streams messages for a given task ID.
        """
        task_id = request.taskId
        logger.info(f"Received GetAgentTaskStream request for taskId: {task_id}")

        async with self.task_lock:
            task_info = self.tasks.get(task_id)

        if not task_info:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Task with ID {task_id} not found.")
            return

        try:
            async for msg in stream_manager.get_message_stream(task_id):
                yield agent_pb2.GetAgentTaskStreamResponse(
                    taskStream=agent_pb2.TaskStream(
                        taskId=task_id,
                        stage=msg.stage,
                        message=msg.message
                    )
                )
        except asyncio.CancelledError:
            logger.info(f"GetAgentTaskStream for {task_id} cancelled by client.")
        except Exception as e:
            logger.error(f"Error in GetAgentTaskStream for task {task_id}: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"An error occurred during streaming: {e}")
        finally:
            # Clean up the task and stream when done
            await stream_manager.unregister_task(task_id)

    async def GetAgentInfo(self, request, context):
        """
        Returns information about the agent.
        """
        from importlib.metadata import version, PackageNotFoundError
        try:
            v = version("gui_agents")
        except PackageNotFoundError:
            v = "unknown"
        return agent_pb2.AgentInfo(
            version=v,
            maxConcurrentTasks=self.max_concurrent_task_num,
            log_level=level,
            domain=platform.node(),
        )

    async def _run_task(self, task_id: str, backend_kwargs):
        """Helper to run a task's main loop and handle state."""
        async with self.task_lock:
            self.tasks[task_id]["status"] = "running"
            agent = self.tasks[task_id]["agent"]
            steps = self.tasks[task_id]["max_steps"]
            query = self.tasks[task_id]["query"]

        try:
            # Send message through stream manager
            await stream_manager.add_message(task_id, "starting", "Task starting")

            hwi = HardwareInterface(backend='lybic', **backend_kwargs)

            agent.reset()

            # Run the blocking function in a separate thread to avoid blocking the event loop
            await asyncio.to_thread(app.run_agent_normal,(agent,query, hwi,steps,False))

            final_state = Registry.get("GlobalStateStore").get_running_state()
            async with self.task_lock:
                self.tasks[task_id]["final_state"] = final_state
                self.tasks[task_id]["status"] = "finished"

            if final_state and final_state.status == "completed":
                await stream_manager.add_message(task_id, "finished", "Task completed successfully")
            else:
                status = final_state.status if final_state else 'unknown'
                await stream_manager.add_message(task_id, "finished", f"Task finished with status: {status}")

        except Exception as e:
            logger.error(f"Error during task execution for {task_id}: {e}", exc_info=True)
            async with self.task_lock:
                self.tasks[task_id]["status"] = "error"
            await stream_manager.add_message(task_id, "error", f"An error occurred: {e}")
        finally:
            logger.info(f"Task {task_id} processing finished.")

    async def _make_backend_kwargs(self, request):
        platform_map = {
            agent_pb2.SandboxOS.WINDOWS: "Windows",
            agent_pb2.SandboxOS.LINUX: "Ubuntu",
        }
        backend = "lybic"
        if request.HasField("runningConfig") and request.runningConfig.backend:
            backend = request.runningConfig.backend
        backend_kwargs: dict
        platform_str = platform.system()
        sid = ''
        if backend == 'lybic':
            if request.HasField("sandbox"):
                if request.sandbox.HasField('os'):
                    # todo: add shape args
                    platform_str = platform_map.get(request.sandbox.os, platform.system())
                else:
                    sid, platform_str = await self._create_sandbox()
            else:
                sid, platform_str = await self._create_sandbox()

        else:
            platform_str = platform_map.get(request.sandbox.os, platform.system())
        backend_kwargs = {"platform": platform_str, "precreate_sid": sid}
        return backend_kwargs

    async def _make_agent(self,request):
        max_steps = 50
        if request.HasField("runningConfig") and request.runningConfig.steps:
            max_steps = request.runningConfig.steps

        # Dynamically build tools_dict based on global config
        _ , tools_dict = load_config()

        if self.global_common_config.HasField("stageModelConfig"):
            stage_config = self.global_common_config.stageModelConfig
            logger.info("Applying global model configurations to this task.")

            def apply_config(tool_name, llm_config:LLMConfig):
                if tool_name in tools_dict and llm_config.modelName:
                    tool_config = tools_dict[tool_name]
                    tool_config['provider'] = llm_config.provider
                    tool_config['model_name'] = llm_config.modelName
                    tool_config['model'] = llm_config.modelName

                    # IMPORTANT Override api key and endpoint
                    if llm_config.apiKey:
                        tool_config['api_key'] = llm_config.apiKey
                    if llm_config.apiEndpoint:
                        tool_config['base_url'] = llm_config.apiEndpoint

                    logger.info(f"Override tool '{tool_name}' with model '{llm_config.modelName}'.")

            if stage_config.HasField("embeddingModel"):
                apply_config('embedding', stage_config.embeddingModel)

            if stage_config.HasField("groundingModel"):
                apply_config('grounding', stage_config.groundingModel)

            if stage_config.HasField("actionGeneratorModel"):
                common_llm_config = stage_config.actionGeneratorModel
                # Apply common config to all other LLM-based tools
                for tool_name, config in tools_dict.items():
                    if config.get("is_llm_tool") and tool_name not in ['embedding', 'grounding']:
                        apply_config(tool_name, common_llm_config)

        return AgentS2(
            platform="windows",  # 沙盒中的系统
            screen_size=[1280, 720],
            enable_takeover=False,
            enable_search=False,
            tools_config={"tools": tools_dict},
        )


    async def RunAgentInstruction(self, request, context):
        task_id = str(uuid.uuid4())
        logger.info(f"Received RunAgentInstruction request, assigning taskId: {task_id}")

        async with self.task_lock:
            if len(self.tasks) >= self.max_concurrent_task_num:
                context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
                context.set_details(f"Max concurrent tasks ({self.max_concurrent_task_num}) reached.")
                return


        queue = asyncio.Queue()
        task_future = None

        async with self.task_lock:
            if len(self.tasks) >= self.max_concurrent_task_num:
                context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
                context.set_details(f"Max concurrent tasks ({self.max_concurrent_task_num}) reached.")
                return

            agent = await self._make_agent(request=request)
            backend_kwargs = await self._make_backend_kwargs(request)
            max_steps = 50
            if request.HasField("runningConfig") and request.runningConfig.steps:
                max_steps = request.runningConfig.steps

            task_future = asyncio.create_task(self._run_task(task_id, backend_kwargs))
            self.tasks[task_id] = {
                "request": request,
                "status": "pending",
                "final_state": None,
                "queue": queue,
                "future": task_future,
                "query": request.instruction,
                "agent": agent,
                "max_steps": max_steps,
            }

        try:
            for msg in stream_manager.get_message_stream(task_id):
                yield agent_pb2.TaskStream(
                    taskId=task_id,
                    stage=msg.stage,
                    message=msg.message
                )
        except asyncio.CancelledError:
            logger.info(f"RunAgentInstruction stream for {task_id} cancelled by client.")
            if task_future:
                task_future.cancel()
        except Exception as e:
            logger.error(f"Error in RunAgentInstruction stream for task {task_id}: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"An error occurred during streaming: {e}")

    async def RunAgentInstructionAsync(self, request, context):
        """
        Starts a task asynchronously and returns immediately with a task ID.
        The task can be monitored via GetAgentTaskStream.
        """
        task_id = str(uuid.uuid4())
        logger.info(f"Received RunAgentInstructionAsync request, assigning taskId: {task_id}")

        async with self.task_lock:
            if len(self.tasks) >= self.max_concurrent_task_num:
                context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
                context.set_details(f"Max concurrent tasks ({self.max_concurrent_task_num}) reached.")
                return

            agent = await self._make_agent(request=request)
            backend_kwargs = await self._make_backend_kwargs(request)
            max_steps = 50
            if request.HasField("runningConfig") and request.runningConfig.steps:
                max_steps = request.runningConfig.steps

            # Create queue for this task
            queue = asyncio.Queue()

            # Register task with stream manager
            await stream_manager.register_task(task_id)

            # Start the task in background
            task_future = asyncio.create_task(self._run_task(task_id, backend_kwargs))

            self.tasks[task_id] = {
                "request": request,
                "status": "pending",
                "final_state": None,
                "queue": queue,
                "future": task_future,
                "query": request.instruction,
                "agent": agent,
                "max_steps": max_steps,
            }

        return agent_pb2.RunAgentInstructionAsyncResponse(taskId=task_id)

    async def QueryTaskStatus(self, request, context):
        task_id = request.taskId
        async with self.task_lock:
            task_info = self.tasks.get(task_id)

        if not task_info:
            return agent_pb2.QueryTaskStatusResponse(
                taskId=task_id,
                status=agent_pb2.TaskStatus.NOT_FOUND,
                message=f"Task with ID {task_id} not found."
            )

        status = task_info["status"]
        controller = task_info.get("controller")
        final_state = task_info.get("final_state")

        status_map = {
            "pending": agent_pb2.TaskStatus.PENDING,
            "running": agent_pb2.TaskStatus.RUNNING,
            "fulfilled": agent_pb2.TaskStatus.SUCCESS,
            "rejected": agent_pb2.TaskStatus.FAILURE,
        }

        if status == "finished":
            task_status = status_map.get(final_state.status,
                                         agent_pb2.TaskStatus.SUCCESS) if final_state else agent_pb2.TaskStatus.SUCCESS
            message = f"Task finished with status: {final_state.status}" if final_state else "Task finished."
            result = final_state.result if final_state and hasattr(final_state, 'result') else ""
        elif status == "error":
            task_status = agent_pb2.TaskStatus.FAILURE
            message = "Task failed with an exception."
            result = ""
        else:  # pending or running
            task_status = status_map.get(status, agent_pb2.TaskStatus.TASKSTATUSUNDEFINED)
            message = "Task is running."
            if controller and controller.global_state.thoughts:
                message = controller.global_state.thoughts[-1]
            result = ""

        return agent_pb2.QueryTaskStatusResponse(
            taskId=task_id,
            status=task_status,
            message=message,
            result=result,
            sandbox=task_info["request"].sandbox
        )

    async def GetGlobalCommonConfig(self, request, context):
        return self.global_common_config

    async def GetCommonConfig(self, request, context):
        async with self.task_lock:
            task_info = self.tasks.get(request.id)
        if task_info and task_info.get("request"):
            return task_info["request"].runningConfig
        context.set_code(grpc.StatusCode.NOT_FOUND)
        context.set_details(f"Config for task {request.id} not found.")
        return agent_pb2.CommonConfig()

    async def SetGlobalCommonConfig(self, request, context):
        logger.info("Setting new global common config.")
        self.global_common_config = request.commonConfig

        if self.global_common_config.HasField("authorizationInfo"):  # lybic
            if self.lybic_client:
                await self.lybic_client.close()
            self.lybic_client = LybicClient(LybicAuth(
                org_id=self.global_common_config.authorizationInfo.orgId,
                api_key=self.global_common_config.authorizationInfo.apiKey,
                endpoint=self.global_common_config.authorizationInfo.endpoint or "https://api.lybic.cn/"
            ))

        return agent_pb2.SetCommonConfigResponse(success=True, id=self.global_common_config.id)

    async def SetGlobalCommonLLMConfig(self, request, context):
        if not self.global_common_config.HasField("stageModelConfig"):
            self.global_common_config.stageModelConfig.SetInParent()
        self.global_common_config.stageModelConfig.actionGeneratorModel.CopyFrom(request.llmConfig)
        logger.info(f"Global common LLM config updated to: {request.llmConfig.modelName}")
        return request.llmConfig

    async def SetGlobalGroundingLLMConfig(self, request, context):
        if not self.global_common_config.HasField("stageModelConfig"):
            self.global_common_config.stageModelConfig.SetInParent()
        self.global_common_config.stageModelConfig.groundingModel.CopyFrom(request.llmConfig)
        logger.info(f"Global grounding LLM config updated to: {request.llmConfig.modelName}")
        return request.llmConfig

    async def SetGlobalEmbeddingLLMConfig(self, request, context):
        if not self.global_common_config.HasField("stageModelConfig"):
            self.global_common_config.stageModelConfig.SetInParent()
        self.global_common_config.stageModelConfig.embeddingModel.CopyFrom(request.llmConfig)
        logger.info(f"Global embedding LLM config updated to: {request.llmConfig.modelName}")
        return request.llmConfig

    async def _create_sandbox(self):
        # todo: add shape args
        if not self.lybic_client:
            raise Exception("Lybic client not initialized. Please call SetGlobalCommonConfig before")
        if not self.sandbox:
            self.sandbox = Sandbox(self.lybic_client)
        result = await self.sandbox.create()
        return result.sandbox.id, result.sandbox.shape.os



async def serve():
    port = os.environ.get("GRPC_PORT", 50051)
    max_workers = int(os.environ.get("GRPC_MAX_WORKER_THREADS", 100))
    # task_num = int(os.environ.get("TASK_MAX_TASKS", 5))
    servicer = AgentServicer(max_concurrent_task_num=1)
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers))
    agent_pb2_grpc.add_AgentServicer_to_server(servicer, server)
    server.add_insecure_port(f'[::]:{port}')
    logger.info(f"Agent gRPC server started on port {port}")

    await server.start()
    await server.wait_for_termination()

def main():
    """Entry point for the gRPC server."""
    asyncio.run(serve())

if __name__ == '__main__':
    main()
