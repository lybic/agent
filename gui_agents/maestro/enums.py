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

class TriggerRole(str, Enum):
    """触发角色"""
    CONTROLLER = "controller" # controller
    WORKER_GET_ACTION = "worker_get_action" # Worker
    EVALUATOR_QUALITY_CHECK = "evaluator_quality_check" # Evaluator
    EVALUATOR_FINAL_CHECK = "evaluator_final_check" # Evaluator
    MANAGER_REPLAN = "manager_replan" # Manager
    MANAGER_SUPPLEMENT = "manager_supplement" # Manager
    EXECUTOR_EXECUTE_ACTION = "executor_execute_action" # Executor
    HARDWARE_EXECUTE_ACTION = "hardware_execute_action" # Hardware

class TriggerCode(str, Enum):
    """触发代码枚举"""
    
    # 规则检验相关
    RULE_QUALITY_CHECK_STEPS = "rule_quality_check_steps"           # 距离上次质检过去了5步
    RULE_QUALITY_CHECK_REPEATED_ACTIONS = "rule_quality_check_repeated_actions"  # 相同连续动作高于3次
    RULE_REPLAN_LONG_EXECUTION = "rule_replan_long_execution"       # 一个subtask的执行action过长，超过15次
    
    # 任务状态规则相关
    RULE_MAX_STATE_SWITCHES_REACHED = "rule_max_state_switches_reached"  # 达到最大状态切换次数
    RULE_PLAN_NUMBER_EXCEEDED = "rule_plan_number_exceeded"              # 规划次数超过限制
    RULE_STATE_SWITCH_COUNT_EXCEEDED = "rule_state_switch_count_exceeded"  # 状态切换次数超过50步
    RULE_TASK_COMPLETED = "rule_task_completed"                          # 任务已完成
    
    # 状态处理相关 - INIT状态
    SUBTASK_READY = "subtask_ready" # INIT -> GET_ACTION
    NO_SUBTASKS = "no_subtasks" # INIT -> manager: replan
    INIT_ERROR = "init_error" # INIT -> manager: replan
    
    # 状态处理相关 - GET_ACTION状态
    NO_CURRENT_SUBTASK_ID = "no_current_subtask_id" # worker: get_action | executor: execute_action | evaluator: quality_check -> INIT
    SUBTASK_NOT_FOUND = "subtask_not_found" # worker: get_action | executor: execute_action -> INIT
    WORKER_SUCCESS = "worker_success" # worker: get_action -> evaluator: quality_check
    WORK_CANNOT_EXECUTE = "work_cannot_execute" # worker: get_action -> manager: replan
    WORKER_STALE_PROGRESS = "worker_stale_progress" # worker: get_action -> evaluator: quality_check
    WORKER_SUPPLEMENT = "worker_supplement" # worker: get_action -> manager: supplement
    WORKER_GENERATE_ACTION = "worker_generate_action" # worker: get_action -> executor
    NO_WORKER_DECISION = "no_worker_decision" # worker: get_action -> manager: replan
    GET_ACTION_ERROR = "get_action_error" # worker: get_action -> manager: replan
    
    # 状态处理相关 - EXECUTE_ACTION状态
    EXECUTION_ERROR = "execution_error" # executor: execute_action -> worker: get_action
    COMMAND_COMPLETED = "command_completed" # executor: execute_action -> worker: get_action
    NO_COMMAND = "no_command" # executor: execute_action -> worker: get_action
    
    # 状态处理相关 - QUALITY_CHECK状态
    ALL_SUBTASKS_COMPLETED = "all_subtasks_completed" # evaluator: quality_check -> evaluator: final_check
    QUALITY_CHECK_PASSED = "quality_check_passed" # # evaluator: quality_check -> worker: get_action
    QUALITY_CHECK_FAILED = "quality_check_failed" # evaluator: quality_check -> manager: replan
    QUALITY_CHECK_SUPPLEMENT = "quality_check_supplement" # evaluator: quality_check -> manager: supplement
    QUALITY_CHECK_EXECUTE_ACTION = "quality_check_execute_action" # evaluator: quality_check -> executor: execute_action
    QUALITY_CHECK_ERROR = "quality_check_error" # evaluator: quality_check -> manager: replan

    # 状态处理相关 - PLAN状态
    SUBTASK_READY_AFTER_PLAN = "subtask_ready_after_plan" # manager: replan -> GET_ACTION
    PLAN_ERROR = "plan_error" # manager: replan -> INIT

    # 状态处理相关 - SUPPLEMENT状态
    SUPPLEMENT_COMPLETED = "supplement_completed" # manager: supplement -> manager: replan
    SUPPLEMENT_ERROR = "supplement_error" # manager: supplement -> manager: replan
 
    # 状态处理相关 - FINAL_CHECK状态
    FINAL_CHECK_ERROR = "final_check_error" # evaluator: final_check -> END: Done
    FINAL_CHECK_PENDING = "final_check_pending" # evaluator: final_check -> worker: get_action
    FINAL_CHECK_PASSED = "final_check_passed" # evaluator: final_check -> END: Done
    FINAL_CHECK_FAILED = "final_check_failed" # evaluator: final_check -> manager: replan

    # 错误恢复相关
    UNKNOWN_STATE = "unknown_state" # unknown -> INIT
    ERROR_RECOVERY = "error_recovery" # unknown -> INIT
    