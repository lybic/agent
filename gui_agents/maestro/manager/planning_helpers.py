"""
Planning helper functions for Manager
Contains helper functions for context building, prompt generation, and trigger code handling
"""

import logging
from typing import Dict, Any

from gui_agents.maestro.enums import TRIGGER_CODE_BY_MODULE
from gui_agents.maestro.manager.utils import (
    get_failed_subtasks_info, get_failure_reasons, get_current_failed_subtask,
    get_quality_check_failure_info, get_final_check_failure_info,
    get_execution_time_info, get_supplement_info, count_subtasks_from_info
)
from gui_agents.maestro.new_global_state import NewGlobalState
from gui_agents.maestro.enums import SubtaskStatus

logger = logging.getLogger(__name__)


def get_planning_context(global_state, platform: str, replan_attempts: int, 
                        planning_history: list, trigger_code: str) -> Dict[str, Any]:
    """Get context information for planning with trigger_code specific details"""
    task = global_state.get_task()
    subtasks = global_state.get_subtasks()
    screenshot = global_state.get_screenshot()

    is_replan_now = replan_attempts > 0

    context = {
        "task_objective": task.objective or "",
        "task_status": task.status or "",
        "all_subtasks": subtasks,
        "history_subtasks": get_history_subtasks_info(global_state),
        "pending_subtasks": get_pending_subtasks_info(global_state),
        "screenshot": screenshot,
        "platform": platform,
        "planning_scenario": "replan" if is_replan_now else "initial_plan",
        "replan_attempts": replan_attempts,
        "planning_history": planning_history[-3:] if planning_history else [],
        "trigger_code": trigger_code
    }

    # Add failure information only when truly re-planning
    if is_replan_now:
        context["failed_subtasks"] = get_failed_subtasks_info(global_state)
        context["failure_reasons"] = get_failure_reasons(global_state)
        # Add recent subtasks operation history (last two)
        context["recent_subtasks_history"] = get_recent_subtasks_operation_history(global_state, limit=2)

    # Add trigger_code specific context information
    context.update(get_trigger_code_specific_context(global_state, trigger_code))

    return context


def get_trigger_code_specific_context(global_state, trigger_code: str) -> Dict[str, Any]:
    """Get trigger_code specific context information"""
    context = {}
    
    if trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["work_cannot_execute"]:
        # Worker cannot execute situation
        context["trigger_context"] = {
            "type": "worker_cannot_execute",
            "description": "Worker reported that the current subtask cannot be executed",
            "focus": "Need to analyze why the subtask cannot be executed and find alternative approaches"
        }
        # Get current failed subtask information
        current_subtask = get_current_failed_subtask(global_state)
        if current_subtask:
            context["current_failed_subtask"] = current_subtask
            
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["quality_check_failed"]:
        # Quality check failed situation
        context["trigger_context"] = {
            "type": "quality_check_failed",
            "description": "Quality check failed for the current subtask",
            "focus": "Need to understand why quality check failed and improve the approach"
        }
        # Get specific information about quality check failure
        context["quality_check_failure"] = get_quality_check_failure_info(global_state)
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["no_worker_decision"]:
        # Worker has no decision situation
        context["trigger_context"] = {
            "type": "no_worker_decision",
            "description": "Worker could not make a decision for the current subtask",
            "focus": "Need to provide clearer instructions or break down the subtask"
        }
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["get_action_error"]:
        # GET_ACTION state error situation
        context["trigger_context"] = {
            "type": "get_action_error",
            "description": "Error occurred during GET_ACTION state processing",
            "focus": "Need to handle the error and provide alternative approaches"
        }
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["quality_check_error"]:
        # Quality check error situation
        context["trigger_context"] = {
            "type": "quality_check_error",
            "description": "Error occurred during quality check process",
            "focus": "Need to handle the quality check error and continue with alternative approaches"
        }
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["final_check_failed"]:
        # Final quality check failed situation
        context["trigger_context"] = {
            "type": "final_check_failed",
            "description": "Final quality check failed for the entire task",
            "focus": "Need to address the final quality issues and complete the task"
        }
        # Get final quality check failure information
        context["final_check_failure"] = get_final_check_failure_info(global_state)
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["rule_replan_long_execution"]:
        # Long execution time requiring replanning situation
        context["trigger_context"] = {
            "type": "long_execution_replan",
            "description": "Task has been executing for too long, need to replan",
            "focus": "Need to optimize the execution plan and reduce execution time"
        }
        # Get execution time information
        context["execution_time_info"] = get_execution_time_info(global_state)
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["no_subtasks"]:
        # No subtasks situation
        context["trigger_context"] = {
            "type": "no_subtasks",
            "description": "No subtasks available for execution",
            "focus": "Need to create initial subtasks for the task"
        }
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["init_error"]:
        # Initialization error situation
        context["trigger_context"] = {
            "type": "init_error",
            "description": "Error occurred during task initialization",
            "focus": "Need to handle initialization error and start fresh"
        }
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["supplement_completed"]:
        # Supplement completed situation
        context["trigger_context"] = {
            "type": "supplement_completed",
            "description": "Supplement collection completed, ready to replan",
            "focus": "Use the collected supplement information to improve planning"
        }
        # Get supplement information
        context["supplement_info"] = get_supplement_info(global_state)
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["supplement_error"]:
        # Supplement error situation
        context["trigger_context"] = {
            "type": "supplement_error",
            "description": "Error occurred during supplement collection",
            "focus": "Handle supplement error and continue with available information"
        }
        
    else:
        # Default situation
        context["trigger_context"] = {
            "type": "general_replan",
            "description": f"General replanning triggered by: {trigger_code}",
            "focus": "Analyze the current situation and improve the plan"
        }
        
    return context


