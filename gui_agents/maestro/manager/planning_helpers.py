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
        # Worker无法执行的情况
        context["trigger_context"] = {
            "type": "worker_cannot_execute",
            "description": "Worker reported that the current subtask cannot be executed",
            "focus": "Need to analyze why the subtask cannot be executed and find alternative approaches"
        }
        # 获取当前失败的subtask信息
        current_subtask = get_current_failed_subtask(global_state)
        if current_subtask:
            context["current_failed_subtask"] = current_subtask
            
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["quality_check_failed"]:
        # 质检失败的情况
        context["trigger_context"] = {
            "type": "quality_check_failed",
            "description": "Quality check failed for the current subtask",
            "focus": "Need to understand why quality check failed and improve the approach"
        }
        # 获取质检失败的具体信息
        context["quality_check_failure"] = get_quality_check_failure_info(global_state)
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["no_worker_decision"]:
        # Worker没有决策的情况
        context["trigger_context"] = {
            "type": "no_worker_decision",
            "description": "Worker could not make a decision for the current subtask",
            "focus": "Need to provide clearer instructions or break down the subtask"
        }
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["get_action_error"]:
        # GET_ACTION状态错误的情况
        context["trigger_context"] = {
            "type": "get_action_error",
            "description": "Error occurred during GET_ACTION state processing",
            "focus": "Need to handle the error and provide alternative approaches"
        }
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["quality_check_error"]:
        # 质检错误的情况
        context["trigger_context"] = {
            "type": "quality_check_error",
            "description": "Error occurred during quality check process",
            "focus": "Need to handle the quality check error and continue with alternative approaches"
        }
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["final_check_failed"]:
        # 最终质检失败的情况
        context["trigger_context"] = {
            "type": "final_check_failed",
            "description": "Final quality check failed for the entire task",
            "focus": "Need to address the final quality issues and complete the task"
        }
        # 获取最终质检失败的信息
        context["final_check_failure"] = get_final_check_failure_info(global_state)
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["rule_replan_long_execution"]:
        # 长时间执行需要重规划的情况
        context["trigger_context"] = {
            "type": "long_execution_replan",
            "description": "Task has been executing for too long, need to replan",
            "focus": "Need to optimize the execution plan and reduce execution time"
        }
        # 获取执行时间信息
        context["execution_time_info"] = get_execution_time_info(global_state)
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["no_subtasks"]:
        # 没有subtask的情况
        context["trigger_context"] = {
            "type": "no_subtasks",
            "description": "No subtasks available for execution",
            "focus": "Need to create initial subtasks for the task"
        }
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["init_error"]:
        # 初始化错误的情况
        context["trigger_context"] = {
            "type": "init_error",
            "description": "Error occurred during task initialization",
            "focus": "Need to handle initialization error and start fresh"
        }
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["supplement_completed"]:
        # 补充资料完成的情况
        context["trigger_context"] = {
            "type": "supplement_completed",
            "description": "Supplement collection completed, ready to replan",
            "focus": "Use the collected supplement information to improve planning"
        }
        # 获取补充资料信息
        context["supplement_info"] = get_supplement_info(global_state)
        
    elif trigger_code == TRIGGER_CODE_BY_MODULE.MANAGER_REPLAN_CODES["supplement_error"]:
        # 补充资料错误的情况
        context["trigger_context"] = {
            "type": "supplement_error",
            "description": "Error occurred during supplement collection",
            "focus": "Handle supplement error and continue with available information"
        }
        
    else:
        # 默认情况
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

# Planning Focus (Re-plan)
- Analyze why previous attempts failed and identify bottlenecks
- Preserve valid progress; DO NOT duplicate completed subtasks
- Adjust ordering, refine steps, or replace failing subtasks
- Ensure dependencies remain valid and achievable

{trigger_specific_guidance}
"""
        decision = """
# Planning Decision (Re-plan)
- Prioritize resolving blockers and mitigating risks found previously
- Introduce new/modified subtasks only where necessary
- Keep completed subtasks out of the list; reference them only in dependencies
"""
    else:
        planning_task = f"""
# Current Planning Task
You need to perform INITIAL PLANNING to decompose the objective into executable subtasks.

# Planning Focus (Initial)
- Cover the full path from start to completion
- Define clear, verifiable completion criteria for each subtask
- Keep reasonable granularity; avoid overly fine steps unless needed for reliability

