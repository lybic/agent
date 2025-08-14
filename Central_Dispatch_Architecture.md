# Central Dispatch Architecture - GUI Agent Refactoring

## 概述

本文档描述了GUI Agent系统的重构方案，引入中央调度系统（Central Dispatcher）作为核心协调组件，实现分层决策机制和智能成本控制。

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    Central Dispatcher                       │
│  ┌─────────────────┬─────────────────┬─────────────────┐   │
│  │   状态管理       │   决策触发       │   信息协调       │   │
│  │                │                │                │   │
│  │ • 任务进度      │ • 重规划时机     │ • 模块数据传递   │   │
│  │ • 子任务队列    │ • 质检触发       │ • 执行日志管理   │   │
│  │ • 执行历史      │ • 完成/失败判断  │ • 状态变化通知   │   │
│  │ • 失败/成功统计 │ • 用户介入时机   │                │   │
│  └─────────────────┴─────────────────┴─────────────────┘   │
└─────────────────────────────────────────────────────────────┘
              │                    │                    │
              ▼                    ▼                    ▼
    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
    │     Manager     │  │   Reflector     │  │     Worker      │
    │   (规划层)       │  │   (质检层)       │  │   (执行层)       │
    └─────────────────┘  └─────────────────┘  └─────────────────┘
              │                    │                    │
              └──────────────┬─────────────────────────┘
                            ▼
                   ┌─────────────────┐
                   │  Global State   │
                   │   (数据中台)     │
                   └─────────────────┘
```

## 分层决策机制

### 🚀 实时层（每步执行后）
**责任者**: Central Dispatcher  
**触发频率**: 每个Worker动作执行后  
**成本**: 极低（基于规则）

#### 检查项目
1. **动作记录与统计**
   - 记录动作到执行历史
   - 更新步数计数器
   - 统计成功/失败次数

2. **异常模式检测**
   ```python
   # 连续相同动作检测
   if last_3_actions_identical():
       trigger_quality_check("REPEATED_ACTION")
   
   # 单个子任务步数过多
   if current_subtask_steps > 10:
       trigger_quality_check("EXCESSIVE_STEPS")
   
   # 错误动作检测
   if action_type == "fail":
       trigger_manager_replan("WORKER_FAIL")
   
   # 完成动作验证
   if action_type == "done":
       verify_task_completion()
   ```

3. **决策输出**
   - `CONTINUE`: 继续正常执行
   - `QUALITY_CHECK`: 触发质检层
   - `REPLAN`: 触发Manager重规划
   - `USER_INTERVENTION`: 请求用户介入

### 🔍 质检层（周期性触发）
**责任者**: Reflector + Central Dispatcher  
**触发频率**: 按需（异常时）或周期性（每5步）  
**成本**: 中等（轻量级LLM调用）

#### 触发条件
```python
class QualityCheckTrigger:
    PERIODIC = "every_5_steps"           # 周期性检查
    REPEATED_ACTION = "action_loop"      # 动作重复
    EXCESSIVE_STEPS = "too_many_steps"   # 步数过多
    NO_PROGRESS = "ui_unchanged"         # 界面无变化
    WORKER_CONFUSED = "worker_stuck"     # Worker报告困难
    TIME_EXCEEDED = "subtask_timeout"    # 子任务超时
```

#### 质检内容
1. **视觉对比分析**
   ```python
   def visual_progress_check():
       current_screenshot = global_state.get_screenshot()
       previous_screenshot = global_state.get_previous_screenshot()
       
       # 使用轻量级视觉模型
       ui_change_score = lightweight_vision_model.compare(
           current_screenshot, previous_screenshot
       )
       
       return {
           "ui_changed": ui_change_score > 0.1,
           "progress_direction": analyze_progress_direction(),
           "confidence": ui_change_score
       }
   ```

2. **进展分析**
   ```python
   def progress_analysis():
       recent_actions = global_state.get_recent_actions(5)
       subtask_goal = global_state.get_current_subtask().info
       
       return reflector.analyze_progress(
           recent_actions=recent_actions,
           goal=subtask_goal,
           screenshot=global_state.get_screenshot()
       )
   ```

3. **效率评估**
   - 操作合理性检查
   - 时间效率评估
   - 错误率统计

#### 质检输出
```python
@dataclass
class QualityReport:
    status: Literal["GOOD", "CONCERNING", "CRITICAL"]
    recommendation: Literal["CONTINUE", "ADJUST", "REPLAN"]
    confidence: float
    issues: List[str]
    suggestions: List[str]
    cost_estimate: float