def generate_planning_prompt(context: Dict[str, Any], 
                           integrated_knowledge: str = "", trigger_code: str = "controller") -> str:
    """Generate planning prompt based on scenario, context and trigger_code"""

    # Determine scenario from context to ensure auto mode works
    planning_scenario: str = context.get("planning_scenario", "initial_plan")
    history_subtasks: str = context.get("history_subtasks", "")
    pending_subtasks: str = context.get("pending_subtasks", "")
    is_replan: bool = planning_scenario == "replan"
    trigger_context = context.get("trigger_context", {})
    
    # Generate trigger_code specific planning guidance
    trigger_specific_guidance = generate_trigger_specific_guidance(trigger_code, trigger_context, context)

    # Scenario-specific planning task section
    if is_replan:
        planning_task = f"""
# Current Planning Task
You need to RE-PLAN the task based on prior attempts and failures.

# CRITICAL: Original Task Objective Alignment
**ALWAYS keep the original task objective as your north star**: {context.get('task_objective', '')}
- Every subtask MUST directly contribute to achieving the original objective
- Do NOT deviate from the core purpose or add unrelated functionality
- Ensure the overall plan logically leads to completing the original task

# Planning Focus (Re-plan)
- Analyze why previous attempts failed and identify bottlenecks
- Preserve valid progress; DO NOT duplicate completed subtasks
- Adjust ordering, refine steps, or replace failing subtasks
- Ensure dependencies remain valid and achievable
- **CRITICAL**: Verify each new subtask is necessary and sufficient for the original objective
- **ALLOWED**: Consider alternative approaches only when previous methods have failed

{trigger_specific_guidance}
"""
        decision = """
# Planning Decision (Re-plan)
- Prioritize resolving blockers and mitigating risks found previously
- Introduce new/modified subtasks only where necessary for the ORIGINAL objective
- Keep completed subtasks out of the list; reference them only in dependencies
- **MANDATORY**: Before finalizing, review the entire plan to ensure it directly serves the original task objective
- **ALLOWED**: Use alternative approaches when previous methods have proven ineffective
- **FORBIDDEN**: Add verification/validation-only subtasks (Verify/Review/Confirm/Test/Check/QA). Evaluator performs quality checks and the system will re-plan on failures.
"""
    else:
        planning_task = f"""
# Current Planning Task
You need to perform INITIAL PLANNING to decompose the objective into executable subtasks.

# Planning Focus (Initial)
- Cover the full path from start to completion
- Define clear, verifiable completion criteria for each subtask
- Keep reasonable granularity; avoid overly fine steps unless needed for reliability
- **CRITICAL**: Generate only ONE optimal execution path for each subtask
- **FORBIDDEN**: Do NOT create alternative approaches, backup plans, or fallback strategies
- **FORBIDDEN**: Do NOT create standalone verification/validation-only subtasks (e.g., "Verify", "Validation", "Review", "Confirm", "Test", "Check", "QA"). Quality checks are handled automatically by the Evaluator.

{trigger_specific_guidance}
"""
        decision = """
# Planning Decision (Initial)
- Decompose the user objective into an ordered set of executable subtasks
- Make dependencies explicit and minimize unnecessary coupling
- Assign appropriate worker roles to each subtask
- **MANDATORY**: Ensure every subtask passes the rationality self-check
- **MANDATORY**: Verify the complete plan directly achieves the stated objective
- **FORBIDDEN**: Do NOT include alternative approaches or backup strategies
- **SINGLE PATH**: Focus on the most likely successful approach for each subtask
"""

    # Common guidance and output schema
    common_guidance = f"""
# Decomposition Principles
1. Each subtask should have clear objectives and completion criteria
2. Dependencies between subtasks should be clear
3. Assign appropriate Worker type for each subtask
4. Consider execution risks and exceptional cases
5. Every subtask must be justified against the original objective

# No Side Effects (No Extra Artifacts/Files)
- Do NOT create, save any files, documents, screenshots, notes, or other artifacts unless the objective explicitly requests such outputs.
- Prefer reusing currently open software and webpages; avoid opening new ones unless necessary for the objective.

# CRITICAL ANALYST ASSIGNMENT RULES
1. **NEVER assign Analyst as the first subtask** - Analyst cannot start any task
2. **Analyst MUST be preceded by Operator** - Operator must write information to memory first
3. **Analyst can only work with memory** - cannot access desktop or perform GUI operations
4. **Verify memory availability** - ensure all required data is in memory before assigning Analyst
5. **Analyst dependency chain**: Operator (gather) → Analyst (analyze) → Operator (apply)

# Mandatory Cross-Role Split for GUI-derived Q&A/Analysis
- If the objective requires reading content from GUI and then answering questions/doing analysis:
  1) Operator must gather the content via GUI and store it with memorize using QUESTION / DATA / GUIDANCE fields.
  2) Analyst must answer using only memory/artifacts (no screenshot), producing the final answers/list.
  3) Operator must write/apply the answers back into GUI and save/confirm.
- Do not merge these roles in one subtask. Keep one clear role per subtask.
- Prefer batching: gather all items first, then answer once, then write once.
- Note: Do NOT include verification/validation-only subtasks; Evaluator will handle quality checks automatically.

# Task Information
Objective: {context.get('task_objective', '')}
Planning Scenario: {planning_scenario}
Trigger Code: {trigger_code}
Current Progress: {count_subtasks_from_info(context.get('history_subtasks', ''))} subtask completed, {count_subtasks_from_info(context.get('pending_subtasks', ''))} subtask pending
History Subtasks: {history_subtasks}
Pending Subtasks: {pending_subtasks}
Platform: {context.get('platform', '')}
"""

    # Replan-specific extra diagnostic information
    replan_info = ""
    if is_replan:
        recent_ops = context.get("recent_subtasks_history", "")
        replan_info = f"""
# Re-planning Information
Re-planning Attempts: {context.get('replan_attempts', 0)}
Failed Subtasks: {context.get('failed_subtasks', '')}
Failure Reasons: {context.get('failure_reasons', '')}

# Recent Subtasks Operation History (latest 2)
{recent_ops if recent_ops else 'N/A'}

# Re-plan Output Constraints
- Only include new subtasks in the JSON list
- Do not include already completed subtasks
- Keep or update dependencies to reference existing subtask IDs when applicable
- Before outputting, perform final alignment check with original objective
"""

    # Environment information
    env_info = f"""
# Current Environment Information
Screenshot Available: {'Yes' if context.get('screenshot') else 'No'}

# Retrieved/Integrated Knowledge
You may refer to some retrieved knowledge if you think they are useful.{integrated_knowledge if integrated_knowledge else 'N/A'}

# FINAL REMINDER
**Before submitting your plan, perform one final check:**
1. Does every subtask directly serve the original objective: "{context.get('task_objective', '')}"?
2. Is the sequence logical and efficient?
3. Are there any unnecessary or redundant steps?
4. Will completing all subtasks actually achieve the stated goal?
5. **CRITICAL ANALYST CHECK**: 
   - Is the first subtask assigned to Analyst? (FORBIDDEN - Analyst cannot be first)
   - For any Analyst subtask, has Operator written required information to memory first?
   - Can Analyst work with only memory data (no desktop access needed)?

Please output the planning solution based on the above information:
"""

    planning_prompt = f"""
{planning_task}
{decision}
{common_guidance}
{replan_info}
{env_info}
"""

    return planning_prompt


