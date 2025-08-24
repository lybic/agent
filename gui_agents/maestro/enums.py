"""
Controller Enums
集中管理所有控制器相关的枚举值
"""

from enum import Enum

class ControllerState(str, Enum):
    """控制器状态定义"""
    INIT = "INIT"                    # 立项阶段
    GET_ACTION = "GET_ACTION"        # 取下一步动作
    EXECUTE_ACTION = "EXECUTE_ACTION"  # 执行动作阶段
    QUALITY_CHECK = "QUALITY_CHECK"  # 质检门检查
    PLAN = "PLAN"                    # 重规划阶段
    SUPPLEMENT = "SUPPLEMENT"        # 资料补全阶段
    FINAL_CHECK = "FINAL_CHECK"      # 最终质检阶段
    DONE = "DONE"                    # 任务终结，还没想好怎么处理done状态


class SubtaskStatus(str, Enum):
    """子任务状态"""
    PENDING = "pending"      # 执行中
    READY = "ready"          # 准备执行
    FULFILLED = "fulfilled"  # 已完成
    REJECTED = "rejected"    # 被拒绝
    STALE = "stale"          # 过时


class ExecStatus(str, Enum):
    """执行状态"""
    EXECUTED = "executed"    # 已执行
    TIMEOUT = "timeout"      # 超时
    BLOCKED = "blocked"      # 阻塞
    ERROR = "error"          # 错误


class GateDecision(str, Enum):
    """质检门决策"""
    GATE_DONE = "gate_done"           # 质检通过
    GATE_FAIL = "gate_fail"           # 质检失败
    GATE_SUPPLEMENT = "gate_supplement"  # 需要补充资料
    GATE_CONTINUE = "gate_continue"   # 继续执行


class GateTrigger(str, Enum):
    """质检门触发条件"""
    MANUAL = "manual"       # 手动触发
    TIMEOUT = "timeout"     # 超时触发
    ERROR = "error"         # 错误触发
    PERIODIC_CHECK = "periodic_check"  # 定期检查
    WORKER_STALE = "worker_stale"      # Worker过时
    WORKER_SUCCESS = "worker_success"  # Worker成功
    FINAL_CHECK = "final_check"        # 最终检查

class WorkerDecision(str, Enum):
    """Worker决策"""
    WORKER_DONE = "worker_done"           # 子任务完成
    CANNOT_EXECUTE = "worker_fail"           # 子任务失败
    SUPPLEMENT = "worker_supplement"  # 需要补充资料
    STALE_PROGRESS = "worker_stale_progress"   # 需要质检
    GENERATE_ACTION = "worker_generate_action"  # 生成action

class WorkerTrigger(str, Enum):
    """Worker触发条件"""
    MANUAL = "manual"       # 手动触发



class TaskStatus(str, Enum):
    """任务状态"""
    CREATED = "created"      # 已创建
    PENDING = "pending"      # 等待中
    ON_HOLD = "on_hold"     # 暂停中
    FULFILLED = "fulfilled"  # 已完成
    REJECTED = "rejected"    # 被拒绝
    CANCELLED = "cancelled"  # 已取消


class WorkerStatus(str, Enum):
    """Worker状态"""
    IDLE = "idle"           # 空闲
    BUSY = "busy"           # 忙碌
    ERROR = "error"         # 错误
    OFFLINE = "offline"     # 离线


class EvaluatorStatus(str, Enum):
    """Evaluator状态"""
    IDLE = "idle"           # 空闲
    EVALUATING = "evaluating"  # 评估中
    ERROR = "error"         # 错误
    OFFLINE = "offline"     # 离线


class ManagerStatus(str, Enum):
    """Manager状态"""
    IDLE = "idle"           # 空闲
    PLANNING = "planning"   # 规划中
    SUPPLEMENTING = "supplementing"  # 补充资料中
    ERROR = "error"         # 错误
    OFFLINE = "offline"     # 离线


class EventType(str, Enum):
    """事件类型"""
    INFO = "info"           # 信息
    WARNING = "warning"     # 警告
    ERROR = "error"         # 错误
    SUCCESS = "success"     # 成功
    STATE_SWITCH = "state_switch"  # 状态切换
    STATUS_CHANGE = "status_change"  # 状态变化 

class TriggerCode(str, Enum):
    """触发代码枚举"""
    # Hardware相关
    HARDWARE_GET_ACTION = "hardware_get_action"
    
    # Final Check相关
    FINAL_CHECK_GATE_DONE = "final_check_gate_done"
    FINAL_CHECK_GATE_FAIL = "final_check_gate_fail"
    
    # Evaluator相关
    EVALUATOR_GATE_DONE_FINAL_CHECK = "evaluator_gate_done_final_check"
    EVALUATOR_GATE_FAIL_GET_ACTION = "evaluator_gate_fail_get_action"
    EVALUATOR_GATE_SUPPLEMENT = "evaluator_gate_supplement"
    EVALUATOR_GATE_CONTINUE = "evaluator_gate_continue"
    
    # Worker相关
    WORKER_SUCCESS = "worker_success"
    WORK_CANNOT_EXECUTE = "work_cannot_execute"
    WORKER_STALE_PROGRESS = "worker_stale_progress"
    WORKER_GENERATE_ACTION = "worker_generateaction"
    WORKER_SUPPLEMENT = "worker_supplement"
    
    # Manager相关
    MANAGER_GET_ACTION = "manager_get_action"
    MANAGER_REPLAN = "manager_replan"
    
    # 规则检验相关
    RULE_QUALITY_CHECK_STEPS = "rule_quality_check_steps"           # 距离上次质检过去了5步
    RULE_QUALITY_CHECK_REPEATED_ACTIONS = "rule_quality_check_repeated_actions"  # 相同连续动作高于3次
    RULE_REPLAN_LONG_EXECUTION = "rule_replan_long_execution"       # 一个subtask的执行action过长，超过15次