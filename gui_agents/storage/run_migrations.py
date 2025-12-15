#!/usr/bin/env python3
"""
Database migration script for PostgreSQL storage.

Usage:
    python -m gui_agents.storage.run_migrations --connection-string "postgresql://user:password@host:port/database"
    
Or with environment variable:
    export DATABASE_URL="postgresql://user:password@host:port/database"
    python -m gui_agents.storage.run_migrations
"""
import argparse
import asyncio
import logging
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from .migrate import migrate_database
except ImportError:
    # Try absolute import
    from gui_agents.storage.migrate import migrate_database


async def main():
    """Main entry point for migration script."""
    parser = argparse.ArgumentParser(description='Run database migrations for PostgreSQL storage')
    parser.add_argument(
        '--connection-string',
        help='PostgreSQL connection string (format: postgresql://user:password@host:port/database)',
        default=os.environ.get('DATABASE_URL')
    )
    
    args = parser.parse_args()
    
    if not args.connection_string:
        logger.error("No connection string provided. Use --connection-string or set DATABASE_URL environment variable")
        sys.exit(1)
    
    logger.info("Starting database migration...")
    logger.info(f"Connection: {args.connection_string.split('@')[1] if '@' in args.connection_string else 'hidden'}")
    
    success = await migrate_database(args.connection_string)
    
    if success:
        logger.info("✅ Migration completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ Migration failed")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
