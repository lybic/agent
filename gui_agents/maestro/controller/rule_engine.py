"""Rule Engine for Maestro Controller
Responsible for handling various business rules and state checks
"""

import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from gui_agents.maestro.new_global_state import NewGlobalState
from ..enums import ControllerState, SubtaskStatus, TaskStatus, TriggerCode
from ..data_models import CommandData
from ..Action import Action

logger = logging.getLogger(__name__)


class RuleEngine:
    """Rule engine responsible for handling various business rules and state checks"""
    
    def __init__(
        self, 
        global_state: NewGlobalState, 
        max_steps: int = 50,
        max_state_switches: int = 500, 
        max_state_duration: int = 300,
        flow_config: Optional[Dict[str, Any]] = None,
    ):
        self.global_state = global_state
        self.max_steps = max_steps
        self.max_state_switches = max_state_switches
        self.max_state_duration = max_state_duration
        # Added: Flow configuration thresholds
        self.flow_config = flow_config or {}
        self.quality_check_interval_secs = self.flow_config.get("quality_check_interval_secs", 300)
        self.first_quality_check_min_commands = self.flow_config.get("first_quality_check_min_commands", 5)
        self.repeated_action_min_consecutive = self.flow_config.get("repeated_action_min_consecutive", 3)
        self.replan_long_execution_threshold = self.flow_config.get("replan_long_execution_threshold", 15)
        self.plan_number_limit = self.flow_config.get("plan_number_limit", 50)
    
    def _are_actions_similar(self, action1: Dict[str, Any], action2: Dict[str, Any]) -> bool:
        """Check if two Actions are the same (excluding descriptive fields)
        
        Args:
            action1: Dictionary representation of the first Action
            action2: Dictionary representation of the second Action
            
        Returns:
            bool: Returns True if the two Actions are the same, otherwise False
        """
        try:
            # Check if Action types are the same
            if action1.get("type") != action2.get("type"):
                return False
            
            # Get Action type
            action_type = action1.get("type")
            
            # Define descriptive fields to exclude (these fields don't affect actual Action execution)
            descriptive_fields = {
                "element_description",  # Click, DoubleClick, Move, Scroll
                "starting_description",  # Drag
                "ending_description",    # Drag
            }
            
            # Compare all non-descriptive fields
            for key in action1:
                if key in descriptive_fields:
                    continue  # Skip descriptive fields
                
                if key not in action2:
                    return False
                
                if action1[key] != action2[key]:
                    return False
            
            # Check if action2 has fields that action1 doesn't have (except descriptive fields)
            for key in action2:
                if key in descriptive_fields:
                    continue  # Skip descriptive fields
                
                if key not in action1:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error comparing actions: {e}")
            return False
    
    def _check_consecutive_similar_actions(self, commands: List[CommandData], min_consecutive: int = 3) -> bool:
        """Check if there are consecutive similar Actions
        
        Args:
            commands: List of commands
            min_consecutive: Minimum consecutive count
            
        Returns:
            bool: Returns True if consecutive similar Actions are found, otherwise False
        """
        return False
        try:
            if min_consecutive is None:
                min_consecutive = self.repeated_action_min_consecutive
            if len(commands) < min_consecutive:
                return False
            
            # Start from the latest command and check consecutive Actions
            consecutive_count = 1
            current_action = commands[-1].action
            
            # Check forward from the second-to-last command
            for i in range(len(commands) - 2, -1, -1):
                if self._are_actions_similar(current_action, commands[i].action):
                    consecutive_count += 1
                    if consecutive_count >= min_consecutive:
                        logger.info(f"Found {consecutive_count} consecutive similar actions")
                        return True
                else:
                    # Reset count
                    consecutive_count = 1
                    current_action = commands[i].action
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking consecutive similar actions: {e}")
            return False
    
    def check_task_state_rules(self, state_switch_count: int) -> Optional[tuple[ControllerState, TriggerCode]]:
        """Check task_state related rules, including termination conditions
        
        Returns:
            Optional[tuple[ControllerState, TriggerCode]]: Returns new state and corresponding TriggerCode, returns None if no rules are triggered
        """
        try:
            task = self.global_state.get_task()
            if not task:
                return None

            # # Check maximum state switch count
            # if state_switch_count >= self.max_state_switches:
            #     logger.warning(
            #         f"Maximum state switches ({self.max_state_switches}) reached"
            #     )
            #     self.global_state.update_task_status(TaskStatus.REJECTED)
            #     return (ControllerState.DONE, TriggerCode.RULE_MAX_STATE_SWITCHES_REACHED)

            # Check task status
            if task.status == "completed":
                logger.info("Task marked as completed")
                return (ControllerState.DONE, TriggerCode.RULE_TASK_COMPLETED)

            # Check planning count limit - if planning count exceeds configured limit, mark task as failed
            plan_num = self.global_state.get_plan_num()
            if plan_num > self.plan_number_limit:
                logger.warning(
                    f"Plan number ({plan_num}) exceeds limit ({self.plan_number_limit}), marking task as REJECTED")
                self.global_state.update_task_status(TaskStatus.REJECTED)
                return (ControllerState.DONE, TriggerCode.RULE_PLAN_NUMBER_EXCEEDED)

            # current_step greater than max_steps - rejected/fulfilled
            if task.step_num >= self.max_steps:
                # Check if all subtasks are completed
                logger.warning(
                    f"Step number ({task.step_num}) >= max_steps ({self.max_steps}) but subtasks not completed, marking task as REJECTED"
                )
                self.global_state.update_task_status(TaskStatus.REJECTED)
                return (ControllerState.DONE, TriggerCode.RULE_STATE_SWITCH_COUNT_EXCEEDED)
                    

            return None

        except Exception as e:
            logger.error(f"Error checking task state rules: {e}")
            return None
    
    def check_current_state_rules(self) -> Optional[tuple[ControllerState, TriggerCode]]:
        """Check current_state related rules
        
        Returns:
            Optional[tuple[ControllerState, TriggerCode]]: Returns new state and corresponding TriggerCode, returns None if no rules are triggered
        """
        try:
            task = self.global_state.get_task()
            if not task:
                return None

            # Quality check trigger logic: 5 commands have been generated since the last quality check, and the creation time of these 5 commands is all greater than the last quality check time
            gate_checks = self.global_state.get_gate_checks()
            if gate_checks:
                # Get the time of the most recent quality check
                latest_quality_check = max(gate_checks, key=lambda x: x.created_at)
                latest_quality_check_time = datetime.fromisoformat(latest_quality_check.created_at)
                
                # Check if there are enough commands for quality check
                all_commands = self.global_state.get_commands()
                
                # Calculate the number of new commands generated since the last quality check
                new_commands_count = 0
                for command in reversed(all_commands):  # Start checking from the latest command
                    cmd_time = datetime.fromisoformat(command.created_at)
                    if cmd_time > latest_quality_check_time:
                        new_commands_count += 1
                    else:
                        break  # Stop when encountering commands earlier than quality check time
                
                # If the number of newly generated commands reaches the threshold, trigger quality check
                if (new_commands_count >= self.first_quality_check_min_commands and 
                    self.global_state.get_controller_current_state() not in [ControllerState.QUALITY_CHECK, ControllerState.DONE]):
                    logger.info(f"Quality check triggered: {new_commands_count} new commands after last quality check at {latest_quality_check_time}, switching to QUALITY_CHECK")
                    return (ControllerState.QUALITY_CHECK, TriggerCode.RULE_QUALITY_CHECK_STEPS)
            else:
                # If there are no quality check records and the current subtask's command count reaches the threshold, perform the first quality check
                if task.current_subtask_id:
                    subtask = self.global_state.get_subtask(task.current_subtask_id)
                    if (subtask and len(subtask.command_trace_ids) >= self.first_quality_check_min_commands and 
                        self.global_state.get_controller_current_state() not in [ControllerState.QUALITY_CHECK, ControllerState.DONE]):
                        logger.info(f"First quality check after {self.first_quality_check_min_commands} commands for subtask {task.current_subtask_id}, switching to QUALITY_CHECK")
                        return (ControllerState.QUALITY_CHECK, TriggerCode.RULE_QUALITY_CHECK_STEPS)

            # Consecutive similar actions exceed configured count - QUALITY_CHECK
            if task.current_subtask_id:
                subtask = self.global_state.get_subtask(task.current_subtask_id)
                if subtask and len(subtask.command_trace_ids) >= self.repeated_action_min_consecutive:
                    # Get all commands for the current subtask
                    commands = self.global_state.get_commands_for_subtask(task.current_subtask_id)
                    if commands and self._check_consecutive_similar_actions(commands[-self.repeated_action_min_consecutive:], min_consecutive=self.repeated_action_min_consecutive):
                        logger.info(
                            f"Found {self.repeated_action_min_consecutive}+ consecutive similar actions in subtask {task.current_subtask_id}, switching to QUALITY_CHECK"
                        )
                        return (ControllerState.QUALITY_CHECK, TriggerCode.RULE_QUALITY_CHECK_REPEATED_ACTIONS)

            # If a subtask's execution actions are too long, exceeding the configured threshold - REPLAN
            if task.current_subtask_id:
                subtask = self.global_state.get_subtask(task.current_subtask_id)
                if subtask and len(subtask.command_trace_ids) > self.replan_long_execution_threshold:
                    logger.info(
                        f"Subtask {task.current_subtask_id} has > {self.replan_long_execution_threshold} commands, switching to PLAN"
                    )
                    self.global_state.update_subtask_status(task.current_subtask_id, SubtaskStatus.REJECTED, "replan long execution, too many commands, current_subtask_id: " + task.current_subtask_id)
                    return (ControllerState.PLAN, TriggerCode.RULE_REPLAN_LONG_EXECUTION)

            return None

        except Exception as e:
            logger.error(f"Error checking current situation rules: {e}")
            return None
    
    def is_state_timeout(self) -> bool:
        """Check if the current state has timed out"""
        state_start_time = self.global_state.get_controller_state_start_time()
        return (time.time() - state_start_time) > self.max_state_duration