```

### 🎯 规划层（按需触发）
**责任者**: Manager  
**触发频率**: 按需  
**成本**: 高（完整LLM规划）

#### 重规划触发条件
```python
class ReplanTrigger:
    REFLECTOR_RECOMMENDATION = "quality_check_failed"
    WORKER_CONSECUTIVE_FAIL = "multiple_failures" 
    SUBTASK_TIMEOUT = "time_exceeded"
    UNHANDLEABLE_ERROR = "critical_error"
    USER_REQUEST = "manual_trigger"
    CONTEXT_CHANGED = "environment_shift"
```

#### 重规划策略
```python
class ReplanStrategy:
    LIGHT_ADJUSTMENT = {
        "scope": "current_subtask",
        "action": "modify_parameters",
        "cost": "low"
    }
    
    MEDIUM_ADJUSTMENT = {
        "scope": "subtask_sequence", 
        "action": "reorder_tasks",
        "cost": "medium"
    }
    
    HEAVY_ADJUSTMENT = {
        "scope": "entire_plan",
        "action": "complete_redecomposition", 
        "cost": "high"
    }
    
    ESCALATION = {
        "scope": "user_intervention",
        "action": "request_help",
        "cost": "variable"
    }
```

## Central Dispatcher 详细设计

### 核心类定义
```python
class CentralDispatcher:
    def __init__(self):
        self.global_state = GlobalState()
        self.manager = Manager()
        self.reflector = Reflector()
        self.worker = Worker()
        self.hardware_interface = HardwareInterface()
        
        # 状态管理
        self.current_phase = "INITIALIZATION"
        self.step_counter = 0
        self.subtask_step_counter = 0
        self.failure_count = 0
        
        # 决策历史
        self.decision_history = []
        self.quality_reports = []
        
        # 成本控制
        self.cost_tracker = CostTracker()
        
    def main_execution_loop(self, instruction: str) -> bool:
        """主执行循环"""
        self.global_state.set_Tu(instruction)
        
        while not self.is_task_completed():
            # 1. 评估当前状况
            situation = self.assess_current_situation()
            
            # 2. 根据情况决定行动
            if situation == "NEED_REPLAN":
                self.trigger_manager_replan()
            elif situation == "NEED_QUALITY_CHECK":
                self.trigger_quality_check()
            elif situation == "READY_FOR_EXECUTION":
                self.execute_worker_action()
            else:  # USER_INTERVENTION_NEEDED
                self.request_user_intervention()
                
            # 3. 后处理检查
            self.post_action_analysis()
            
            # 4. 更新状态
            self.update_execution_state()
            
        return self.global_state.get_termination_flag() == "terminated"
```

### 状态管理模块
```python
class ExecutionStateManager:
    def __init__(self, global_state: GlobalState):
        self.global_state = global_state
        self.metrics = ExecutionMetrics()
        
    def assess_current_situation(self) -> SituationAssessment:
        """评估当前执行情况"""
        return SituationAssessment(
            needs_replan=self._check_replan_conditions(),
            needs_quality_check=self._check_quality_conditions(),
            ready_for_execution=self._check_execution_readiness(),
            user_intervention_needed=self._check_intervention_conditions()
        )
        
    def _check_replan_conditions(self) -> bool:
        """检查是否需要重新规划"""
        conditions = [
            self.metrics.consecutive_failures >= 3,
            self.metrics.subtask_duration > MAX_SUBTASK_TIME,
            self.global_state.get_latest_quality_report().recommendation == "REPLAN",
            self.metrics.no_progress_steps >= 5
        ]
        return any(conditions)
        
    def _check_quality_conditions(self) -> bool:
        """检查是否需要质检"""
        conditions = [
            self.metrics.steps_since_last_check >= 5,
            self.metrics.repeated_action_count >= 3,
            self.metrics.ui_unchanged_steps >= 3,
            self.metrics.error_rate > 0.5
        ]
        return any(conditions)
