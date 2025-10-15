# gui_agents/s2/store/registry.py

# Usage: in any file, get the object through Registry.get
# from gui_agents.store.registry import Registry
# GlobalStateStore = Registry.get("GlobalStateStore")

import threading
from typing import Optional


class Registry:
    """
    Registry class that supports both global singleton and task-specific instances.

    For backward compatibility, maintains the global singleton behavior while
    supporting task-level isolation for concurrent execution.
    """
    _global_services: dict[str, object] = {}
    _global_lock = threading.RLock()

    # Thread-local storage for task-specific registries
    _thread_local = threading.local()

    def __init__(self):
        """Create a new registry instance"""
        self._services: dict[str, object] = {}
        self._lock = threading.RLock()

    # ========== Instance methods ==========
    def register(self, name: str, obj: object):
        """Register an object in this registry instance"""
        with self._lock:
            self._services[name] = obj

    def get(self, name: str) -> object:
        """Get an object from this registry instance"""
        with self._lock:
            if name not in self._services:
                raise KeyError(f"{name!r} not registered in Registry")
            return self._services[name]

    def clear(self):
        """Clear all objects in this registry instance"""
        with self._lock:
            self._services.clear()

    # ========== Class methods for global registry (backward compatibility) ==========
    @classmethod
    def register(cls, name: str, obj: object):
        """Register an object in the global registry (backward compatibility)"""
        with cls._global_lock:
            cls._global_services[name] = obj

    @classmethod
    def get(cls, name: str) -> object:
        """Get an object from the global registry (backward compatibility)"""
        with cls._global_lock:
            if name not in cls._global_services:
                raise KeyError(f"{name!r} not registered in Registry")
            return cls._global_services[name]

    @classmethod
    def clear(cls):
        """Clear all objects in the global registry"""
        with cls._global_lock:
            cls._global_services.clear()

    # ========== Task-specific registry management ==========
    @classmethod
    def set_task_registry(cls, task_id: str, registry: 'Registry'):
        """Set a task-specific registry in thread-local storage"""
        if not hasattr(cls._thread_local, 'task_registries'):
            cls._thread_local.task_registries = {}
        cls._thread_local.task_registries[task_id] = registry

    @classmethod
    def get_task_registry(cls, task_id: str) -> Optional['Registry']:
        """Get a task-specific registry from thread-local storage"""
        if not hasattr(cls._thread_local, 'task_registries'):
            return None
        return cls._thread_local.task_registries.get(task_id)

    @classmethod
    def remove_task_registry(cls, task_id: str):
        """Remove a task-specific registry from thread-local storage"""
        if hasattr(cls._thread_local, 'task_registries'):
            cls._thread_local.task_registries.pop(task_id, None)

    @classmethod
    def get_from_context(cls, name: str, task_id: Optional[str] = None) -> object:
        """
        Get an object, trying task-specific registry first, then global registry.

        Args:
            name: Object name to retrieve
            task_id: Optional task ID for task-specific lookup

        Returns:
            The requested object

        Raises:
            KeyError: If object not found in any registry
        """
        # Try task-specific registry first
        if task_id:
            task_registry = cls.get_task_registry(task_id)
            if task_registry:
                try:
                    return task_registry.get(name)
                except KeyError:
                    pass  # Fall back to global registry

        # Fall back to global registry
        return cls.get(name)
