# Central Dispatcher Implementation Plan

## 重构实施计划

### 🎯 目标
将现有的 `agent_normal.py` 重构为基于中央调度系统的新架构，实现智能决策、成本控制和更好的可观测性。

## 实施阶段

### 阶段1：核心框架搭建 (Week 1-2)

#### 1.1 创建 Central Dispatcher 基础结构
**文件**: `lybicguiagents/gui_agents/agents/central_dispatcher.py`

```python
# 需要实现的核心类
class CentralDispatcher:
    """中央调度系统核心类"""
    
class ExecutionStateManager:
    """执行状态管理器"""
    
class DecisionTrigger:
    """决策触发器"""
    
class InformationCoordinator:
    """信息协调器"""
    
class CostController:
    """成本控制器"""
```

#### 1.2 扩展 Global State
**文件**: `lybicguiagents/gui_agents/agents/enhanced_global_state.py`

```python
# 基于现有 GlobalState 的扩展
class EnhancedGlobalState(GlobalState):
    """增强版全局状态管理"""
    
    # 新增方法
    def add_quality_report(self, report: QualityReport) -> None
    def get_quality_reports(self, limit: int = 10) -> List[QualityReport]
    def record_execution_metrics(self, metrics: ExecutionMetrics) -> None
    def get_execution_metrics(self) -> ExecutionMetrics
    def log_module_interaction(self, message: ModuleMessage) -> None
    def get_execution_history(self, limit: int = 20) -> List[Dict]
    def get_recent_actions(self, limit: int = 5) -> List[Dict]
```

#### 1.3 数据结构定义
**文件**: `lybicguiagents/gui_agents/agents/dispatch_types.py`

```python
# 所有相关的数据类型定义
@dataclass
class SituationAssessment: ...

@dataclass  
class ExecutionMetrics: ...

@dataclass
class QualityReport: ...

@dataclass
class QualityCheckContext: ...

# 等等...
```

### 阶段2：质检层实现 (Week 3-4)

#### 2.1 增强 Reflector
**文件**: `lybicguiagents/gui_agents/agents/enhanced_reflector.py`

```python
class EnhancedReflector(Reflector):
    """增强版反思器"""
    
    def comprehensive_check(self, context: QualityCheckContext, config: QualityCheckConfig) -> QualityReport:
        """综合质检"""
        
    def lightweight_progress_check(self, recent_actions: List[Dict]) -> ProgressReport:
        """轻量级进展检查"""
        
    def visual_change_analysis(self, current_screenshot: Image, previous_screenshot: Image) -> VisualChangeReport:
        """视觉变化分析"""
```

#### 2.2 成本控制逻辑
**文件**: `lybicguiagents/gui_agents/agents/cost_control.py`

```python
class CostTracker:
    """成本追踪器"""
    
class QualityCheckConfig:
    """质检配置"""
    
class SmartCheckStrategy:
    """智能检查策略"""
```

### 阶段3：重规划层优化 (Week 5-6)

#### 3.1 增强 Manager
**文件**: `lybicguiagents/gui_agents/agents/enhanced_manager.py`

```python
class EnhancedManager(Manager):
    """增强版管理器"""
    
    def adjust_current_subtask(self, context: ReplanContext) -> List[Node]:
        """轻度调整当前子任务"""
        
    def reorder_subtasks(self, context: ReplanContext) -> List[Node]:
        """中度调整：重排子任务"""
        
    def complete_replan(self, context: ReplanContext) -> List[Node]:
        """重度调整：完全重规划"""
```

#### 3.2 决策规则引擎
**文件**: `lybicguiagents/gui_agents/agents/decision_rules.py`

```python
class TriggerRule:
    """触发规则基类"""
    
class RuleEngine:
    """规则引擎"""
    
# 预定义规则
PREDEFINED_RULES = [
    ConsecutiveFailureRule(),
    RepeatedActionRule(), 
    ExcessiveStepsRule(),
    # ...
]
```

### 阶段4：集成与测试 (Week 7-8)