```

### 决策触发模块
```python
class DecisionTrigger:
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.trigger_rules = self._load_trigger_rules()
        
    def evaluate_triggers(self, context: ExecutionContext) -> List[TriggerEvent]:
        """评估所有触发条件"""
        triggered_events = []
        
        for rule in self.trigger_rules:
            if rule.evaluate(context):
                triggered_events.append(
                    TriggerEvent(
                        type=rule.trigger_type,
                        priority=rule.priority,
                        reason=rule.reason,
                        confidence=rule.confidence
                    )
                )
                
        return sorted(triggered_events, key=lambda x: x.priority, reverse=True)
        
    def _load_trigger_rules(self) -> List[TriggerRule]:
        """加载触发规则"""
        return [
            TriggerRule(
                name="consecutive_failures",
                condition=lambda ctx: ctx.consecutive_failures >= 3,
                trigger_type="REPLAN",
                priority=10,
                reason="连续失败次数过多"
            ),
            TriggerRule(
                name="repeated_actions",
                condition=lambda ctx: ctx.repeated_action_count >= 3,
                trigger_type="QUALITY_CHECK", 
                priority=8,
                reason="检测到重复动作"
            ),
            # ... 更多规则
        ]
```

### 信息协调模块
```python
class InformationCoordinator:
    def __init__(self, global_state: GlobalState):
        self.global_state = global_state
        self.message_bus = MessageBus()
        
    def coordinate_module_interaction(self, source: str, target: str, data: Dict):
        """协调模块间交互"""
        message = ModuleMessage(
            source=source,
            target=target,
            data=data,
            timestamp=time.time()
        )
        
        # 记录交互日志
        self.global_state.log_module_interaction(message)
        
        # 转发消息
        return self.message_bus.send(message)
        
    def broadcast_state_change(self, change_type: str, data: Dict):
        """广播状态变化"""
        notification = StateChangeNotification(
            change_type=change_type,
            data=data,
            timestamp=time.time()
        )
        
        self.message_bus.broadcast(notification)
```

## 成本控制策略

### 三层成本控制
```python
class CostController:
    def __init__(self):
        self.budgets = {
            "low_cost": {"limit": 0.01, "operations": ["rule_check", "simple_detection"]},
            "medium_cost": {"limit": 0.10, "operations": ["light_vision", "progress_check"]}, 
            "high_cost": {"limit": 1.00, "operations": ["full_replan", "deep_analysis"]}
        }
        
    def can_afford_operation(self, operation_type: str, estimated_cost: float) -> bool:
        """检查是否能承担操作成本"""
        for tier, config in self.budgets.items():
            if operation_type in config["operations"]:
                return estimated_cost <= config["limit"]
        return False
        
    def optimize_quality_check(self, trigger_reason: str) -> QualityCheckConfig:
        """根据触发原因优化质检配置"""
        if trigger_reason == "PERIODIC":
            return QualityCheckConfig(
                use_lightweight_model=True,
                screenshot_analysis=True,
                deep_reasoning=False,
                estimated_cost=0.02
            )
        elif trigger_reason == "CRITICAL_ERROR":
            return QualityCheckConfig(
                use_lightweight_model=False,
                screenshot_analysis=True, 
                deep_reasoning=True,
                estimated_cost=0.15
            )
