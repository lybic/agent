
from concurrent import futures
import grpc
import logging

# This assumes you have generated pb2 and pb2_grpc files from agent.proto
# You might need to adjust the import paths based on your project structure.
# For example: from .. import agent_pb2
from ..proto import agent_pb2, agent_pb2_grpc

from .stream_manager import stream_manager, StreamMessage

logger = logging.getLogger(__name__)

class AgentServicer(agent_pb2_grpc.AgentServicer):
    """
    Implements the Agent gRPC service.
    """

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

    # ... other RPC implementations would go here ...

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    agent_pb2_grpc.add_AgentServicer_to_server(AgentServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    logger.info("Agent gRPC server started on port 50051")
    server.wait_for_termination()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    serve()
