"""Core Agent Service implementation"""

import logging
import threading
import time
import uuid
import datetime
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Optional, Any, Union
from pathlib import Path

from .api_models import (
    TaskRequest, TaskResult, TaskStatus, ExecutionStats, 
    AsyncTaskHandle, Backend, AgentMode
)
from .config import ServiceConfig
from .exceptions import (
    AgentServiceError, TaskExecutionError, TaskTimeoutError, 
    ConfigurationError, BackendError
)

# Import existing agent classes
from ..agents.agent_s import AgentS2, AgentSFast
from ..agents.hardware_interface import HardwareInterface
from ..store.registry import Registry
from ..agents.global_state import GlobalState


class AgentService:
    """
    Core service class that provides a unified interface for GUI automation tasks.
    
    This service wraps the existing Agent-S functionality and provides:
    - Synchronous and asynchronous task execution
    - Configuration management with multi-level API key support
    - Task lifecycle management
    - Execution statistics and monitoring
    """
    
    def __init__(
        self, 
        config: Optional[ServiceConfig] = None,
        **kwargs
    ):
        """
        Initialize the Agent Service
        
        Args:
            config: Service configuration. If None, will create from environment
            **kwargs: Override configuration parameters
        """
        # Initialize configuration
        if config is None:
            config = ServiceConfig.from_env()
        
        # Apply kwargs overrides
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        # Validate configuration
        config.validate()
        
        self.config = config
        self.logger = self._setup_logging()
        
        # Task management
        self._tasks: Dict[str, TaskResult] = {}
        self._task_futures: Dict[str, Future] = {}
        self._task_lock = threading.RLock()
        
        # Thread pool for async execution
        self._executor = ThreadPoolExecutor(
            max_workers=config.max_concurrent_tasks,
            thread_name_prefix="AgentService"
        )
        
        # Agent instances cache
        self._agents: Dict[str, Union[AgentS2, AgentSFast]] = {}
        self._hwi_instances: Dict[str, HardwareInterface] = {}
        
        self.logger.info(f"AgentService initialized with config: {config.to_dict()}")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the service"""
        logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        logger.setLevel(getattr(logging, self.config.log_level.upper()))
        
        # Create log directory if it doesn't exist
        log_dir = Path(self.config.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        return logger
    
    def _get_or_create_agent(self, mode: str, **kwargs) -> Union[AgentS2, AgentSFast]:
        """Get or create agent instance based on mode"""
        cache_key = f"{mode}_{hash(str(sorted(kwargs.items())))}"
        
        if cache_key not in self._agents:
            agent_kwargs = {
                'platform': kwargs.get('platform', self.config.default_platform),
                'enable_takeover': kwargs.get('enable_takeover', self.config.enable_takeover),
                'enable_search': kwargs.get('enable_search', self.config.enable_search),
            }
            
            if mode == AgentMode.FAST.value:
                self._agents[cache_key] = AgentSFast(**agent_kwargs)
            else:
                self._agents[cache_key] = AgentS2(**agent_kwargs)
            
            self.logger.debug(f"Created new agent: {mode} with kwargs: {agent_kwargs}")
        
        return self._agents[cache_key]
    
    def _get_or_create_hwi(self, backend: str, **kwargs) -> HardwareInterface:
        """Get or create hardware interface instance"""
        cache_key = f"{backend}_{hash(str(sorted(kwargs.items())))}"
        
        if cache_key not in self._hwi_instances:
            # Get backend-specific config
            backend_config = self.config.get_backend_config(backend)
            backend_config.update(kwargs)
            
            # Add platform info
            backend_config.setdefault('platform', self.config.default_platform)
            
            self._hwi_instances[cache_key] = HardwareInterface(
                backend=backend, 
                **backend_config
            )
            
            self.logger.debug(f"Created new HWI: {backend} with config: {backend_config}")
        
        return self._hwi_instances[cache_key]
    
    def _setup_global_state(self, task_id: str) -> str:
        """Setup global state for task execution"""
        # Create timestamp-based directory structure like cli_app.py
        datetime_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        timestamp_dir = Path(self.config.log_dir) / datetime_str
        cache_dir = timestamp_dir / "cache" / "screens"
        state_dir = timestamp_dir / "state"
        
        cache_dir.mkdir(parents=True, exist_ok=True)
        state_dir.mkdir(parents=True, exist_ok=True)
        
        # Register global state for this task
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
        
        # Use task-specific registry key to avoid conflicts
        registry_key = "GlobalStateStore"
        Registry.register(registry_key, global_state)
        
        return str(timestamp_dir)
    
    def _execute_task_internal(self, request: TaskRequest, task_result: TaskResult) -> TaskResult:
        """Internal task execution method"""
        try:
            task_result.mark_started()
            self.logger.info(f"Starting task {task_result.task_id}: {request.instruction}")
            
            # Setup global state
            task_dir = self._setup_global_state(task_result.task_id)
            
            # Create agent and hardware interface
            agent = self._get_or_create_agent(
                request.mode,
                platform=self.config.default_platform,
                enable_takeover=request.enable_takeover,
                enable_search=request.enable_search
            )
            
            hwi = self._get_or_create_hwi(
                request.backend,
                **(request.config or {})
            )
            
            # Reset agent state
            agent.reset()
            
            # Execute task using existing run_agent logic
            start_time = time.time()
            
            if request.mode == AgentMode.FAST.value:
                self._run_agent_fast_internal(
                    agent, request.instruction, hwi, 
                    request.max_steps, request.enable_takeover,
                    task_result.task_id
                )
            else:
                self._run_agent_normal_internal(
                    agent, request.instruction, hwi, 
                    request.max_steps, request.enable_takeover,
                    task_result.task_id
                )
            
            end_time = time.time()
            
            # Create execution stats
            stats = ExecutionStats(
                total_duration=end_time - start_time,
                steps_count=0,  # Will be populated from global state if available
                tokens_used={"input": 0, "output": 0, "total": 0}
            )
            
            # Try to get more detailed stats from display.json
            try:
                display_json_path = Path(task_dir) / "display.json"
                if display_json_path.exists():
                    # Import here to avoid circular imports
                    # Use dynamic import to handle packaging issues
                    try:
                        from gui_agents.utils.analyze_display import analyze_display_json
                    except ImportError:
                        try:
                            from ..utils.analyze_display import analyze_display_json
                        except ImportError:
                            # Fallback for packaged version
                            import importlib
                            utils_module = importlib.import_module('gui_agents.utils')
                            analyze_display_json = getattr(utils_module.analyze_display, 'analyze_display_json')
                    analysis_result = analyze_display_json(str(display_json_path))
                    if analysis_result:
                        stats.steps_count = analysis_result.get('steps', 0)
                        stats.tokens_used = {
                            "input": analysis_result.get('input_tokens', 0),
                            "output": analysis_result.get('output_tokens', 0),
                            "total": analysis_result.get('total_tokens', 0)
                        }
                        stats.cost = analysis_result.get('cost', 0.0)
            except Exception as e:
                self.logger.warning(f"Failed to analyze execution stats: {e}")
            
            # Mark as completed
            task_result.mark_completed(
                result={"message": "Task completed successfully"},
                stats=stats
            )
            
            self.logger.info(
                f"Task {task_result.task_id} completed in {stats.total_duration:.2f}s "
                f"with {stats.steps_count} steps"
            )
            
        except Exception as e:
            error_msg = f"Task execution failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            task_result.mark_failed(error_msg)
            
        finally:
            # Cleanup global state registry
            registry_key = f"GlobalStateStore"
            try:
                # Registry doesn't have unregister method, we'll use clear or manual removal
                if hasattr(Registry, '_services') and registry_key in Registry._services:
                    del Registry._services[registry_key]
            except:
                pass
        
        return task_result
    
    def _run_agent_normal_internal(self, agent, instruction: str, hwi, max_steps: int, 
                                 enable_takeover: bool, task_id: str):
        """Run agent in normal mode (adapted from cli_app.py)"""
        # This is a simplified version - you may want to adapt the full logic from cli_app.py
        global_state: GlobalState = Registry.get(f"GlobalStateStore")  # type: ignore
        global_state.set_Tu(instruction)
        global_state.set_running_state("running")
        
        # Use dynamic import to handle packaging issues
        try:
            from gui_agents.agents.Action import Screenshot
        except ImportError:
            try:
                from ..agents.Action import Screenshot
            except ImportError:
                # Fallback for packaged version
                import importlib
                agents_module = importlib.import_module('gui_agents.agents')
                Screenshot = getattr(agents_module.Action, 'Screenshot')
        from PIL import Image
        
        for step in range(max_steps):
            # Take screenshot
            screenshot: Image.Image = hwi.dispatch(Screenshot())
            global_state.set_screenshot(screenshot)
            obs = global_state.get_obs_for_manager()
            
            # Get agent prediction
            info, code = agent.predict(instruction=instruction, observation=obs)
            
            # Check for completion
            if "done" in code[0]["type"].lower() or "fail" in code[0]["type"].lower():
                agent.update_narrative_memory(f"Task: {instruction}")
                break
            
            if "next" in code[0]["type"].lower():
                continue
                
            if "wait" in code[0]["type"].lower():
                time.sleep(5)
                continue
            
            # Execute action
            hwi.dispatchDict(code[0])
            time.sleep(1.0)
    
    def _run_agent_fast_internal(self, agent, instruction: str, hwi, max_steps: int, 
                               enable_takeover: bool, task_id: str):
        """Run agent in fast mode (adapted from cli_app.py)"""
        global_state: GlobalState = Registry.get(f"GlobalStateStore")  # type: ignore
        global_state.set_Tu(instruction)
        global_state.set_running_state("running")
        
        # Use dynamic import to handle packaging issues
        try:
            from gui_agents.agents.Action import Screenshot
        except ImportError:
            try:
                from ..agents.Action import Screenshot
            except ImportError:
                # Fallback for packaged version
                import importlib
                agents_module = importlib.import_module('gui_agents.agents')
                Screenshot = getattr(agents_module.Action, 'Screenshot')
        from PIL import Image
        
        for step in range(max_steps):
            # Take screenshot
            screenshot: Image.Image = hwi.dispatch(Screenshot())
            global_state.set_screenshot(screenshot)
            obs = global_state.get_obs_for_manager()
            
            # Get agent prediction
            info, code = agent.predict(instruction=instruction, observation=obs)
            
            # Check for completion
            if "done" in code[0]["type"].lower() or "fail" in code[0]["type"].lower():
                break
            
            if "wait" in code[0]["type"].lower():
                wait_duration = code[0].get("duration", 5000) / 1000
                time.sleep(wait_duration)
                continue
            
            # Execute action
            hwi.dispatchDict(code[0])
            time.sleep(0.5)
    
    def execute_task(
        self, 
        instruction: str,
        backend: str | None = None,
        mode: str | None = None,
        max_steps: int | None = None,
        enable_takeover: bool | None = None,
        enable_search: bool | None = None,
        timeout: int | None = None,
        **kwargs
    ) -> TaskResult:
        """
        Execute a task synchronously
        
        Args:
            instruction: Task instruction in natural language
            backend: Backend to use (overrides config default)
            mode: Agent mode ('normal' or 'fast', overrides config default)
            max_steps: Maximum steps (overrides config default)
            enable_takeover: Enable user takeover (overrides config default)
            enable_search: Enable web search (overrides config default)
            timeout: Task timeout in seconds (overrides config default)
            **kwargs: Additional configuration parameters
            
        Returns:
            TaskResult with execution details
        """
        # Create task request with defaults from config
        request = TaskRequest(
            instruction=instruction,
            backend=backend or self.config.default_backend,
            mode=mode or self.config.default_mode,
            max_steps=max_steps or self.config.default_max_steps,
            enable_takeover=enable_takeover if enable_takeover is not None else self.config.enable_takeover,
            enable_search=enable_search if enable_search is not None else self.config.enable_search,
            timeout=timeout or self.config.task_timeout,
            config=kwargs
        )
        
        # Create task result
        task_result = TaskResult.create_pending(instruction)
        
        # Store task
        with self._task_lock:
            self._tasks[task_result.task_id] = task_result
        
        # Execute task
        try:
            return self._execute_task_internal(request, task_result)
        finally:
            # Cleanup task future if exists
            with self._task_lock:
                self._task_futures.pop(task_result.task_id, None)
    
    def execute_task_async(
        self,
        instruction: str,
        **kwargs
    ) -> AsyncTaskHandle:
        """
        Execute a task asynchronously
        
        Args:
            instruction: Task instruction
            **kwargs: Same as execute_task
            
        Returns:
            AsyncTaskHandle for monitoring the task
        """
        # Create task request
        request = TaskRequest(
            instruction=instruction,
            backend=kwargs.get('backend', self.config.default_backend),
            mode=kwargs.get('mode', self.config.default_mode),
            max_steps=kwargs.get('max_steps', self.config.default_max_steps),
            enable_takeover=kwargs.get('enable_takeover', self.config.enable_takeover),
            enable_search=kwargs.get('enable_search', self.config.enable_search),
            timeout=kwargs.get('timeout', self.config.task_timeout),
            config={k: v for k, v in kwargs.items() if k not in [
                'backend', 'mode', 'max_steps', 'enable_takeover', 
                'enable_search', 'timeout'
            ]}
        )
        
        # Create task result
        task_result = TaskResult.create_pending(instruction)
        
        # Store task and submit to executor
        with self._task_lock:
            self._tasks[task_result.task_id] = task_result
            future = self._executor.submit(self._execute_task_internal, request, task_result)
            self._task_futures[task_result.task_id] = future
        
        return AsyncTaskHandle(task_id=task_result.task_id, status=TaskStatus.PENDING)
    
    def get_task_status(self, task_id: str) -> Optional[TaskResult]:
        """Get task status and result"""
        with self._task_lock:
            return self._tasks.get(task_id)
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task"""
        with self._task_lock:
            # Cancel future if exists
            future = self._task_futures.get(task_id)
            if future:
                cancelled = future.cancel()
                if cancelled:
                    # Mark task as cancelled
                    task = self._tasks.get(task_id)
                    if task:
                        task.mark_cancelled()
                    return True
            return False
    
    def list_tasks(self, status: Optional[TaskStatus] = None) -> Dict[str, TaskResult]:
        """List all tasks, optionally filtered by status"""
        with self._task_lock:
            if status is None:
                return self._tasks.copy()
            else:
                return {
                    task_id: task for task_id, task in self._tasks.items()
                    if task.status == status
                }
    
    def cleanup_finished_tasks(self, max_age_seconds: int = 3600):
        """Clean up finished tasks older than max_age_seconds"""
        current_time = time.time()
        to_remove = []
        
        with self._task_lock:
            for task_id, task in self._tasks.items():
                if (task.is_finished and task.completed_at and 
                    current_time - task.completed_at > max_age_seconds):
                    to_remove.append(task_id)
            
            for task_id in to_remove:
                self._tasks.pop(task_id, None)
                self._task_futures.pop(task_id, None)
        
        if to_remove:
            self.logger.info(f"Cleaned up {len(to_remove)} finished tasks")
    
    def shutdown(self):
        """Shutdown the service and cleanup resources"""
        self.logger.info("Shutting down AgentService...")
        
        # Cancel all running tasks
        with self._task_lock:
            for task_id in list(self._task_futures.keys()):
                self.cancel_task(task_id)
        
        # Shutdown executor
        self._executor.shutdown(wait=True)
        
        # Clear caches
        self._agents.clear()
        self._hwi_instances.clear()
        
        self.logger.info("AgentService shutdown complete")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown() 