def generate_trigger_specific_guidance(trigger_code: str, trigger_context: Dict[str, Any], 
                                     context: Dict[str, Any]) -> str:
    """Generate trigger_code specific planning guidance"""
    
    if trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["work_cannot_execute"]:
        return """
# Worker Cannot Execute - Specific Guidance
- The Worker reported that the current subtask cannot be executed
- Analyze the specific reason for failure and find alternative approaches
- Consider breaking down the subtask into smaller, more manageable steps
- Look for alternative methods or tools to achieve the same goal
- Ensure the new plan addresses the specific execution barriers identified
"""
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["quality_check_failed"]:
        quality_info = context.get("quality_check_failure", {})
        return f"""
# Quality Check Failed - Specific Guidance
- The quality check failed for the current subtask
- Review the quality check notes: {quality_info.get('notes', 'No notes available')}
- Identify what specific quality criteria were not met
- Improve the approach to meet the quality standards
- Consider adding intermediate verification steps
- Ensure the new plan includes better quality control measures
"""
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["no_worker_decision"]:
        return """
# No Worker Decision - Specific Guidance
- Worker could not make a decision for the current subtask
- Provide clearer, more specific instructions
- Break down the subtask into smaller, more obvious steps
- Add more context or examples to guide the worker
- Consider using a different worker role that might be better suited
- Ensure the new plan has clear decision criteria and fallback options
"""
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["get_action_error"]:
        return """
# GET_ACTION Error - Specific Guidance
- Error occurred during GET_ACTION state processing
- Handle the error gracefully and provide alternative approaches
- Consider simplifying the action generation process
- Add error handling and recovery mechanisms
- Ensure the new plan is more robust and error-resistant
"""
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["quality_check_error"]:
        return """
# Quality Check Error - Specific Guidance
- Error occurred during quality check process
- Handle the quality check error and continue with alternative approaches
- Consider using simpler quality criteria
- Add fallback quality assessment methods
- Ensure the new plan includes error handling for quality checks
"""
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["final_check_failed"]:
        final_info = context.get("final_check_failure", {})
        return f"""
# Final Check Failed - Specific Guidance
- Final quality check failed for the entire task
- Total gate checks: {final_info.get('total_gate_checks', 0)}
- Failed gate checks: {final_info.get('failed_gate_checks', 0)}
- Address the final quality issues and complete the task
- Review all completed subtasks for completeness
- Add missing steps or verification procedures
- Ensure the new plan addresses the root causes of final check failure
"""
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["rule_replan_long_execution"]:
        exec_info = context.get("execution_time_info", {})
        return f"""
# Long Execution Replan - Specific Guidance
- Task has been executing for too long, need to replan
- Current step number: {exec_info.get('step_num', 0)}
- Current plan number: {exec_info.get('plan_num', 0)}
- Optimize the execution plan and reduce execution time
- Consider parallel execution where possible
- Simplify complex subtasks into more efficient steps
- Add timeouts and progress monitoring
- Ensure the new plan is more time-efficient
"""
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["no_subtasks"]:
        return """
# No Subtasks - Specific Guidance
- No subtasks available for execution
- Create initial subtasks for the task
- Break down the main objective into logical steps
- Ensure all necessary steps are covered
- Consider dependencies and execution order
- Assign appropriate worker roles to each subtask
"""
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["init_error"]:
        return """
# Init Error - Specific Guidance
- Error occurred during task initialization
- Handle initialization error and start fresh
- Simplify the initial setup process
- Add error recovery mechanisms
- Ensure the new plan has better initialization procedures
"""
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["supplement_completed"]:
        supplement_info = context.get("supplement_info", {})
        return f"""
# Supplement Completed - Specific Guidance
- Supplement collection completed, ready to replan
- Supplement content length: {supplement_info.get('supplement_length', 0)} characters
- Use the collected supplement information to improve planning
- Incorporate the new information into the task plan
- Update subtasks based on the additional context
- Ensure the new plan leverages all available information
"""
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["supplement_error"]:
        return """
# Supplement Error - Specific Guidance
- Error occurred during supplement collection
- Handle supplement error and continue with available information
- Work with the information that is already available
- Consider alternative information sources
- Ensure the new plan can work with limited information
"""
        
    else:
        return f"""
# General Replanning - Specific Guidance
- General replanning triggered by: {trigger_code}
- Analyze the current situation and improve the plan
- Consider all available context and information
- Address any identified issues or bottlenecks
- Ensure the new plan is more robust and effective
"""


