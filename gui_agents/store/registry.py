# gui_agents/s2/store/registry.py

# Usage: in any file, get the object through Registry.get
# from gui_agents.store.registry import Registry
# GlobalStateStore = Registry.get("GlobalStateStore")

import threading
from typing import Optional, ClassVar


class Registry:
    """
    Registry class that supports both global singleton and task-specific instances.
    It uses a process-wide dictionary for task registries to ensure visibility
    across threads, making it compatible with asyncio.to_thread.
    """
    # For global singletons (backward compatibility)
    _global_services: ClassVar[dict[str, object]] = {}
    _global_lock: ClassVar[threading.RLock] = threading.RLock()

    # Process-wide storage for task-specific registries, protected by a lock
    _task_registries: ClassVar[dict[str, 'Registry']] = {}
    _task_registries_lock: ClassVar[threading.RLock] = threading.RLock()

    # Thread-local storage can be used as a cache for faster access
    _thread_local: ClassVar[threading.local] = threading.local()

    def __init__(self):
        """Create a new registry instance (for a specific task)."""
        self._services: dict[str, object] = {}
        self._lock = threading.RLock()

    # ========== Instance methods (for a single registry) ==========
    def register_instance(self, name: str, obj: object):
        """Register an object in this registry instance."""
        with self._lock:
            self._services[name] = obj

    def get_instance(self, name: str) -> object:
        """Get an object from this registry instance."""
        with self._lock:
            if name not in self._services:
                raise KeyError(f"{name!r} not registered in this Registry instance")
            return self._services[name]

    def clear_instance(self):
        """Clear all objects in this registry instance."""
        with self._lock:
            self._services.clear()

    # ========== Class methods for global registry (backward compatibility) ==========
    @classmethod
    def register(cls, name: str, obj: object):
        """Register an object in the global registry."""
        with cls._global_lock:
            cls._global_services[name] = obj

    @classmethod
    def get(cls, name: str) -> object:
        """Get an object from the global registry."""
        with cls._global_lock:
            if name not in cls._global_services:
                raise KeyError(f"{name!r} not registered in global Registry")
            return cls._global_services[name]

    @classmethod
    def clear(cls):
        """Clear all objects in the global registry."""
        with cls._global_lock:
            cls._global_services.clear()

    # ========== Task-specific registry management (Process-wide) ==========
    @classmethod
    def set_task_registry(cls, task_id: str, registry: 'Registry'):
        """Set a task-specific registry, making it visible process-wide."""
        with cls._task_registries_lock:
            cls._task_registries[task_id] = registry
        
        # Also set it in thread-local for faster access within the current thread
        if not hasattr(cls._thread_local, 'task_cache'):
            cls._thread_local.task_cache = {}
        cls._thread_local.task_cache[task_id] = registry

    @classmethod
    def get_task_registry(cls, task_id: str) -> Optional['Registry']:
        """Get a task-specific registry, checking thread-local cache first."""
        # Check thread-local cache first for performance
        if hasattr(cls._thread_local, 'task_cache'):
            cached_registry = cls._thread_local.task_cache.get(task_id)
            if cached_registry:
                return cached_registry

        # If not in cache, check the process-wide dictionary
        with cls._task_registries_lock:
            registry = cls._task_registries.get(task_id)
            if registry:
                # Populate cache for subsequent calls in the same thread
                if not hasattr(cls._thread_local, 'task_cache'):
                    cls._thread_local.task_cache = {}
                cls._thread_local.task_cache[task_id] = registry
            return registry

    @classmethod
    def remove_task_registry(cls, task_id: str):
        """Remove a task-specific registry from process-wide and thread-local storage."""
        # Remove from the main process-wide storage
        with cls._task_registries_lock:
            cls._task_registries.pop(task_id, None)
        
        # Remove from the current thread's local cache, if it exists
        if hasattr(cls._thread_local, 'task_cache'):
            cls._thread_local.task_cache.pop(task_id, None)

    @classmethod
    def get_from_context(cls, name: str, task_id: Optional[str] = None) -> object:
        """
        Get an object, trying task-specific registry first, then global registry.
        This is now thread-safe across different threads for the same task_id.
        """
        # Try task-specific registry first
        if task_id:
            task_registry = cls.get_task_registry(task_id)
            if task_registry:
                try:
                    return task_registry.get_instance(name)
                except KeyError:
                    pass  # Fall back to global registry

        # Fall back to global registry for CLI mode or if not in task registry
        return cls.get(name)