#### 4.1 新版 Agent 主类
**文件**: `lybicguiagents/gui_agents/agents/agent_dispatched.py`

```python
class AgentDispatchedNormal(UIAgent):
    """基于中央调度的智能代理"""
    
    def __init__(self, ...):
        # 初始化 Central Dispatcher
        self.dispatcher = CentralDispatcher(...)
        
    def predict(self, instruction: str, observation: Dict) -> Tuple[Dict, List[str]]:
        """主预测方法 - 委托给调度器"""
        return self.dispatcher.execute_task_step(instruction, observation)
```

#### 4.2 CLI 应用集成
**文件**: `lybicguiagents/gui_agents/cli_app_v2.py`

```python
# 在现有 cli_app.py 基础上创建新版本
def main():
    # 选择代理类型
    if args.use_dispatcher:
        agent = AgentDispatchedNormal(...)
    else:
        agent = AgentSNormal(...)  # 保持向后兼容
```

## 详细实现规划

### Central Dispatcher 核心实现

```python
class CentralDispatcher:
    def __init__(self, platform: str, tools_dict: Dict, **kwargs):
        # 初始化各组件
        self.global_state = EnhancedGlobalState(...)
        self.manager = EnhancedManager(...)
        self.reflector = EnhancedReflector(...)
        self.worker = Worker(...)
        self.grounding = Grounding(...)
        self.hardware_interface = HardwareInterface(...)
        
        # 核心模块
        self.state_manager = ExecutionStateManager(self.global_state)
        self.decision_trigger = DecisionTrigger(self)
        self.info_coordinator = InformationCoordinator(self.global_state)
        self.cost_controller = CostController()
        
        # 执行状态
        self.current_instruction = ""
        self.execution_metrics = ExecutionMetrics()
        
    def execute_task_step(self, instruction: str, observation: Dict) -> Tuple[Dict, List[str]]:
        """执行一个任务步骤"""
        # 1. 初始化或更新指令
        if instruction != self.current_instruction:
            self._initialize_new_task(instruction)
            
        # 2. 更新观察
        self._update_observation(observation)
        
        # 3. 评估情况
        situation = self.state_manager.assess_current_situation()
        
        # 4. 决策分发
        if situation.needs_replan:
            return self._handle_replan(situation)
        elif situation.needs_quality_check:
            return self._handle_quality_check(situation)
        elif situation.ready_for_execution:
            return self._handle_normal_execution(situation)
        else:
            return self._handle_user_intervention(situation)
            
    def _handle_normal_execution(self, situation: SituationAssessment) -> Tuple[Dict, List[str]]:
        """处理正常执行"""
        # 1. Worker 生成动作
        worker_info = self.worker.generate_next_action(
            Tu=self.current_instruction,
            search_query=self.global_state.get_search_query(),
            subtask=self.global_state.get_current_subtask().name,
            subtask_info=self.global_state.get_current_subtask().info,
            future_tasks=self.global_state.get_remaining_subtasks(),
            done_task=self.global_state.get_completed_subtasks(),
            obs=self.global_state.get_obs_for_manager()
        )
        
        # 2. Grounding 处理
        try:
            self.grounding.assign_coordinates(worker_info["executor_plan"], observation)
            plan_code = self._extract_and_sanitize_code(worker_info["executor_plan"])
            exec_code = eval(plan_code)
        except Exception as e:
            logger.error(f"Grounding error: {e}")
            exec_code = {"type": "Wait", "duration": 1000}
            
        # 3. 记录执行
        self._record_execution_step(worker_info, exec_code)
        
        # 4. 后处理检查
        self._post_execution_check(exec_code)
        
        return worker_info, [exec_code]
        
    def _handle_quality_check(self, situation: SituationAssessment) -> Tuple[Dict, List[str]]:
        """处理质检"""
        # 1. 配置质检
        check_config = self.cost_controller.optimize_quality_check(situation.check_reason)
        
        # 2. 执行质检
        context = QualityCheckContext(
            recent_actions=self.global_state.get_recent_actions(5),
            current_screenshot=self.global_state.get_screenshot(),
            subtask_goal=self.global_state.get_current_subtask(),
            execution_history=self.global_state.get_execution_history(10)
        )
        
        quality_report = self.reflector.comprehensive_check(context, check_config)
        
        # 3. 处理质检结果
        self.global_state.add_quality_report(quality_report)
        
        if quality_report.recommendation == "REPLAN":
            # 触发重规划
            situation.needs_replan = True
            situation.replan_reason = f"quality_check_{quality_report.status}"
            return self._handle_replan(situation)
        elif quality_report.recommendation == "ADJUST":
            # 轻微调整
            return self._handle_light_adjustment(quality_report)
        else:
            # 继续执行
            situation.ready_for_execution = True
            return self._handle_normal_execution(situation)
            
    def _handle_replan(self, situation: SituationAssessment) -> Tuple[Dict, List[str]]:
        """处理重规划"""
        # 1. 构建重规划上下文
        replan_context = ReplanContext(
            failure_reason=situation.replan_reason,
            failed_subtasks=self.global_state.get_failed_subtasks(),
            completed_subtasks=self.global_state.get_completed_subtasks(),
            remaining_subtasks=self.global_state.get_remaining_subtasks(),
            execution_history=self.global_state.get_execution_history(),
            quality_reports=self.global_state.get_quality_reports()
        )
        
        # 2. 确定重规划策略
        strategy = self._determine_replan_strategy(situation.replan_reason)
        
        # 3. 执行重规划
        if strategy == "LIGHT_ADJUSTMENT":
            new_plan = self.manager.adjust_current_subtask(replan_context)
        elif strategy == "MEDIUM_ADJUSTMENT":
            new_plan = self.manager.reorder_subtasks(replan_context)
        else:  # HEAVY_ADJUSTMENT
            # 调用现有的 get_action_queue 方法
            manager_info, new_plan = self.manager.get_action_queue(
                Tu=self.current_instruction,
                observation=self.global_state.get_obs_for_manager(),
                running_state=self.global_state.get_running_state(),
                failed_subtask=self.global_state.get_latest_failed_subtask(),
                completed_subtasks_list=self.global_state.get_completed_subtasks(),
                remaining_subtasks_list=self.global_state.get_remaining_subtasks()
            )
            
        # 4. 更新状态
        self.global_state.set_remaining_subtasks(new_plan)
        self._reset_execution_state()
        
        # 5. 立即执行第一个子任务
        if new_plan:
            self.global_state.set_current_subtask(new_plan[0])
            self.global_state.set_remaining_subtasks(new_plan[1:])
            
            situation.ready_for_execution = True
            return self._handle_normal_execution(situation)
        else:
            # 没有可执行的任务，结束
            return {}, [{"type": "Done"}]
```

