# Task Storage Migration Guide

This guide helps you migrate from the in-memory task storage to external PostgreSQL storage.

## Before You Start

The new storage layer is **backward compatible**. By default, the service uses in-memory storage just like before. No action is required unless you want persistent storage.

## Migration Steps

### Step 1: Install PostgreSQL

On Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
```

### Step 2: Create Database

```bash
sudo -u postgres psql
CREATE DATABASE agent_tasks;
CREATE USER agent_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE agent_tasks TO agent_user;
\q
```

### Step 3: Install Python Dependencies

```bash
pip install asyncpg
```

### Step 4: Configure Environment

Edit your `.env` file:

```bash
TASK_STORAGE_BACKEND=postgres
POSTGRES_CONNECTION_STRING=postgresql://agent_user:your_password@localhost:5432/agent_tasks
```

### Step 5: Restart Service

The database schema will be created automatically on first use.

For complete documentation, see `gui_agents/storage/README.md`