{trigger_specific_guidance}
"""
        decision = """
# Planning Decision (Initial)
- Decompose the user objective into an ordered set of executable subtasks
- Make dependencies explicit and minimize unnecessary coupling
- Assign appropriate worker roles to each subtask
"""

    # Common guidance and output schema
    common_guidance = f"""
# Decomposition Principles
1. Each subtask should have clear objectives and completion criteria
2. Dependencies between subtasks should be clear
3. Assign appropriate Worker type for each subtask
4. Consider execution risks and exceptional cases

# Mandatory Cross-Role Split for GUI-derived Q&A/Analysis
- If the objective requires reading content from GUI and then answering questions/doing analysis:
  1) Operator must gather the content via GUI and store it with memorize using QUESTION / DATA / GUIDANCE fields.
  2) Analyst must answer using only memory/artifacts (no screenshot), producing the final answers/list.
  3) Operator must write/apply the answers back into GUI and save/confirm.
- Do not merge these roles in one subtask. Keep one clear role per subtask.
- Prefer batching: gather all items first, then answer once, then write once.

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
"""

    # Environment information
    env_info = f"""
# Current Environment Information
Screenshot Available: {'Yes' if context.get('screenshot') else 'No'}

# Retrieved/Integrated Knowledge
You may refer to some retrieved knowledge if you think they are useful.{integrated_knowledge if integrated_knowledge else 'N/A'}

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
    """获取最近完成的子任务（最多limit个）的操作历史，格式化为可读文本。
    规则：
    - 优先使用 Task.history_subtask_ids 从后向前取最近（非 READY）子任务
    - 若数量不足，补充使用所有子任务中状态非 READY 的，按 updated_at 倒序补齐（去重）
    - 每个子任务下列出该子任务的命令（按时间倒序），包含类型、状态、消息与执行摘要
    """
    try:
        task = global_state.get_task()
        all_subtasks = global_state.get_subtasks()
        id_to_subtask = {s.subtask_id: s for s in all_subtasks}

        # 仅选择状态非 READY 的子任务
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
            # 从所有子任务中筛选非 READY，按 updated_at 倒序补齐
            remaining = [s for s in all_subtasks if s.subtask_id not in {st.subtask_id for st in recent_subtasks} and _is_non_ready(s)]
            remaining.sort(key=lambda x: getattr(x, 'updated_at', ''), reverse=True)
            for s in remaining:
                recent_subtasks.append(s)
                if len(recent_subtasks) >= limit:
                    break

        lines = []
        if not recent_subtasks:
            return "无历史操作记录"

        for idx, subtask in enumerate(recent_subtasks, 1):
            lines.append(f"=== 子任务 {idx} ===")
            lines.append(f"ID: {subtask.subtask_id}")
            title = getattr(subtask, 'title', '') or ''
            if title:
                lines.append(f"标题: {title}")
            # 命令历史
            commands = list(global_state.get_commands_for_subtask(subtask.subtask_id))
            if not commands:
                lines.append("无操作命令记录")
                lines.append("")
                continue
            for i, cmd in enumerate(commands, 1):
                action_type = "未知操作"
                action_desc = ""
                try:
                    if isinstance(cmd.action, dict):
                        if "type" in cmd.action:
                            action_type = cmd.action["type"]
                        if "message" in cmd.action:
                            action_desc = cmd.action["message"]
                        elif "element_description" in cmd.action:
                            action_desc = f"操作元素: {cmd.action['element_description']}"
                        elif "text" in cmd.action:
                            action_desc = f"输入文本: {cmd.action['text']}"
                        elif "keys" in cmd.action:
                            action_desc = f"按键: {cmd.action['keys']}"
                except Exception:
                    pass
                status = getattr(cmd, 'worker_decision', '')
                message = getattr(cmd, 'message', '') or ''
                exec_status = getattr(cmd, 'exec_status', '')
                exec_message = getattr(cmd, 'exec_message', '')

                lines.append(f"{i}. [{action_type}] - 状态: {status}")
                if action_desc:
                    lines.append(f"   描述: {action_desc}")
                if message:
                    lines.append(f"   消息: {message}")
                if exec_status:
                    lines.append(f"   执行状态: {exec_status}")
                if exec_message:
                    lines.append(f"   执行消息: {exec_message}")
            lines.append("")
        return "\n".join(lines)
    except Exception:
        return ""