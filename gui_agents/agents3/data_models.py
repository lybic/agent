"""
Data Models for Agent System
定义系统中核心数据结构的数据模型
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from .enums import (
    TaskStatus, SubtaskStatus, GateDecision, GateTrigger, 
    ControllerState, ExecStatus
)


# ========= Controller State Data Model =========
@dataclass
class ControllerStateData:
    """控制器状态数据结构"""
    current_state: str = field(default_factory=lambda: ControllerState.GET_ACTION.value)
    trigger: str = field(default="controller")
    trigger_details: str = field(default="initialization")
    history_state: List[str] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "current_state": self.current_state,
            "trigger": self.trigger,
            "trigger_details": self.trigger_details,
            "history_state": self.history_state,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ControllerStateData':
        """从字典创建实例"""
        return cls(
            current_state=data.get("current_state", ControllerState.GET_ACTION.value),
            trigger=data.get("trigger", "controller"),
            trigger_details=data.get("trigger_details", "initialization"),
            history_state=data.get("history_state", []),
            updated_at=data.get("updated_at", datetime.now().isoformat())
        )


# ========= Task Data Model =========
@dataclass
class TaskData:
    """任务数据结构"""
    task_id: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    objective: str = ""
    status: str = field(default_factory=lambda: TaskStatus.CREATED.value)
    current_subtask_id: Optional[str] = None
    history_subtask_ids: List[str] = field(default_factory=list)
    pending_subtask_ids: List[str] = field(default_factory=list)
    qa_policy: Dict[str, Any] = field(default_factory=lambda: {
        "per_subtask": True,
        "final_gate": True,
        "risky_actions": ["open", "submit", "hotkey"]
    })

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "task_id": self.task_id,
            "created_at": self.created_at,
            "objective": self.objective,
            "status": self.status,
            "current_subtask_id": self.current_subtask_id,
            "history_subtask_ids": self.history_subtask_ids,
            "pending_subtask_ids": self.pending_subtask_ids,
            "qa_policy": self.qa_policy
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskData':
        """从字典创建实例"""
        return cls(
            task_id=data["task_id"],
            created_at=data.get("created_at", datetime.now().isoformat()),
            objective=data.get("objective", ""),
            status=data.get("status", TaskStatus.CREATED.value),
            current_subtask_id=data.get("current_subtask_id"),
            history_subtask_ids=data.get("history_subtask_ids", []),
            pending_subtask_ids=data.get("pending_subtask_ids", []),
            qa_policy=data.get("qa_policy", {
                "per_subtask": True,
                "final_gate": True,
                "risky_actions": ["open", "submit", "hotkey"]
            })
        )


# ========= Subtask Data Model =========
@dataclass
class SubtaskData:
    """子任务数据结构"""
    subtask_id: str
    task_id: str
    title: str = ""
    description: str = ""
    assignee_role: str = "operator"
    attempt_no: int = 1
    status: str = field(default_factory=lambda: SubtaskStatus.READY.value)
    reasons_history: List[Dict[str, str]] = field(default_factory=list)
    command_trace_ids: List[str] = field(default_factory=list)
    gate_check_ids: List[str] = field(default_factory=list)
    last_reason_text: Optional[str] = None
    last_gate_decision: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "subtask_id": self.subtask_id,
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "assignee_role": self.assignee_role,
            "attempt_no": self.attempt_no,
            "status": self.status,
            "reasons_history": self.reasons_history,
            "command_trace_ids": self.command_trace_ids,
            "gate_check_ids": self.gate_check_ids,
            "last_reason_text": self.last_reason_text,
            "last_gate_decision": self.last_gate_decision,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SubtaskData':
        """从字典创建实例"""
        return cls(
            subtask_id=data["subtask_id"],
            task_id=data["task_id"],
            title=data.get("title", ""),
            description=data.get("description", ""),
            assignee_role=data.get("assignee_role", "operator"),
            attempt_no=data.get("attempt_no", 1),
            status=data.get("status", SubtaskStatus.READY.value),
            reasons_history=data.get("reasons_history", []),
            command_trace_ids=data.get("command_trace_ids", []),
            gate_check_ids=data.get("gate_check_ids", []),
            last_reason_text=data.get("last_reason_text"),
            last_gate_decision=data.get("last_gate_decision"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat())
        )


# ========= Command Data Model =========
@dataclass
class CommandData:
    """命令数据结构"""
    command_id: str
    task_id: str
    subtask_id: Optional[str] = None
    action: Dict[str, Any] = field(default_factory=dict)
    pre_screenshot_id: Optional[str] = None
    pre_screenshot_analysis: str = ""
    post_screenshot_id: Optional[str] = None
    exec_status: str = field(default_factory=lambda: ExecStatus.EXECUTED.value)
    exec_message: str = "OK"
    exec_latency_ms: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    executed_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "command_id": self.command_id,
            "task_id": self.task_id,
            "subtask_id": self.subtask_id,
            "action": self.action,
            "pre_screenshot_id": self.pre_screenshot_id,
            "pre_screenshot_analysis": self.pre_screenshot_analysis,
            "post_screenshot_id": self.post_screenshot_id,
            "exec_status": self.exec_status,
            "exec_message": self.exec_message,
            "exec_latency_ms": self.exec_latency_ms,
            "created_at": self.created_at,
            "executed_at": self.executed_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CommandData':
        """从字典创建实例"""
        return cls(
            command_id=data["command_id"],
            task_id=data["task_id"],
            subtask_id=data.get("subtask_id"),
            action=data.get("action", {}),
            pre_screenshot_id=data.get("pre_screenshot_id"),
            pre_screenshot_analysis=data.get("pre_screenshot_analysis", ""),
            post_screenshot_id=data.get("post_screenshot_id"),
            exec_status=data.get("exec_status", ExecStatus.EXECUTED.value),
            exec_message=data.get("exec_message", "OK"),
            exec_latency_ms=data.get("exec_latency_ms", 0),
            created_at=data.get("created_at", datetime.now().isoformat()),
            executed_at=data.get("executed_at", datetime.now().isoformat())
        )


# ========= Gate Check Data Model =========
@dataclass
class GateCheckData:
    """质检门数据结构"""
    gate_check_id: str
    task_id: str
    subtask_id: Optional[str] = None
    trigger: str = field(default_factory=lambda: GateTrigger.PERIODIC_CHECK.value)
    decision: Optional[str] = None
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "gate_check_id": self.gate_check_id,
            "task_id": self.task_id,
            "subtask_id": self.subtask_id,
            "trigger": self.trigger,
            "decision": self.decision,
            "notes": self.notes,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GateCheckData':
        """从字典创建实例"""
        return cls(
            gate_check_id=data["gate_check_id"],
            task_id=data["task_id"],
            subtask_id=data.get("subtask_id"),
            trigger=data.get("trigger", GateTrigger.PERIODIC_CHECK.value),
            decision=data.get("decision"),
            notes=data.get("notes", ""),
            created_at=data.get("created_at", datetime.now().isoformat())
        )


# ========= Factory Functions =========
def create_task_data(task_id: str, objective: str = "") -> TaskData:
    """创建新的任务数据"""
    return TaskData(
        task_id=task_id,
        objective=objective,
        status=TaskStatus.CREATED.value
    )


def create_subtask_data(subtask_id: str, task_id: str, title: str, description: str, 
                       assignee_role: str = "operator") -> SubtaskData:
    """创建新的子任务数据"""
    return SubtaskData(
        subtask_id=subtask_id,
        task_id=task_id,
        title=title,
        description=description,
        assignee_role=assignee_role,
        status=SubtaskStatus.READY.value
    )


def create_command_data(command_id: str, task_id: str, action: Dict[str, Any], 
                       subtask_id: Optional[str] = None) -> CommandData:
    """创建新的命令数据"""
    return CommandData(
        command_id=command_id,
        task_id=task_id,
        subtask_id=subtask_id,
        action=action,
        exec_status=ExecStatus.EXECUTED.value
    )


def create_gate_check_data(gate_check_id: str, task_id: str, decision: str, 
                          subtask_id: Optional[str] = None, notes: str = "",
                          trigger: str = GateTrigger.PERIODIC_CHECK.value) -> GateCheckData:
    """创建新的质检门数据"""
    return GateCheckData(
        gate_check_id=gate_check_id,
        task_id=task_id,
        subtask_id=subtask_id,
        decision=decision,
        notes=notes,
        trigger=trigger
    )


def create_controller_state_data(state: ControllerState = ControllerState.GET_ACTION,
                               trigger: str = "controller", 
                               trigger_details: str = "initialization") -> ControllerStateData:
    """创建新的控制器状态数据"""
    return ControllerStateData(
        current_state=state.value,
        trigger=trigger,
        trigger_details=trigger_details
    ) 