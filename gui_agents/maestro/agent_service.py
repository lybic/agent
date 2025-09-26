#!/usr/bin/env python3
import os
import logging
import datetime
logger = logging.getLogger(__name__)
level = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=level,
    format='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger.info("Initializing Agent server")

import platform
from concurrent import futures
import grpc
import threading
import uuid

from gui_agents.proto import agent_pb2, agent_pb2_grpc
from .stream_manager import stream_manager, StreamMessage
from gui_agents.maestro.controller.main_controller import MainController
from gui_agents.maestro.controller.config_manager import ConfigManager

class AgentServicer(agent_pb2_grpc.AgentServicer):
    """
    Implements the Agent gRPC service.
    """
    def __init__(self,max_concurrent_task_num = 5):
        self.max_concurrent_task_num = max_concurrent_task_num
        self.tasks = {}
        self.task_threads = {}
        self.config_manager = ConfigManager()
        self.config_manager.load_tools_configuration()
        self.config_manager.load_flow_configuration()
        self.global_common_config = agent_pb2.CommonConfig(id="global")
        self.task_lock = threading.Lock()

    def GetAgentTaskStream(self, request, context):
        """
        Streams messages for a given task ID.
        This is a blocking, long-lived stream.
        """
        task_id = request.taskId
        logger.info(f"Client subscribed to task stream for taskId: {task_id}")
        
        try:
            message_generator = stream_manager.get_message_stream(task_id)
            for msg in message_generator:
                if msg is None: # Sentinel for stream end
                    logger.info(f"End of stream for task {task_id}")
                    break
                
                response = agent_pb2.GetAgentTaskStreamResponse(
                    taskStream=agent_pb2.TaskStream(
                        taskId=task_id,
                        stage=msg.stage,
                        message=msg.message
                    )
                )
                yield response
        except Exception as e:
            logger.error(f"Error in GetAgentTaskStream for task {task_id}: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"An error occurred: {e}")

    def GetAgentInfo(self, request, context):
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

    def _run_task(self, task_id: str, controller: MainController):
        """Helper to run a task's main loop and handle state."""
        with self.task_lock:
            self.tasks[task_id]["status"] = "running"

        try:
            stream_manager.add_message(task_id, StreamMessage(stage="starting", message="Task starting"))
            controller.execute_main_loop()
            
            final_state = controller.global_state.get_task()
            with self.task_lock:
                self.tasks[task_id]["final_state"] = final_state
                self.tasks[task_id]["status"] = "finished"
            
            if final_state and final_state.status == "fulfilled":
                stream_manager.add_message(task_id, StreamMessage(stage="finished", message="Task completed successfully"))
            else:
                status = final_state.status if final_state else 'unknown'
                stream_manager.add_message(task_id, StreamMessage(stage="finished", message=f"Task finished with status: {status}"))

        except Exception as e:
            logger.error(f"Error during task execution for {task_id}: {e}", exc_info=True)
            with self.task_lock:
                self.tasks[task_id]["status"] = "error"
            stream_manager.add_message(task_id, StreamMessage(stage="error", message=f"An error occurred: {e}"))
        finally:
            stream_manager.close_stream(task_id)
            with self.task_lock:
                if task_id in self.task_threads:
                    del self.task_threads[task_id]
            logger.info(f"Task {task_id} thread finished.")

    def RunAgentInstruction(self, request, context):
        task_id = str(uuid.uuid4())
        logger.info(f"Received RunAgentInstruction request, assigning taskId: {task_id}")

        with self.task_lock:
            if len(self.tasks) >= self.max_concurrent_task_num:
                context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
                context.set_details(f"Max concurrent tasks ({self.max_concurrent_task_num}) reached.")
                return

        controller, _ = self._create_controller_from_request(request, task_id)
        if not controller:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Failed to create task controller.")
            return

        thread = threading.Thread(target=self._run_task, args=(task_id, controller))
        self.task_threads[task_id] = thread
        thread.start()

        try:
            message_generator = stream_manager.get_message_stream(task_id)
            for msg in message_generator:
                if msg is None:
                    break
                yield agent_pb2.TaskStream(
                    taskId=task_id,
                    stage=msg.stage,
                    message=msg.message
                )
        except Exception as e:
            logger.error(f"Error in RunAgentInstruction stream for task {task_id}: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"An error occurred during streaming: {e}")

    def RunAgentInstructionAsync(self, request, context):
        with self.task_lock:
            if len(self.tasks) >= self.max_concurrent_task_num:
                context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
                context.set_details(f"Max concurrent tasks ({self.max_concurrent_task_num}) reached.")
                return agent_pb2.RunAgentInstructionAsyncResponse()

        task_id = str(uuid.uuid4())
        logger.info(f"Received RunAgentInstructionAsync request, assigning taskId: {task_id}")

        controller, _ = self._create_controller_from_request(request, task_id)
        if not controller:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Failed to create task controller.")
            return agent_pb2.RunAgentInstructionAsyncResponse()

        thread = threading.Thread(target=self._run_task, args=(task_id, controller))
        self.task_threads[task_id] = thread
        thread.start()

        return agent_pb2.RunAgentInstructionAsyncResponse(taskId=task_id)

    def QueryTaskStatus(self, request, context):
        task_id = request.taskId
        with self.task_lock:
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
            task_status = status_map.get(final_state.status, agent_pb2.TaskStatus.SUCCESS) if final_state else agent_pb2.TaskStatus.SUCCESS
            message = f"Task finished with status: {final_state.status}" if final_state else "Task finished."
            result = final_state.result if final_state and hasattr(final_state, 'result') else ""
        elif status == "error":
            task_status = agent_pb2.TaskStatus.FAILURE
            message = "Task failed with an exception."
            result = ""
        else: # pending or running
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

    def GetGlobalCommonConfig(self, request, context):
        return self.global_common_config

    def GetCommonConfig(self, request, context):
        with self.task_lock:
            task_info = self.tasks.get(request.id)
        if task_info and task_info.get("request"):
            return task_info["request"].runningConfig
        context.set_code(grpc.StatusCode.NOT_FOUND)
        context.set_details(f"Config for task {request.id} not found.")
        return agent_pb2.CommonConfig()

    def SetGlobalCommonConfig(self, request, context):
        logger.info("Setting new global common config.")
        self.global_common_config = request.commonConfig
        return agent_pb2.SetCommonConfigResponse(success=True, id=self.global_common_config.id)

    def SetGlobalCommonLLMConfig(self, request, context):
        if not self.global_common_config.HasField("stageModelConfig"):
            self.global_common_config.stageModelConfig.SetInParent()
        self.global_common_config.stageModelConfig.actionGeneratorModel.CopyFrom(request.llmConfig)
        logger.info(f"Global common LLM config updated to: {request.llmConfig.modelName}")
        return request.llmConfig

    def SetGlobalGroundingLLMConfig(self, request, context):
        if not self.global_common_config.HasField("stageModelConfig"):
            self.global_common_config.stageModelConfig.SetInParent()
        self.global_common_config.stageModelConfig.groundingModel.CopyFrom(request.llmConfig)
        logger.info(f"Global grounding LLM config updated to: {request.llmConfig.modelName}")
        return request.llmConfig

    def SetGlobalEmbeddingLLMConfig(self, request, context):
        if not self.global_common_config.HasField("stageModelConfig"):
            self.global_common_config.stageModelConfig.SetInParent()
        self.global_common_config.stageModelConfig.embeddingModel.CopyFrom(request.llmConfig)
        logger.info(f"Global embedding LLM config updated to: {request.llmConfig.modelName}")
        return request.llmConfig

    def _create_controller_from_request(self, request, task_id):
        datetime_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir = os.path.join("runtime", f"grpc_task_{task_id}_{datetime_str}")
        os.makedirs(log_dir, exist_ok=True)

        platform_map = {
            agent_pb2.SandboxOS.WINDOWS: "Windows",
            agent_pb2.SandboxOS.LINUX: "Ubuntu",
        }
        platform_str = platform_map.get(request.sandbox.os, platform.system())

        backend = "pyautogui"
        if request.HasField("runningConfig") and request.runningConfig.backend:
            backend = request.runningConfig.backend
        
        max_steps = 50
        if request.HasField("runningConfig") and request.runningConfig.steps:
            max_steps = request.runningConfig.steps

        try:
            controller = MainController(
                platform=platform_str,
                backend=backend,
                user_query=request.instruction,
                max_steps=max_steps,
                env=None,
                log_dir=log_dir,
                datetime_str=datetime_str
            )
            with self.task_lock:
                self.tasks[task_id] = {
                    "controller": controller,
                    "request": request,
                    "status": "pending",
                    "final_state": None
                }
            return controller, log_dir
        except Exception as e:
            logger.error(f"Failed to create MainController for task {task_id}: {e}", exc_info=True)
            return None, None

def serve():
    port = os.environ.get("GRPC_PORT", 50051)
    max_workers = int(os.environ.get("GRPC_MAX_WORKER_THREADS", 100))
    task_num = int(os.environ.get("TASK_MAX_TASKS", 5))

    server = grpc.server(futures.ThreadPoolExecutor(max_workers))
    agent_pb2_grpc.add_AgentServicer_to_server(AgentServicer(task_num), server)
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logger.info(f"Agent gRPC server started on port {port}")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
