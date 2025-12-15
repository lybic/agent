# Database Migrations

This directory contains SQL migration files for the PostgreSQL storage backend.

## Migration Files

- `001_add_conversation_history.sql` - Adds the `conversation_history` column to store LLM conversation history

## Running Migrations

### Automatic (Recommended)

Migrations run automatically when the PostgreSQL storage backend is initialized. No manual action is required.

### Manual

If you need to run migrations manually:

```bash
# Using environment variable
export DATABASE_URL="postgresql://user:password@host:port/database"
python -m gui_agents.storage.run_migrations

# Or using command-line argument
python -m gui_agents.storage.run_migrations --connection-string "postgresql://user:password@host:port/database"
```

### Direct SQL

You can also run the migration SQL directly:

```bash
psql "postgresql://user:password@host:port/database" -f 'sql_file.sql'
```

## Creating New Migrations

1. Create a new SQL file in this directory with a numbered prefix (e.g., `002_description.sql`)
2. Write your migration SQL using idempotent operations (e.g., `IF NOT EXISTS`)
3. Test the migration on a development database
4. The migration will run automatically on next initialization

## Migration Tracking

Migrations are tracked in the `schema_migrations` table, which is automatically created if it doesn't exist. Each migration is recorded with its version and timestamp.

## Troubleshooting

### "column does not exist" Error

This error occurs when the database schema is out of sync with the application code. Run the migration manually:

```bash
python -m gui_agents.storage.run_migrations --connection-string "your_connection_string"
```

### Migration Fails

1. Check PostgreSQL connection string is correct
2. Verify database user has necessary permissions (ALTER TABLE, CREATE TABLE)
3. Check PostgreSQL logs for detailed error messages
4. Ensure `asyncpg` is installed: `pip install asyncpg`