### 增强的 Global State 实现

```python
class EnhancedGlobalState(GlobalState):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 新增路径
        self.quality_reports_path = Path(os.path.join(self.running_state_path.parent, "quality_reports.json"))
        self.execution_metrics_path = Path(os.path.join(self.running_state_path.parent, "execution_metrics.json"))
        self.module_interactions_path = Path(os.path.join(self.running_state_path.parent, "module_interactions.json"))
        
        # 初始化文件
        for path in [self.quality_reports_path, self.execution_metrics_path, self.module_interactions_path]:
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                safe_write_text(path, "[]")
                
    def add_quality_report(self, report: QualityReport) -> None:
        """添加质检报告"""
        reports = self.get_quality_reports()
        reports.append(asdict(report))
        
        tmp = self.quality_reports_path.with_suffix(".tmp")
        try:
            with locked(tmp, "w") as f:
                safe_json_dump(reports, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            tmp.replace(self.quality_reports_path)
        except Exception as e:
            logger.error(f"Failed to add quality report: {e}")
            if tmp.exists():
                tmp.unlink()
            raise
            
    def get_quality_reports(self, limit: int = 10) -> List[Dict]:
        """获取质检报告"""
        try:
            with locked(self.quality_reports_path, "r") as f:
                data = safe_json_load(f)
            return data[-limit:] if isinstance(data, list) else []
        except Exception as e:
            logger.warning(f"Failed to get quality reports: {e}")
            return []
            
    def record_execution_metrics(self, metrics: ExecutionMetrics) -> None:
        """记录执行指标"""
        try:
            with locked(self.execution_metrics_path, "w") as f:
                safe_json_dump(asdict(metrics), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to record execution metrics: {e}")
            
    def get_execution_metrics(self) -> Optional[ExecutionMetrics]:
        """获取执行指标"""
        try:
            with locked(self.execution_metrics_path, "r") as f:
                data = safe_json_load(f)
            return ExecutionMetrics(**data) if isinstance(data, dict) else None
        except Exception as e:
            logger.warning(f"Failed to get execution metrics: {e}")
            return None
            
    def get_execution_history(self, limit: int = 20) -> List[Dict]:
        """获取执行历史"""
        # 基于现有的 agent_log 实现
        agent_log = self.get_agent_log()
        return agent_log[-limit:] if agent_log else []
        
    def get_recent_actions(self, limit: int = 5) -> List[Dict]:
        """获取最近的动作"""
        # 从 actions 中获取最近的动作
        actions = self.get_actions()
        return actions[-limit:] if actions else []
```

