"""
Controller package for Agent-S
包含状态机控制器和相关功能模块
"""

from .config_manager import ConfigManager
from .rule_engine import RuleEngine
from .state_handlers import StateHandlers
from .state_machine import StateMachine
from .main_controller import MainController

# 为了向后兼容，保留NewController别名
NewController = MainController

__all__ = [
    'ConfigManager',
    'RuleEngine',
    'StateHandlers', 
    'StateMachine',
    'MainController',
    'NewController'  # 向后兼容
] 