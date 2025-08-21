"""
Controller Enums
集中管理所有控制器相关的枚举值
"""

from enum import Enum

class ControllerPhase(str, Enum):
    """控制器相位定义"""
    INIT = "INIT"                     # 立项阶段
    GET_ACTION = "GET_ACTION"         # 取下一步动作
    EXECUTE_ACTION = "EXECUTE_ACTION" # 执行动作阶段
    QUALITY_CHECK = "QUALITY_CHECK"   # 质检门检查
    PLAN = "PLAN"                     # 重规划阶段
    SUPPLEMENT = "SUPPLEMENT"         # 资料补全阶段
    DONE = "DONE"                     # 任务终结


class ControllerSituation(str, Enum):
    """控制器状态定义 - 与ControllerPhase保持一致"""
    INIT = "INIT"                     # 立项阶段
    GET_ACTION = "GET_ACTION"         # 取下一步动作
    EXECUTE_ACTION = "EXECUTE_ACTION" # 执行动作阶段
    QUALITY_CHECK = "QUALITY_CHECK"   # 质检门检查
    PLAN = "PLAN"                     # 重规划阶段
    SUPPLEMENT = "SUPPLEMENT"         # 资料补全阶段
    DONE = "DONE"                     # 任务终结


class SubtaskStatus(str, Enum):
    """子任务状态"""
    PENDING = "pending"      # 等待中
    READY = "ready"          # 准备执行
    RUNNING = "running"      # 执行中
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
    GATE_PENDING = "gate_pending"     # 质检中
    GATE_CONTINUE = "gate_continue"   # 继续执行


class GateTrigger(str, Enum):
    """质检门触发条件"""
    AUTO = "auto"           # 自动触发
    MANUAL = "manual"       # 手动触发
    TIMEOUT = "timeout"     # 超时触发
    ERROR = "error"         # 错误触发
    PERIODIC_CHECK = "periodic_check"  # 定期检查
    WORKER_STALE = "worker_stale"      # Worker过时
    WORKER_SUCCESS = "worker_success"  # Worker成功
    FINAL_CHECK = "final_check"  # 最终任务验证


class TaskStatus(str, Enum):
    """任务状态"""
    CREATED = "created"      # 已创建
    PENDING = "pending"      # 等待中
    ON_HOLD = "on_hold"     # 暂停中
    RUNNING = "running"      # 执行中
    FULFILLED = "fulfilled"  # 已完成
    REJECTED = "rejected"    # 被拒绝
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
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
    PHASE_SWITCH = "phase_switch"  # 相位切换
    STATUS_CHANGE = "status_change"  # 状态变化
