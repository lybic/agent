"""
Configuration Manager for Agent-S Controller
负责工具配置和知识库设置
"""

import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ConfigManager:
    """配置管理器，负责工具配置和知识库设置"""
    
    def __init__(self, 
        memory_root_path: str = os.getcwd(),
        memory_folder_name: str = "kb_s2",
        kb_release_tag: str = "v0.2.2",
    ):
        self.memory_root_path = memory_root_path
        self.memory_folder_name = memory_folder_name
        self.tools_config = {}
        self.tools_dict = {}
        self.flow_config: Dict[str, Any] = {}
        
    def load_tools_configuration(self) -> Dict[str, Any]:
        """从配置文件加载工具配置"""
        try:
            tools_config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                "tools", "new_tools_config.json"
            )
            
            with open(tools_config_path, "r") as f:
                self.tools_config = json.load(f)
                logger.info(f"Loaded tools configuration from: {tools_config_path}")
                
                # 构建工具字典，保留所有配置字段
                for tool in self.tools_config["tools"]:
                    tool_name = tool["tool_name"]
                    # 复制所有配置字段，不仅仅是 provider 和 model
                    self.tools_dict[tool_name] = tool.copy()
                    # 确保 model 字段存在（从 model_name 映射）
                    if "model_name" in tool:
                        self.tools_dict[tool_name]["model"] = tool["model_name"]
                    
                logger.debug(f"Tools configuration loaded: {len(self.tools_dict)} tools")
                return self.tools_dict
                
        except Exception as e:
            logger.error(f"Failed to load tools configuration: {e}")
            return {}
    
    def setup_knowledge_base(self, platform: str) -> str:
        """初始化代理的知识库路径并检查是否存在"""
        try:
            # 初始化代理的知识库路径
            local_kb_path = os.path.join(self.memory_root_path, self.memory_folder_name)
            
            # 检查知识库是否存在
            kb_platform_path = os.path.join(local_kb_path, platform)
            if not os.path.exists(kb_platform_path):
                logger.warning(f"Knowledge base for {platform} platform not found in {local_kb_path}")
                os.makedirs(kb_platform_path, exist_ok=True)
                logger.info(f"Created directory: {kb_platform_path}")
            else:
                logger.info(f"Found local knowledge base path: {kb_platform_path}")
                
            return local_kb_path
            
        except Exception as e:
            logger.error(f"Failed to setup knowledge base: {e}")
            return self.memory_root_path
    
    def get_tools_dict(self) -> Dict[str, Any]:
        """获取工具字典"""
        return self.tools_dict
    
    def get_tools_config(self) -> Dict[str, Any]:
        """获取工具配置"""
        return self.tools_config
    
    # ===== 新增：流程配置集中管理 =====
    def load_flow_configuration(self) -> Dict[str, Any]:
        """加载流程配置（目前以内置默认为主，可后续扩展为文件/环境变量）。"""
        try:
            # 统一的默认阈值配置
            self.flow_config = {
                # 任务与状态
                "max_steps": 50,
                "max_state_switches": 100,
                "max_state_duration_secs": 300,
                # 质检相关
                "quality_check_interval_secs": 300,  # 距离上次质检的时间间隔
                "first_quality_check_min_commands": 5,  # 首次质检触发指令数
                # 连续相同行为与重规划
                "repeated_action_min_consecutive": 3,
                "replan_long_execution_threshold": 25,
                # 规划次数上限
                "plan_number_limit": 10,
                # 快照与主循环
                "enable_snapshots": True,
                "snapshot_interval_steps": 10,
                "create_checkpoint_snapshots": True,
                "main_loop_sleep_secs": 0.1,
            }
        except Exception as e:
            logger.error(f"Failed to load flow configuration: {e}")
            # 兜底：至少提供一个空字典
            self.flow_config = {}
        return self.flow_config
    
    def get_flow_config(self) -> Dict[str, Any]:
        """获取流程配置（如未加载则按默认加载）。"""
        if not self.flow_config:
            return self.load_flow_configuration()
        return self.flow_config 