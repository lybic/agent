# new_global_state.py
import json
import os
import time
import logging
import io
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

from PIL import Image

from gui_agents.utils.common_utils import Node
from gui_agents.utils.file_utils import (
    locked, safe_json_dump, safe_json_load, 
    safe_write_json, safe_read_json, safe_write_text, safe_read_text
)
from gui_agents.utils.id_utils import generate_uuid, generate_timestamp_id

logger = logging.getLogger(__name__)

# ========= Standardized Enums =========
class TaskStatus(str, Enum):
    CREATED = "created"
    PENDING = "pending"
    ON_HOLD = "on_hold"
    FULFILLED = "fulfilled"
    REJECTED = "rejected"

class SubtaskStatus(str, Enum):
    READY = "ready"
    PENDING = "pending"
    STALE = "stale"
    FULFILLED = "fulfilled"
    REJECTED = "rejected"

class ExecStatus(str, Enum):
    EXECUTED = "executed"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"
    ERROR = "error"

class GateDecision(str, Enum):
    GATE_DONE = "gate_done"
    GATE_FAIL = "gate_fail"
    GATE_SUPPLEMENT = "gate_supplement"
    GATE_CONTINUE = "gate_continue"

class GateTrigger(str, Enum):
    PERIODIC = "periodic"
    BY_WORKER = "by_worker"
    BY_MANAGER = "by_manager"
    BY_SYSTEM = "by_system"

# ========= File Lock and JSON Operations =========
# These functions are now imported from gui_agents.utils.file_utils