def get_history_subtasks_info(global_state) -> str:
    """Get information about completed subtasks"""
    from gui_agents.maestro.manager.utils import get_history_subtasks_info as _get_history_subtasks_info
    return _get_history_subtasks_info(global_state)


def get_pending_subtasks_info(global_state) -> str:
    """Get information about pending subtasks"""
    from gui_agents.maestro.manager.utils import get_pending_subtasks_info as _get_pending_subtasks_info
    return _get_pending_subtasks_info(global_state) 

def get_recent_subtasks_operation_history(global_state: NewGlobalState, limit: int = 2) -> str:
    """Get operation history of recently completed subtasks (up to limit), formatted as readable text.
    Rules:
    - Prioritize using Task.history_subtask_ids to get recent (non-READY) subtasks from back to front
    - If insufficient quantity, supplement with all subtasks with non-READY status, sorted by updated_at in descending order (deduplicated)
    - List commands for each subtask (in reverse chronological order), including type, status, message and execution summary
    """
    try:
        task = global_state.get_task()
        all_subtasks = global_state.get_subtasks()
        id_to_subtask = {s.subtask_id: s for s in all_subtasks}

        # Only select subtasks with non-READY status
        def _is_non_ready(subtask):
            try:
                return getattr(subtask, 'status', '') != SubtaskStatus.READY.value
            except Exception:
                return True

        recent_ids = list(reversed(task.history_subtask_ids)) if getattr(task, 'history_subtask_ids', None) else []
        recent_subtasks = []
        for sid in recent_ids:
            st = id_to_subtask.get(sid)
            if st and _is_non_ready(st):
                recent_subtasks.append(st)
                if len(recent_subtasks) >= limit:
                    break
        if len(recent_subtasks) < limit:
            # Filter non-READY from all subtasks, supplement in descending order by updated_at
            remaining = [s for s in all_subtasks if s.subtask_id not in {st.subtask_id for st in recent_subtasks} and _is_non_ready(s)]
            remaining.sort(key=lambda x: getattr(x, 'updated_at', ''), reverse=True)
            for s in remaining:
                recent_subtasks.append(s)
                if len(recent_subtasks) >= limit:
                    break

        lines = []
        if not recent_subtasks:
            return "No historical operation records"

        for idx, subtask in enumerate(recent_subtasks, 1):
            lines.append(f"=== Subtask {idx} ===")
            lines.append(f"ID: {subtask.subtask_id}")
            title = getattr(subtask, 'title', '') or ''
            if title:
                lines.append(f"Title: {title}")
            # Command history
            commands = list(global_state.get_commands_for_subtask(subtask.subtask_id))
            if not commands:
                lines.append("No operation command records")
                lines.append("")
                continue
            for i, cmd in enumerate(commands, 1):
                action_type = "Unknown operation"
                action_desc = ""
                try:
                    if isinstance(cmd.action, dict):
                        if "type" in cmd.action:
                            action_type = cmd.action["type"]
                        if "message" in cmd.action:
                            action_desc = cmd.action["message"]
                        elif "element_description" in cmd.action:
                            action_desc = f"Operate element: {cmd.action['element_description']}"
                        elif "text" in cmd.action:
                            action_desc = f"Input text: {cmd.action['text']}"
                        elif "keys" in cmd.action:
                            action_desc = f"Keys: {cmd.action['keys']}"
                except Exception:
                    pass
                status = getattr(cmd, 'worker_decision', '')
                message = getattr(cmd, 'message', '') or ''
                exec_status = getattr(cmd, 'exec_status', '')
                exec_message = getattr(cmd, 'exec_message', '')

                lines.append(f"{i}. [{action_type}] - Status: {status}")
                if action_desc:
                    lines.append(f"   Description: {action_desc}")
                if message:
                    lines.append(f"   Message: {message}")
                if exec_status:
                    lines.append(f"   Execution status: {exec_status}")
                if exec_message:
                    lines.append(f"   Execution message: {exec_message}")
            lines.append("")
        return "\n".join(lines)
    except Exception:
        return ""