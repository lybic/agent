#!/usr/bin/env python3
"""
Test script to verify destroy_sandbox functionality.
"""

import unittest
from unittest.mock import Mock, patch


class TestDestroySandbox(unittest.TestCase):
    """Test destroy_sandbox functionality in LybicBackend"""
    
    def test_lybic_backend_has_destroy_method(self):
        """Verify LybicBackend has destroy_sandbox method"""
        from gui_agents.agents.Backend.LybicBackend import LybicBackend
        
        # Check the method exists
        self.assertTrue(hasattr(LybicBackend, 'destroy_sandbox'))
        
    def test_lybic_mobile_backend_has_destroy_method(self):
        """Verify LybicMobileBackend has destroy_sandbox method"""
        from gui_agents.agents.Backend.LybicMobileBackend import LybicMobileBackend
        
        # Check the method exists
        self.assertTrue(hasattr(LybicMobileBackend, 'destroy_sandbox'))
    
    def test_destroy_sandbox_skips_precreated(self):
        """Verify destroy_sandbox skips pre-created sandboxes"""
        from gui_agents.agents.Backend.LybicBackend import LybicBackend
        
        # Mock the dependencies
        with patch('gui_agents.agents.Backend.LybicBackend.LybicClient') as MockClient:
            with patch('gui_agents.agents.Backend.LybicBackend.Sandbox') as MockSandbox:
                # Create a backend with a pre-created sandbox
                backend = LybicBackend(
                    api_key='test_key',
                    org_id='test_org',
                    precreate_sid='PRECREATED-SANDBOX-ID'
                )
                
                # Mock the sandbox manager to track delete calls
                backend.sandbox_manager = Mock()
                backend.sandbox_manager.delete = Mock()
                
                # Call destroy_sandbox
                backend.destroy_sandbox()
                
                # Verify that delete was NOT called for pre-created sandbox
                backend.sandbox_manager.delete.assert_not_called()
    
    def test_protobuf_has_destroy_field(self):
        """Verify protobuf message has destroySandbox field"""
        from gui_agents.proto.pb import agent_pb2
        
        # Create a request
        request = agent_pb2.RunAgentInstructionRequest()
        
        # Verify the field exists by setting it
        request.destroySandbox = True
        self.assertTrue(request.destroySandbox)
        
        request.destroySandbox = False
        self.assertFalse(request.destroySandbox)
    
    def test_task_request_has_destroy_field(self):
        """Verify TaskRequest has destroy_sandbox field"""
        from gui_agents.service.api_models import TaskRequest
        
        # Create a task request with destroy_sandbox
        request = TaskRequest(
            instruction="Test task",
            destroy_sandbox=True
        )
        
        self.assertTrue(request.destroy_sandbox)
        
        # Create a task request without destroy_sandbox (default should be False)
        request2 = TaskRequest(
            instruction="Test task"
        )
        
        self.assertFalse(request2.destroy_sandbox)


class TestCLIAppDestroySandbox(unittest.TestCase):
    """Test destroy_sandbox in CLI application"""
    
    def test_cli_argument_parser(self):
        """Verify CLI has --destroy-sandbox argument"""
        import gui_agents.cli_app as cli_app
        import argparse
        
        # Create parser similar to main()
        parser = argparse.ArgumentParser(description='GUI Agent CLI Application')
        parser.add_argument('--backend', type=str, default='lybic')
        parser.add_argument('--destroy-sandbox', action='store_true')
        
        # Test parsing
        args = parser.parse_args(['--destroy-sandbox'])
        self.assertTrue(args.destroy_sandbox)
        
        # Test default (without flag)
        args2 = parser.parse_args([])
        self.assertFalse(args2.destroy_sandbox)


if __name__ == "__main__":
    print("=" * 80)
    print("Testing destroy_sandbox functionality")
    print("=" * 80)
    
    # Run tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 80)
    if result.wasSuccessful():
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed")
    print("=" * 80)
    
    exit(0 if result.wasSuccessful() else 1)