# ========= New GlobalState =========
class NewGlobalState:
    """Enhanced global state management for new architecture with role-based access"""

    def __init__(
        self,
        *,
        screenshot_dir: str,
        state_dir: str,
        task_id: Optional[str] = None,
        agent_log_path: str = "",
        display_info_path: str = "",
    ):
        self.screenshot_dir = Path(screenshot_dir)
        self.state_dir = Path(state_dir)
        self.task_id = task_id or f"task-{generate_uuid()[:8]}"
        
        # State file paths
        self.task_path = self.state_dir / "task.json"
        self.subtasks_path = self.state_dir / "subtasks.json"
        self.commands_path = self.state_dir / "commands.json"
        self.gate_checks_path = self.state_dir / "gate_checks.json"
        self.artifacts_path = self.state_dir / "artifacts.md"
        self.supplement_path = self.state_dir / "supplement.md"
        self.events_path = self.state_dir / "events.json"
        
        # Legacy paths for compatibility
        self.agent_log_path = Path(agent_log_path) if agent_log_path else self.state_dir / "agent_log.json"
        self.display_info_path = Path(display_info_path) if display_info_path else self.state_dir / "display.json"
        
        # Ensure necessary directories and files exist
        self._initialize_directories_and_files()

    def _initialize_directories_and_files(self):
        """Initialize directories and create default files"""
        # Create directories
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize state files with default content
        self._init_task_file()
        self._init_subtasks_file()
        self._init_commands_file()
        self._init_gate_checks_file()
        self._init_artifacts_file()
        self._init_supplement_file()
        self._init_events_file()
        
        # Initialize legacy files
        if not self.agent_log_path.exists():
            self.agent_log_path.parent.mkdir(parents=True, exist_ok=True)
            safe_write_text(self.agent_log_path, "[]")
        
        if not self.display_info_path.exists():
            self.display_info_path.parent.mkdir(parents=True, exist_ok=True)
            safe_write_text(self.display_info_path, "{}")

    def _init_task_file(self):
        """Initialize task.json with default content"""
        if not self.task_path.exists():
            default_task = {
                "task_id": self.task_id,
                "created_at": datetime.now().isoformat(),
                "objective": "",
                "status": TaskStatus.CREATED.value,
                "current_subtask_id": None,
                "completed_subtasks": [],
                "pending_subtasks": [],
                "qa_policy": {
                    "per_subtask": True,
                    "final_gate": True,
                    "risky_actions": ["open", "submit", "hotkey"]
                }
            }
            safe_write_json(self.task_path, default_task)

    def _init_subtasks_file(self):
        """Initialize subtasks.json with empty list"""
        if not self.subtasks_path.exists():
            safe_write_text(self.subtasks_path, "[]")

    def _init_commands_file(self):
        """Initialize commands.json with empty list"""
        if not self.commands_path.exists():
            safe_write_text(self.commands_path, "[]")

    def _init_gate_checks_file(self):
        """Initialize gate_checks.json with empty list"""
        if not self.gate_checks_path.exists():
            safe_write_text(self.gate_checks_path, "[]")

    def _init_artifacts_file(self):
        """Initialize artifacts.md with header"""
        if not self.artifacts_path.exists():
            default_content = f"""# Task Artifacts - {self.task_id}

## Overview
This file contains reusable artifacts for the current task.

## Artifacts
"""
            safe_write_text(self.artifacts_path, default_content)

    def _init_supplement_file(self):
        """Initialize supplement.md with header"""
        if not self.supplement_path.exists():
            default_content = f"""# Task Supplement - {self.task_id}

## Overview
This file tracks supplementary information and materials needed for the task.

## Supplements
"""
            safe_write_text(self.supplement_path, default_content)

    def _init_events_file(self):
        """Initialize events.json with empty list"""
        if not self.events_path.exists():
            safe_write_text(self.events_path, "[]")

    # ========= Utility Methods =========
    # _safe_write_json and _safe_read_json methods removed - now using safe_write_json and safe_read_json from file_utils

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID with prefix"""
        return f"{prefix}-{generate_uuid()[:4]}"

    # ========= Screenshot Management =========
    def get_screenshot(self) -> Optional[bytes]:
        """Get latest screenshot as bytes"""
        pngs = sorted(self.screenshot_dir.glob("*.png"))
        if not pngs:
            logger.warning("No screenshot found in %s", self.screenshot_dir)
            return None
        latest = pngs[-1]
        screenshot = Image.open(latest)
        buf = io.BytesIO()
        screenshot.save(buf, format="PNG")
        return buf.getvalue()

    def set_screenshot(self, img: Image.Image) -> str:
        """Save screenshot and return screenshot ID"""
        ts = int(time.time() * 1000)
        screenshot_id = f"shot-{ts:06d}"
        out = self.screenshot_dir / f"{screenshot_id}.png"
        img.save(out)
        logger.debug("Screenshot saved to %s", out)
        return screenshot_id

    def get_screen_size(self) -> List[int]:
        """Get current screen size from latest screenshot"""
        pngs = sorted(self.screenshot_dir.glob("*.png"))
        if not pngs:
            logger.warning("No screenshot found, returning default size [1920, 1080]")
            return [1920, 1080]

        latest = pngs[-1]
        try:
            screenshot = Image.open(latest)
            width, height = screenshot.size
            logger.info("Current screen size: [%d, %d]", width, height)
            return [width, height]
        except Exception as e:
            logger.error("Failed to get screen size: %s", e)
            return [1920, 1080]

    # ========= Task Management =========
    def get_task(self) -> Dict[str, Any]:
        """Get current task information"""
        return safe_read_json(self.task_path, {})

    def set_task(self, task_data: Dict[str, Any]) -> None:
        """Update task information"""
        safe_write_json(self.task_path, task_data)

    def update_task_status(self, status: TaskStatus) -> None:
        """Update task status"""
        task = self.get_task()
        task["status"] = status.value
        self.set_task(task)

    def set_task_objective(self, objective: str) -> None:
        """Set task objective"""
        task = self.get_task()
        task["objective"] = objective
        self.set_task(task)

    def set_current_subtask_id(self, subtask_id: str) -> None:
        """Set current subtask ID"""
        task = self.get_task()
        task["current_subtask_id"] = subtask_id
        self.set_task(task)

    def add_completed_subtask(self, subtask_id: str) -> None:
        """Add subtask to completed list"""
        task = self.get_task()
        if subtask_id not in task["completed_subtasks"]:
            task["completed_subtasks"].append(subtask_id)
        self.set_task(task)

    def add_pending_subtask(self, subtask_id: str) -> None:
        """Add subtask to pending list"""
        task = self.get_task()
        if subtask_id not in task["pending_subtasks"]:
            task["pending_subtasks"].append(subtask_id)
        self.set_task(task)

    def remove_pending_subtask(self, subtask_id: str) -> None:
        """Remove subtask from pending list"""
        task = self.get_task()
        if subtask_id in task["pending_subtasks"]:
            task["pending_subtasks"].remove(subtask_id)
        self.set_task(task)

    # ========= Subtask Management =========
    def get_subtasks(self) -> List[Dict[str, Any]]:
        """Get all subtasks"""
        return safe_read_json(self.subtasks_path, [])

    def get_subtask(self, subtask_id: str) -> Optional[Dict[str, Any]]:
        """Get specific subtask by ID"""
        subtasks = self.get_subtasks()
        for subtask in subtasks:
            if subtask.get("subtask_id") == subtask_id:
                return subtask
        return None

    def add_subtask(self, subtask_data: Dict[str, Any]) -> str:
        """Add new subtask and return subtask ID"""
        subtasks = self.get_subtasks()
        subtask_id = subtask_data.get("subtask_id") or self._generate_id("subtask")
        subtask_data["subtask_id"] = subtask_id
        subtask_data["task_id"] = self.task_id
        subtask_data["attempt_no"] = subtask_data.get("attempt_no", 1)
        subtask_data["status"] = subtask_data.get("status", SubtaskStatus.READY.value)
        subtask_data["reasons_history"] = subtask_data.get("reasons_history", [])
        subtask_data["command_trace_ids"] = subtask_data.get("command_trace_ids", [])
        subtask_data["gate_check_ids"] = subtask_data.get("gate_check_ids", [])
        
        subtasks.append(subtask_data)
        safe_write_json(self.subtasks_path, subtasks)
        
        # Add to pending list
        self.add_pending_subtask(subtask_id)
        
        return subtask_id

    def update_subtask_status(self, subtask_id: str, status: SubtaskStatus, reason: Optional[str] = None) -> None:
        """Update subtask status and optionally add reason"""
        subtasks = self.get_subtasks()
        for subtask in subtasks:
            if subtask.get("subtask_id") == subtask_id:
                subtask["status"] = status.value
                if reason:
                    reason_entry = {
                        "at": datetime.now().isoformat(),
                        "text": reason
                    }
                    subtask["reasons_history"].append(reason_entry)
                    subtask["last_reason_text"] = reason
                break
        
        safe_write_json(self.subtasks_path, subtasks)

    def add_subtask_reason(self, subtask_id: str, reason: str) -> None:
        """Add reason to subtask history"""
        subtasks = self.get_subtasks()
        for subtask in subtasks:
            if subtask.get("subtask_id") == subtask_id:
                reason_entry = {
                    "at": datetime.now().isoformat(),
                    "text": reason
                }
                subtask["reasons_history"].append(reason_entry)
                subtask["last_reason_text"] = reason
                break
        
        safe_write_json(self.subtasks_path, subtasks)

    def add_subtask_command_trace(self, subtask_id: str, command_id: str) -> None:
        """Add command ID to subtask trace"""
        subtasks = self.get_subtasks()
        for subtask in subtasks:
            if subtask.get("subtask_id") == subtask_id:
                if command_id not in subtask["command_trace_ids"]:
                    subtask["command_trace_ids"].append(command_id)
                break
        
        safe_write_json(self.subtasks_path, subtasks)

    def add_subtask_gate_check(self, subtask_id: str, gate_check_id: str) -> None:
        """Add gate check ID to subtask"""
        subtasks = self.get_subtasks()
        for subtask in subtasks:
            if subtask.get("subtask_id") == subtask_id:
                if gate_check_id not in subtask["gate_check_ids"]:
                    subtask["gate_check_ids"].append(gate_check_id)
                break
        
        safe_write_json(self.subtasks_path, subtasks)

    def update_subtask_last_gate(self, subtask_id: str, gate_decision: GateDecision) -> None:
        """Update subtask last gate decision"""
        subtasks = self.get_subtasks()
        for subtask in subtasks:
            if subtask.get("subtask_id") == subtask_id:
                subtask["last_gate_decision"] = gate_decision.value
                break
        
        safe_write_json(self.subtasks_path, subtasks)

    # ========= Command Management =========
    def get_commands(self) -> List[Dict[str, Any]]:
        """Get all commands"""
        return safe_read_json(self.commands_path, [])

    def get_command(self, command_id: str) -> Optional[Dict[str, Any]]:
        """Get specific command by ID"""
        commands = self.get_commands()
        for command in commands:
            if command.get("command_id") == command_id:
                return command
        return None

    def add_command(self, command_data: Dict[str, Any]) -> str:
        """Add new command and return command ID"""
        commands = self.get_commands()
        command_id = command_data.get("command_id") or self._generate_id("cmd")
        
        command = {
            "command_id": command_id,
            "task_id": self.task_id,
            "subtask_id": command_data.get("subtask_id"),
            "command": command_data.get("command"),
            "pre_screenshot_id": command_data.get("pre_screenshot_id"),
            "pre_screenshot_analysis": command_data.get("pre_screenshot_analysis", ""),
            "post_screenshot_id": command_data.get("post_screenshot_id"),
            "exec_status": command_data.get("exec_status", ExecStatus.EXECUTED.value),
            "exec_message": command_data.get("exec_message", "OK"),
            "exec_latency_ms": command_data.get("exec_latency_ms", 0),
            "created_at": command_data.get("created_at", datetime.now().isoformat()),
            "executed_at": command_data.get("executed_at", datetime.now().isoformat())
        }
        
        commands.append(command)
        safe_write_json(self.commands_path, commands)
        
        # Add to subtask trace
        if command["subtask_id"]:
            self.add_subtask_command_trace(command["subtask_id"], command_id)
        
        return command_id

    def update_command_exec_status(self, command_id: str, exec_status: ExecStatus, 
                                 exec_message: str = "", exec_latency_ms: int = 0) -> None:
        """Update command execution status"""
        commands = self.get_commands()
        for command in commands:
            if command.get("command_id") == command_id:
                command["exec_status"] = exec_status.value
                command["exec_message"] = exec_message
                command["exec_latency_ms"] = exec_latency_ms
                command["executed_at"] = datetime.now().isoformat()
                break
        
        safe_write_json(self.commands_path, commands)

    # ========= Gate Check Management =========
    def get_gate_checks(self) -> List[Dict[str, Any]]:
        """Get all gate checks"""
        return safe_read_json(self.gate_checks_path, [])

    def get_gate_check(self, gate_check_id: str) -> Optional[Dict[str, Any]]:
        """Get specific gate check by ID"""
        gate_checks = self.get_gate_checks()
        for gate_check in gate_checks:
            if gate_check.get("gate_check_id") == gate_check_id:
                return gate_check
        return None

    def add_gate_check(self, gate_check_data: Dict[str, Any]) -> str:
        """Add new gate check and return gate check ID"""
        gate_checks = self.get_gate_checks()
        gate_check_id = gate_check_data.get("gate_check_id") or self._generate_id("gc")
        
        gate_check = {
            "gate_check_id": gate_check_id,
            "task_id": self.task_id,
            "subtask_id": gate_check_data.get("subtask_id"),
            "trigger": gate_check_data.get("trigger", GateTrigger.BY_SYSTEM.value),
            "decision": gate_check_data.get("decision"),
            "notes": gate_check_data.get("notes", ""),
            "created_at": gate_check_data.get("created_at", datetime.now().isoformat())
        }
        
        gate_checks.append(gate_check)
        safe_write_json(self.gate_checks_path, gate_checks)
        
        # Add to subtask
        if gate_check["subtask_id"]:
            self.add_subtask_gate_check(gate_check["subtask_id"], gate_check_id)
            self.update_subtask_last_gate(gate_check["subtask_id"], GateDecision(gate_check["decision"]))
        
        return gate_check_id

    # ========= Artifacts Management =========
    def get_artifacts(self) -> str:
        """Get artifacts content"""
        return safe_read_text(self.artifacts_path)

    def set_artifacts(self, content: str) -> None:
        """Set artifacts content"""
        safe_write_text(self.artifacts_path, content)

    def add_artifact(self, artifact_type: str, artifact_data: Dict[str, Any]) -> None:
        """Add new artifact to artifacts.md"""
        current_content = self.get_artifacts()
        
        # Add new artifact section
        artifact_id = self._generate_id("art")
        timestamp = datetime.now().isoformat()
        
        new_artifact = f"""
