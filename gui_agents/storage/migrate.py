"""
Database migration utilities for PostgreSQL storage.

This module provides utilities to run database migrations for the PostgreSQL storage backend.
"""
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import asyncpg
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    asyncpg = None
    logger.warning("`asyncpg` not installed. PostgreSQL migrations will not be available.")


class MigrationManager:
    """Manages database migrations for PostgreSQL storage."""
    
    def __init__(self, connection_string: str):
        """
        Initialize migration manager.
        
        Args:
            connection_string: PostgreSQL connection string
        """
        if not POSTGRES_AVAILABLE:
            raise ImportError(
                "asyncpg is required for PostgreSQL migrations. "
                "Install it with: pip install asyncpg"
            )
        
        self.connection_string = connection_string
        self.migrations_dir = Path(__file__).parent / "migrations"
    
    async def run_migrations(self) -> bool:
        """
        Run all pending migrations.
        
        Returns:
            bool: True if migrations were successful
        """
        if not self.migrations_dir.exists():
            logger.warning(f"Migrations directory not found: {self.migrations_dir}")
            return True
        
        try:
            conn = await asyncpg.connect(self.connection_string)
            
            # Create migrations tracking table if not exists
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(255) PRIMARY KEY,
                    applied_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            
            # Get already applied migrations
            applied = await conn.fetch("SELECT version FROM schema_migrations")
            applied_versions = {row['version'] for row in applied}
            
            # Get all migration files
            migration_files = sorted(self.migrations_dir.glob("*.sql"))
            
            for migration_file in migration_files:
                version = migration_file.stem
                
                if version in applied_versions:
                    logger.debug(f"Migration {version} already applied, skipping")
                    continue
                
                logger.info(f"Applying migration: {version}")
                
                # Read and execute migration
                sql = migration_file.read_text()
                await conn.execute(sql)
                
                # Record migration as applied
                await conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES ($1)",
                    version
                )
                
                logger.info(f"Migration {version} applied successfully")
            
            await conn.close()
            logger.info("All migrations completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to run migrations: {e}")
            return False
    
    async def run_migration_file(self, migration_file: str) -> bool:
        """
        Run a specific migration file.
        
        Args:
            migration_file: Path to migration SQL file
            
        Returns:
            bool: True if migration was successful
        """
        try:
            conn = await asyncpg.connect(self.connection_string)
            
            migration_path = Path(migration_file)
            if not migration_path.exists():
                logger.error(f"Migration file not found: {migration_file}")
                return False
            
            logger.info(f"Applying migration: {migration_path.name}")
            sql = migration_path.read_text()
            await conn.execute(sql)
            await conn.close()
            
            logger.info(f"Migration {migration_path.name} applied successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to run migration {migration_file}: {e}")
            return False


async def migrate_database(connection_string: str) -> bool:
    """
    Convenience function to run all migrations.
    
    Args:
        connection_string: PostgreSQL connection string
        
    Returns:
        bool: True if migrations were successful
    """
    manager = MigrationManager(connection_string)
    return await manager.run_migrations()
