#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from pathlib import Path
from dotenv import load_dotenv

def load_env_variables():
    env_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        return True
    else:
        print(f".env file not found: {env_path}")
        return False
load_env_variables()

def run_all_tests():
    """运行所有单元测试"""
    # 发现当前目录下的所有测试
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover(os.path.dirname(__file__), pattern='test_*.py')
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(test_suite)

def run_specific_test(test_name):
    """运行指定的单元测试
    
    Args:
        test_name: 测试模块名称，例如 'test_manager' 或 'test_worker'
    """
    if not test_name.startswith('test_'):
        test_name = f'test_{test_name}'
    
    # 导入测试模块
    try:
        test_module = __import__(test_name)
    except ImportError:
        print(f"找不到测试模块: {test_name}")
        return
    
    # 运行测试
    test_loader = unittest.TestLoader()
    test_suite = test_loader.loadTestsFromModule(test_module)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(test_suite)

if __name__ == '__main__':
    """
    python -m gui_agents.unit_test.run_tests
    """
    if len(sys.argv) > 1:
        # 运行指定的测试
        run_specific_test(sys.argv[1])
    else:
        # 运行所有测试
        run_all_tests() 