## {artifact_type} - {artifact_id}
- **Created**: {timestamp}
- **Type**: {artifact_type}
- **Data**: {json.dumps(artifact_data, indent=2, ensure_ascii=False)}

---
"""
        
        updated_content = current_content + new_artifact
        self.set_artifacts(updated_content)

    # ========= Supplement Management =========
    def get_supplement(self) -> str:
        """Get supplement content"""
        return safe_read_text(self.supplement_path)

    def set_supplement(self, content: str) -> None:
        """Set supplement content"""
        safe_write_text(self.supplement_path, content)

    def add_supplement_entry(self, entry_type: str, description: str, 
                           sla: Optional[str] = None, status: str = "open") -> None:
        """Add new supplement entry"""
        current_content = self.get_supplement()
        
        entry_id = self._generate_id("sup")
        timestamp = datetime.now().isoformat()
        
        new_entry = f"""
## {entry_type} - {entry_id}
- **Created**: {timestamp}
- **Type**: {entry_type}
- **Description**: {description}
- **SLA**: {sla or "Not specified"}
- **Status**: {status}

---
"""
        
        updated_content = current_content + new_entry
        self.set_supplement(updated_content)

    # ========= Events Management =========
    def get_events(self) -> List[Dict[str, Any]]:
        """Get all events"""
        return safe_read_json(self.events_path, [])

    def add_event(self, actor: str, action: str, details: Optional[str] = None) -> str:
        """Add new event"""
        events = self.get_events()
        event_id = self._generate_id("evt")
        
        event = {
            "event_id": event_id,
            "task_id": self.task_id,
            "actor": actor,
            "action": action,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        
        events.append(event)
        safe_write_json(self.events_path, events)
        
        return event_id

    # ========= Role-based Access Methods =========
    # Controller methods
    def controller_get_task_state(self) -> Dict[str, Any]:
        """Controller: Get current task state for decision making"""
        return {
            "task": self.get_task(),
            "current_subtask": self.get_subtask(self.get_task().get("current_subtask_id", "")),
            "pending_subtasks": self.get_task().get("pending_subtasks", [])
        }

    def controller_switch_phase(self, new_phase: str) -> None:
        """Controller: Switch to new phase"""
        self.add_event("controller", f"phase_switch_to_{new_phase}")

    # Manager methods
    def manager_get_planning_context(self) -> Dict[str, Any]:
        """Manager: Get context needed for planning"""
        return {
            "task": self.get_task(),
            "subtasks": self.get_subtasks(),
            "artifacts": self.get_artifacts(),
            "supplement": self.get_supplement()
        }

    def manager_create_subtask(self, title: str, description: str, 
                             assignee_role: str = "operator") -> str:
        """Manager: Create new subtask"""
        subtask_data = {
            "title": title,
            "description": description,
            "assignee_role": assignee_role
        }
        subtask_id = self.add_subtask(subtask_data)
        self.add_event("manager", "create_subtask", f"Created subtask: {title}")
        return subtask_id

    # Worker methods
    def worker_get_execution_context(self, subtask_id: str) -> Dict[str, Any]:
        """Worker: Get context needed for execution"""
        subtask = self.get_subtask(subtask_id)
        if not subtask:
            return {}
        
        return {
            "subtask": subtask,
            "task": self.get_task(),
            "screenshot": self.get_screenshot(),
            "artifacts": self.get_artifacts()
        }

    def worker_report_result(self, subtask_id: str, result: str, 
                           reason_code: Optional[str] = None) -> None:
        """Worker: Report execution result"""
        if result == "success":
            self.update_subtask_status(subtask_id, SubtaskStatus.FULFILLED)
        elif result == "CANNOT_EXECUTE":
            self.update_subtask_status(subtask_id, SubtaskStatus.REJECTED, reason_code)
        elif result == "STALE_PROGRESS":
            self.update_subtask_status(subtask_id, SubtaskStatus.STALE)
        elif result == "NEED_SUPPLEMENT":
            self.update_subtask_status(subtask_id, SubtaskStatus.PENDING, "Need supplement")
        
        self.add_event("worker", f"report_{result}", f"Subtask {subtask_id}: {result}")

    # Evaluator methods
    def evaluator_get_quality_context(self, subtask_id: str) -> Dict[str, Any]:
        """Evaluator: Get context needed for quality check"""
        subtask = self.get_subtask(subtask_id)
        if not subtask:
            return {}
        
        return {
            "subtask": subtask,
            "commands": [self.get_command(cmd_id) for cmd_id in subtask.get("command_trace_ids", [])],
            "gate_checks": [self.get_gate_check(gc_id) for gc_id in subtask.get("gate_check_ids", [])],
            "screenshot": self.get_screenshot()
        }

    def evaluator_make_decision(self, subtask_id: str, decision: GateDecision, 
                               notes: str, trigger: GateTrigger = GateTrigger.BY_SYSTEM) -> str:
        """Evaluator: Make quality gate decision"""
        gate_check_data = {
            "subtask_id": subtask_id,
            "decision": decision.value,
            "notes": notes,
            "trigger": trigger.value
        }
        
        gate_check_id = self.add_gate_check(gate_check_data)
        self.add_event("evaluator", f"gate_{decision.value}", f"Decision: {decision.value}")
        
        return gate_check_id

    # Hardware methods
    def hardware_execute_command(self, subtask_id: str, action: Dict[str, Any], 
                               pre_screenshot: Image.Image) -> str:
        """Hardware: Execute command and record results"""
        # Save pre-screenshot
        pre_screenshot_id = self.set_screenshot(pre_screenshot)
        
        # Create command entry
        command_data = {
            "subtask_id": subtask_id,
            "command": action,
            "pre_screenshot_id": pre_screenshot_id,
            "pre_screenshot_analysis": "Pre-execution screenshot captured"
        }
        
        command_id = self.add_command(command_data)
        self.add_event("hardware", "execute_command", f"Executed command: {action}")
        
        return command_id

    def hardware_complete_command(self, command_id: str, post_screenshot: Image.Image,
                                exec_status: ExecStatus, exec_message: str = "", 
                                exec_latency_ms: int = 0) -> None:
        """Hardware: Complete command execution"""
        # Save post-screenshot
        post_screenshot_id = self.set_screenshot(post_screenshot)
        
        # Update command with results
        commands = self.get_commands()
        for command in commands:
            if command.get("command_id") == command_id:
                command["post_screenshot_id"] = post_screenshot_id
                command["exec_status"] = exec_status.value
                command["exec_message"] = exec_message
                command["exec_latency_ms"] = exec_latency_ms
                command["executed_at"] = datetime.now().isoformat()
                break
        
        safe_write_json(self.commands_path, commands)
        self.add_event("hardware", "complete_command", f"Completed command: {exec_status.value}")

    # ========= Legacy Compatibility Methods =========
    def get_obs_for_manager(self):
        """Legacy: Get observation for manager"""
        return {
            "screenshot": self.get_screenshot(),
            "task": self.get_task(),
            "current_subtask": self.get_subtask(self.get_task().get("current_subtask_id", ""))
        }

    def get_obs_for_grounding(self):
        """Legacy: Get observation for grounding"""
        return {"screenshot": self.get_screenshot()}

    def get_obs_for_evaluator(self):
        """Legacy: Get observation for evaluator"""
        return {
            "screenshot": self.get_screenshot(),
            "subtasks": self.get_subtasks(),
            "commands": self.get_commands(),
            "gate_checks": self.get_gate_checks()
        }

    def log_operation(self, module: str, operation: str, data: Dict[str, Any]) -> None:
        """Legacy: Log operation (redirects to new event system)"""
        self.add_event(module, operation, str(data))
        
        # Also log to display_info for backward compatibility
        try:
            display_info = safe_read_json(self.display_info_path, {})
            if "operations" not in display_info:
                display_info["operations"] = {}
            if module not in display_info["operations"]:
                display_info["operations"][module] = []
            
            operation_entry = {
                "operation": operation,
                "timestamp": time.time(),
                **data
            }
            display_info["operations"][module].append(operation_entry)
            
            safe_write_json(self.display_info_path, display_info)
        except Exception as e:
            logger.warning(f"Failed to update display_info: {e}") 