```

### 智能检查策略
```python
class SmartCheckStrategy:
    LOW_COST_CHECKS = [
        "action_repetition_detection",
        "execution_time_monitoring", 
        "screenshot_hash_comparison",
        "keyword_matching"
    ]
    
    MEDIUM_COST_CHECKS = [
        "lightweight_visual_analysis",
        "ui_element_detection",
        "progress_direction_analysis",
        "error_dialog_detection"
    ]
    
    HIGH_COST_CHECKS = [
        "deep_task_progress_evaluation",
        "complex_ui_understanding",
        "comprehensive_error_diagnosis",
        "strategy_adjustment_recommendation"
    ]
    
    def select_appropriate_checks(self, context: ExecutionContext) -> List[str]:
        """根据上下文选择合适的检查"""
        selected_checks = self.LOW_COST_CHECKS.copy()
        
        if context.error_rate > 0.3:
            selected_checks.extend(self.MEDIUM_COST_CHECKS)
            
        if context.critical_failure or context.user_requested_deep_analysis:
            selected_checks.extend(self.HIGH_COST_CHECKS)
            
        return selected_checks
```

## 执行流程伪代码

### 主循环
```python
def main_execution_loop(instruction: str) -> bool:
    dispatcher = CentralDispatcher()
    
    # 初始化
    dispatcher.initialize_task(instruction)
    
    while not dispatcher.is_task_completed() and within_step_limit():
        # 1. 状态评估
        situation = dispatcher.assess_current_situation()
        
        # 2. 决策分发
        if situation.needs_replan:
            dispatcher.trigger_manager_replan(situation.replan_reason)
            
        elif situation.needs_quality_check:
            quality_report = dispatcher.trigger_quality_check(situation.check_reason)
            dispatcher.process_quality_report(quality_report)
            
        elif situation.ready_for_execution:
            # 3. 正常执行Worker动作
            worker_action = dispatcher.worker.generate_next_action()
            execution_result = dispatcher.hardware.execute(worker_action)
            dispatcher.record_execution(worker_action, execution_result)
            
            # 4. 后处理检查
            dispatcher.post_action_check(execution_result)
            
        else:
            dispatcher.request_user_intervention(situation.intervention_reason)
            
        # 5. 状态更新
        dispatcher.update_execution_state()
        
    return dispatcher.get_final_result()
```

### 质检触发流程
```python
def trigger_quality_check(self, reason: str) -> QualityReport:
    # 1. 成本评估
    check_config = self.cost_controller.optimize_quality_check(reason)
    
    if not self.cost_controller.can_afford_operation("quality_check", check_config.estimated_cost):
        return self._fallback_rule_based_check()
    
    # 2. 执行质检
    context = QualityCheckContext(
        recent_actions=self.global_state.get_recent_actions(5),
        current_screenshot=self.global_state.get_screenshot(),
        subtask_goal=self.global_state.get_current_subtask(),
        execution_history=self.global_state.get_execution_history()
    )
    
    quality_report = self.reflector.comprehensive_check(context, check_config)
    
    # 3. 记录结果
    self.global_state.add_quality_report(quality_report)
    
    return quality_report
```

### Manager重规划流程
```python
def trigger_manager_replan(self, reason: str) -> bool:
    # 1. 收集重规划上下文
    replan_context = ReplanContext(
        failure_reason=reason,
        failed_subtasks=self.global_state.get_failed_subtasks(),
        completed_subtasks=self.global_state.get_completed_subtasks(),
        remaining_subtasks=self.global_state.get_remaining_subtasks(),
        execution_history=self.global_state.get_execution_history(),
        quality_reports=self.global_state.get_quality_reports()
    )
    
    # 2. 确定重规划策略
    strategy = self._determine_replan_strategy(reason)
    
    # 3. 执行重规划
    if strategy == ReplanStrategy.LIGHT_ADJUSTMENT:
        new_plan = self.manager.adjust_current_subtask(replan_context)
    elif strategy == ReplanStrategy.MEDIUM_ADJUSTMENT:
        new_plan = self.manager.reorder_subtasks(replan_context)
    else:  # HEAVY_ADJUSTMENT
        new_plan = self.manager.complete_replan(replan_context)
    
    # 4. 更新状态
    self.global_state.set_remaining_subtasks(new_plan)
    self.reset_executor_state()
    
    return True
