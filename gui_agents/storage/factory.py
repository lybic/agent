"""
Factory for creating storage instances based on configuration.
"""

import os
import logging
from typing import Optional

from .base import TaskStorage
from .memory_storage import MemoryStorage
from .postgres_storage import PostgresStorage

logger = logging.getLogger(__name__)


def create_storage(
    backend: Optional[str] = None,
    postgres_connection_string: Optional[str] = None
) -> TaskStorage:
    """
    Create a storage instance based on configuration.
    
    Args:
        backend: Storage backend type ('memory' or 'postgres')
                 If None, reads from TASK_STORAGE_BACKEND env variable
        postgres_connection_string: PostgreSQL connection string
                                   If None, reads from POSTGRES_CONNECTION_STRING env variable
    
    Returns:
        TaskStorage instance (MemoryStorage or PostgresStorage)
    
    Raises:
        ValueError: If backend type is invalid or required configuration is missing
    """
    # Read configuration from environment variables if not provided
    if backend is None:
        backend = os.environ.get('TASK_STORAGE_BACKEND', 'memory').lower()
    
    backend = backend.lower()
    
    if backend == 'memory':
        logger.info("Using in-memory task storage")
        return MemoryStorage()
    
    elif backend == 'postgres':
        if postgres_connection_string is None:
            postgres_connection_string = os.environ.get('POSTGRES_CONNECTION_STRING')
        
        if not postgres_connection_string:
            raise ValueError(
                "PostgreSQL connection string is required for 'postgres' backend. "
                "Set POSTGRES_CONNECTION_STRING environment variable or pass it as argument."
            )
        
        logger.info("Using PostgreSQL task storage")
        return PostgresStorage(postgres_connection_string)
    
    else:
        raise ValueError(
            f"Invalid storage backend: {backend}. "
            f"Supported backends: 'memory', 'postgres'"
        )
