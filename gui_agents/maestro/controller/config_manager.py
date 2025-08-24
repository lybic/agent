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
                
                # 构建工具字典
                for tool in self.tools_config["tools"]:
                    tool_name = tool["tool_name"]
                    self.tools_dict[tool_name] = {
                        "provider": tool["provider"],
                        "model": tool["model_name"]
                    }
                    
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