## 测试策略

### 单元测试
```python
# tests/test_central_dispatcher.py
class TestCentralDispatcher:
    def test_situation_assessment(self):
        """测试情况评估"""
        
    def test_quality_check_trigger(self):
        """测试质检触发"""
        
    def test_replan_trigger(self):
        """测试重规划触发"""
        
    def test_cost_control(self):
        """测试成本控制"""
```

### 集成测试
```python
# tests/test_integration_dispatcher.py
class TestIntegrationDispatcher:
    def test_full_task_execution(self):
        """测试完整任务执行流程"""
        
    def test_error_recovery(self):
        """测试错误恢复机制"""
        
    def test_performance_comparison(self):
        """测试与原版本的性能对比"""
```

## 向后兼容性

### 渐进式迁移
1. **保留原有 AgentSNormal**: 确保现有代码继续工作
2. **新增 AgentDispatchedNormal**: 提供新的调度版本
3. **CLI 选项**: 通过命令行参数选择使用哪个版本
4. **配置切换**: 通过配置文件控制默认行为

### 配置示例
```python
# config/agent_config.json
{
    "default_agent_type": "dispatched",  # "normal" or "dispatched"
    "dispatcher_config": {
        "enable_quality_check": true,
        "quality_check_interval": 5,
        "cost_control_enabled": true,
        "max_replan_attempts": 3
    },
    "fallback_to_normal": true  # 如果调度版本失败，回退到普通版本
}
```

## 监控和日志

### 性能监控
```python
class PerformanceMonitor:
    def track_execution_time(self, module: str, operation: str, duration: float):
        """追踪执行时间"""
        
    def track_cost(self, module: str, operation: str, cost: float):
        """追踪成本"""
        
    def track_success_rate(self, module: str, success: bool):
        """追踪成功率"""
        
    def generate_report(self) -> Dict:
        """生成性能报告"""
```

### 调试支持
```python
class DispatcherDebugger:
    def log_decision_point(self, situation: SituationAssessment, decision: str):
        """记录决策点"""
        
    def log_quality_check_details(self, context: QualityCheckContext, result: QualityReport):
        """记录质检详情"""
        
    def export_execution_trace(self) -> str:
        """导出执行轨迹"""
```

## 下一步行动

1. **立即开始**: 创建 `central_dispatcher.py` 和 `dispatch_types.py`
2. **并行开发**: 同时进行 GlobalState 扩展和 Reflector 增强
3. **逐步集成**: 每完成一个模块就进行单元测试
4. **性能基准**: 与原版本建立性能对比基准
5. **用户反馈**: 在内部测试中收集使用体验

这个重构将大幅提升系统的智能性、可观测性和可维护性，同时保持良好的向后兼容性。 