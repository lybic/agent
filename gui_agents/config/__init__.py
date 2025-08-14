"""
Configuration module for GUI Agents dispatcher system.

This module provides configuration management for the central dispatcher,
quality checking, and cost management systems.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

def load_dispatcher_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load dispatcher configuration from JSON file.
    
    Args:
        config_path: Path to configuration file. If None, uses default.
        
    Returns:
        Configuration dictionary
    """
    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), "dispatcher_config.json")
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        raise ValueError(f"Failed to load dispatcher config from {config_path}: {e}")

def load_quality_profiles(profiles_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load quality check profiles from JSON file.
    
    Args:
        profiles_path: Path to profiles file. If None, uses default.
        
    Returns:
        Profiles dictionary
    """
    if profiles_path is None:
        profiles_path = os.path.join(os.path.dirname(__file__), "quality_profiles.json")
    
    try:
        with open(profiles_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        raise ValueError(f"Failed to load quality profiles from {profiles_path}: {e}")

def get_profile_config(profile_name: str, profiles_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get specific quality profile configuration.
    
    Args:
        profile_name: Name of the profile to load
        profiles_path: Path to profiles file. If None, uses default.
        
    Returns:
        Profile configuration dictionary
        
    Raises:
        ValueError: If profile not found
    """
    profiles = load_quality_profiles(profiles_path)
    
    if profile_name not in profiles.get("profiles", {}):
        available = list(profiles.get("profiles", {}).keys())
        raise ValueError(f"Profile '{profile_name}' not found. Available: {available}")
    
    return profiles["profiles"][profile_name]

def save_config(config: Dict[str, Any], config_path: str) -> None:
    """
    Save configuration to JSON file.
    
    Args:
        config: Configuration dictionary to save
        config_path: Path where to save the configuration
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        raise ValueError(f"Failed to save config to {config_path}: {e}")

# Default configuration paths
DEFAULT_DISPATCHER_CONFIG = os.path.join(os.path.dirname(__file__), "dispatcher_config.json")
DEFAULT_QUALITY_PROFILES = os.path.join(os.path.dirname(__file__), "quality_profiles.json")

__all__ = [
    "load_dispatcher_config",
    "load_quality_profiles", 
    "get_profile_config",
    "save_config",
    "DEFAULT_DISPATCHER_CONFIG",
    "DEFAULT_QUALITY_PROFILES"
] 