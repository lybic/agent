-- Migration: Add conversation_history column to agent_tasks table
-- Date: 2025-12-15
-- Description: Adds the conversation_history JSONB column to store LLM conversation history

-- Add the conversation_history column if it doesn't exist
ALTER TABLE agent_tasks 
ADD COLUMN IF NOT EXISTS conversation_history JSONB;

-- Add comment for documentation
COMMENT ON COLUMN agent_tasks.conversation_history IS 'LLM conversation history (excluding images) stored as JSON';
