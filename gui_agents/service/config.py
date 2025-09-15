"""Configuration management for Agent Service"""

import os
import json
import platform
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Union
from pathlib import Path
from .exceptions import ConfigurationError, APIKeyError


@dataclass
class LLMConfig:
    """LLM provider configuration"""
    provider: str  # openai, anthropic, zhipu, etc.
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    api_version: Optional[str] = None
    rate_limit: int = -1
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceConfig:
    """Comprehensive service configuration with multi-level API key support"""
    
    # Agent settings
    default_backend: str = 'lybic'
    default_mode: str = 'normal'
    default_max_steps: int = 50
    default_platform: str = field(default_factory=lambda: platform.system().lower())
    
    # Service settings
    max_concurrent_tasks: int = 5
    task_timeout: int = 3600  # 1 hour
    enable_takeover: bool = False
    enable_search: bool = True
    
    # Logging settings
    log_level: str = 'INFO'
    log_dir: str = 'runtime'
    
    # LLM configuration
    llm_config: Optional[LLMConfig] = None
    
    # API Keys - multiple providers support
    api_keys: Dict[str, str] = field(default_factory=dict)
    
    # Backend-specific configurations
    backend_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Environment variable mappings
    env_mapping: Dict[str, str] = field(default_factory=lambda: {
        'AGENT_BACKEND': 'default_backend',
        'AGENT_MODE': 'default_mode', 
        'AGENT_MAX_STEPS': 'default_max_steps',
        'AGENT_LOG_LEVEL': 'log_level',
        'AGENT_LOG_DIR': 'log_dir',
        'AGENT_TASK_TIMEOUT': 'task_timeout',
        'AGENT_ENABLE_TAKEOVER': 'enable_takeover',
        'AGENT_ENABLE_SEARCH': 'enable_search',
        # Lybic specific
        'LYBIC_PRECREATE_SID': 'lybic_sid',
        'LYBIC_API_KEY': 'lybic_api_key',
    })
    
    # Known API key environment variables
    api_key_env_vars: Dict[str, str] = field(default_factory=lambda: {
        'openai': 'OPENAI_API_KEY',
        'anthropic': 'ANTHROPIC_API_KEY',
        'zhipu': 'ZHIPU_API_KEY',
        'gemini': 'GEMINI_API_KEY',
        'groq': 'GROQ_API_KEY',
        'deepseek': 'DEEPSEEK_API_KEY',
        'dashscope': 'DASHSCOPE_API_KEY',
        'azure_openai': 'AZURE_OPENAI_API_KEY',
        'lybic': 'LYBIC_API_KEY',
        'huggingface': 'HF_TOKEN',
        'siliconflow': 'SILICONFLOW_API_KEY',
        'monica': 'MONICA_API_KEY',
        'openrouter': 'OPENROUTER_API_KEY',
    })
    
    @classmethod
    def from_env(cls, config_file: Optional[Union[str, Path]] = None) -> 'ServiceConfig':
        """Create configuration from environment variables and optional config file
        
        Priority order (highest to lowest):
        1. Environment variables
        2. Config file
        3. Default values
        """
        config = cls()
        
        # Load from config file first (lower priority)
        if config_file:
            config = config.load_from_file(config_file)
        
        # Override with environment variables (higher priority)
        config._load_from_env()
        
        return config
    
    def _load_from_env(self):
        """Load configuration from environment variables"""
        # Load general settings
        for env_key, attr_name in self.env_mapping.items():
            if env_key in os.environ:
                value = os.environ[env_key]
                # Type conversion based on attribute type
                if hasattr(self, attr_name):
                    current_value = getattr(self, attr_name)
                    if isinstance(current_value, bool):
                        value = value.lower() in ('true', '1', 'yes', 'on')
                    elif isinstance(current_value, int):
                        try:
                            value = int(value)
                        except ValueError:
                            continue
                    setattr(self, attr_name, value)
        
        # Load API keys from environment
        for provider, env_var in self.api_key_env_vars.items():
            if env_var in os.environ:
                self.api_keys[provider] = os.environ[env_var]
    
    @classmethod
    def load_from_file(cls, config_file: Union[str, Path]) -> 'ServiceConfig':
        """Load configuration from JSON file"""
        config_path = Path(config_file)
        
        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Create config instance
            config = cls()
            
            # Update with file data
            for key, value in data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            return config

        except json.JSONDecodeError as e:
            raise ConfigurationError("Invalid JSON in config file") from e
        except OSError as e:
            raise ConfigurationError("Error loading config file") from e
    
    def save_to_file(self, config_file: Union[str, Path]):
        """Save configuration to JSON file"""
        config_path = Path(config_file)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict, excluding non-serializable fields
        data = {}
        for key, value in self.__dict__.items():
            if not key.startswith('_') and key not in ['env_mapping', 'api_key_env_vars']:
                data[key] = value
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise ConfigurationError(f"Error saving config file: {e}")
    
    def get_api_key(self, provider: str, required: bool = True) -> Optional[str]:
        """Get API key for a provider with fallback chain
        
        Priority:
        1. Direct api_keys dict
        2. Environment variable
        3. None (if not required)
        
        Args:
            provider: Provider name (openai, anthropic, etc.)
            required: Whether to raise error if not found
            
        Returns:
            API key string or None
            
        Raises:
            APIKeyError: If required but not found
        """
        # Check direct api_keys dict first
        if provider in self.api_keys:
            return self.api_keys[provider]
        
        # Check environment variable
        if provider in self.api_key_env_vars:
            env_var = self.api_key_env_vars[provider]
            if env_var in os.environ:
                api_key = os.environ[env_var]
                # Cache it for future use
                self.api_keys[provider] = api_key
                return api_key
        
        # Not found
        if required:
            env_var = self.api_key_env_vars.get(provider, f"{provider.upper()}_API_KEY")
            raise APIKeyError(
                f"API key for '{provider}' not found. "
                f"Please provide it via api_keys parameter or {env_var} environment variable"
            )
        
        return None
    
    def set_api_key(self, provider: str, api_key: str):
        """Set API key for a provider"""
        self.api_keys[provider] = api_key
    
    def get_backend_config(self, backend: str) -> Dict[str, Any]:
        """Get backend-specific configuration"""
        return self.backend_configs.get(backend, {})
    
    def set_backend_config(self, backend: str, config: Dict[str, Any]):
        """Set backend-specific configuration"""
        self.backend_configs[backend] = config
    
    def validate(self):
        """Validate configuration"""
        if self.default_max_steps <= 0:
            raise ConfigurationError("default_max_steps must be positive")
        
        if self.task_timeout <= 0:
            raise ConfigurationError("task_timeout must be positive")
        
        if self.max_concurrent_tasks <= 0:
            raise ConfigurationError("max_concurrent_tasks must be positive")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            key: value for key, value in self.__dict__.items()
            if not key.startswith('_')
        } 