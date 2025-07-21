#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import sys
import os

# Add project root directory to Python path
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
    """Run all unit tests"""
    # Discover all tests in the current directory
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover(os.path.dirname(__file__), pattern='test_*.py')
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(test_suite)

def run_specific_test(test_name):
    """Run specified unit tests
    
    Args:
        test_name: Test module name, e.g. 'test_manager' or 'test_worker'
    """
    if not test_name.startswith('test_'):
        test_name = f'test_{test_name}'
    
    # Import test module
    try:
        test_module = __import__(test_name)
    except ImportError:
        print(f"Test module not found: {test_name}")
        return
    
    # Run tests
    test_loader = unittest.TestLoader()
    test_suite = test_loader.loadTestsFromModule(test_module)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(test_suite)

if __name__ == '__main__':
    """
    python -m gui_agents.unit_test.run_tests
    """
    if len(sys.argv) > 1:
        # Run specified tests
        run_specific_test(sys.argv[1])
    else:
        # Run all tests
        run_all_tests() 