```

## 模块接口定义

### Central Dispatcher接口
```python
class ICentralDispatcher(ABC):
    @abstractmethod
    def assess_current_situation(self) -> SituationAssessment: pass
    
    @abstractmethod
    def trigger_quality_check(self, reason: str) -> QualityReport: pass
    
    @abstractmethod
    def trigger_manager_replan(self, reason: str) -> bool: pass
    
    @abstractmethod
    def execute_worker_action(self) -> ExecutionResult: pass
    
    @abstractmethod
    def post_action_check(self, result: ExecutionResult) -> None: pass
```

### Enhanced Global State接口
```python
class IEnhancedGlobalState(ABC):
    # 现有接口保持不变
    
    # 新增接口
    @abstractmethod
    def add_quality_report(self, report: QualityReport) -> None: pass
    
    @abstractmethod
    def get_quality_reports(self, limit: int = 10) -> List[QualityReport]: pass
    
    @abstractmethod
    def record_execution_metrics(self, metrics: ExecutionMetrics) -> None: pass
    
    @abstractmethod
    def get_execution_metrics(self) -> ExecutionMetrics: pass
    
    @abstractmethod
    def log_module_interaction(self, message: ModuleMessage) -> None: pass
```

### Reflector增强接口
```python
class IEnhancedReflector(ABC):
    @abstractmethod
    def comprehensive_check(self, context: QualityCheckContext, config: QualityCheckConfig) -> QualityReport: pass
    
    @abstractmethod
    def lightweight_progress_check(self, recent_actions: List[Dict]) -> ProgressReport: pass
    
    @abstractmethod
    def visual_change_analysis(self, current_screenshot: Image, previous_screenshot: Image) -> VisualChangeReport: pass
```

## 数据结构定义

### 核心数据结构
```python
@dataclass
class SituationAssessment:
    needs_replan: bool
    needs_quality_check: bool  
    ready_for_execution: bool
    user_intervention_needed: bool
    replan_reason: Optional[str] = None
    check_reason: Optional[str] = None
    intervention_reason: Optional[str] = None

@dataclass
class ExecutionMetrics:
    total_steps: int
    subtask_steps: int
    consecutive_failures: int
    repeated_action_count: int
    ui_unchanged_steps: int
    error_rate: float
    avg_step_duration: float
    cost_spent: float

@dataclass
class QualityCheckContext:
    recent_actions: List[Dict]
    current_screenshot: Image
    subtask_goal: Node
    execution_history: List[Dict]
    
@dataclass 
class QualityReport:
    status: Literal["GOOD", "CONCERNING", "CRITICAL"]
    recommendation: Literal["CONTINUE", "ADJUST", "REPLAN"]
    confidence: float
    issues: List[str]
    suggestions: List[str]
    cost_estimate: float
    timestamp: float
```

## 实施计划

### 阶段1：核心框架搭建
1. 实现 `CentralDispatcher` 基础类
2. 扩展 `GlobalState` 添加新的状态管理功能
3. 创建决策触发规则引擎

### 阶段2：质检层实现
1. 实现轻量级质检策略
2. 集成现有Reflector功能
3. 添加成本控制逻辑

### 阶段3：重规划层优化
1. 优化Manager重规划策略
2. 实现渐进式重规划
3. 添加用户介入机制

### 阶段4：集成测试与优化
1. 端到端测试
2. 性能优化
3. 成本效益分析

## 总结

该架构通过引入中央调度系统，实现了：

1. **智能决策**: 基于规则和AI的分层决策机制
2. **成本控制**: 三层成本控制策略，平衡效果与开销
3. **状态管理**: 统一的状态管理和模块协调
4. **可扩展性**: 模块化设计，易于扩展和维护
5. **可观测性**: 完整的执行历史和质检报告

这种设计既保持了原有系统的功能完整性，又大幅提升了执行效率和智能程度。 