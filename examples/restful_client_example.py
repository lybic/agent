#!/usr/bin/env python3
"""
Example client for Lybic GUI Agent RESTful API

This script demonstrates how to use the RESTful API to:
1. Submit tasks asynchronously
2. Poll task status
3. Use streaming endpoint for real-time updates
"""

import requests
import json
import time
import sys
from typing import Optional


class LybicAgentClient:
    """Simple client for Lybic GUI Agent RESTful API"""
    
    def __init__(self, base_url: str = "http://localhost:8080", 
                 api_key: Optional[str] = None, 
                 org_id: Optional[str] = None):
        """
        Initialize the client
        
        Args:
            base_url: Base URL of the RESTful API server
            api_key: Lybic API key (optional, can be set per request)
            org_id: Lybic organization ID (optional, can be set per request)
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.org_id = org_id
    
    def get_auth(self, api_key: Optional[str] = None, org_id: Optional[str] = None) -> Optional[dict]:
        """Get authentication dict"""
        key = api_key or self.api_key
        org = org_id or self.org_id
        
        if key and org:
            return {
                "api_key": key,
                "org_id": org,
                "api_endpoint": "https://api.lybic.cn/"
            }
        return None
    
    def get_agent_info(self) -> dict:
        """Get agent server information"""
        response = requests.get(f"{self.base_url}/api/agent/info")
        response.raise_for_status()
        return response.json()
    
    def submit_task(self, instruction: str, **kwargs) -> str:
        """
        Submit a task asynchronously
        
        Args:
            instruction: Task instruction in natural language
            **kwargs: Additional parameters (mode, max_steps, etc.)
        
        Returns:
            Task ID
        """
        auth = self.get_auth(kwargs.pop('api_key', None), kwargs.pop('org_id', None))
        
        data = {
            "instruction": instruction,
            "authentication": auth,
            **kwargs
        }
        
        response = requests.post(f"{self.base_url}/api/agent/submit", json=data)
        response.raise_for_status()
        result = response.json()
        return result["task_id"]
    
    def get_task_status(self, task_id: str) -> dict:
        """Get task status"""
        response = requests.get(f"{self.base_url}/api/agent/status", params={"task_id": task_id})
        response.raise_for_status()
        return response.json()
    
    def cancel_task(self, task_id: str) -> dict:
        """Cancel a running task"""
        response = requests.post(f"{self.base_url}/api/agent/cancel", json={"task_id": task_id})
        response.raise_for_status()
        return response.json()
    
    def list_tasks(self, limit: int = 100, offset: int = 0) -> dict:
        """List all tasks"""
        response = requests.get(
            f"{self.base_url}/api/agent/tasks",
            params={"limit": limit, "offset": offset}
        )
        response.raise_for_status()
        return response.json()
    
    def wait_for_task(self, task_id: str, poll_interval: float = 2.0, timeout: float = 300.0) -> dict:
        """
        Wait for a task to complete
        
        Args:
            task_id: Task ID to wait for
            poll_interval: Time between status checks (seconds)
            timeout: Maximum time to wait (seconds)
        
        Returns:
            Final task status
        """
        start_time = time.time()
        
        while True:
            status = self.get_task_status(task_id)
            
            if status["status"] in ["completed", "failed", "cancelled"]:
                return status
            
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"Task {task_id} did not complete within {timeout} seconds")
            
            time.sleep(poll_interval)
    
    def run_task_stream(self, instruction: str, **kwargs):
        """
        Run a task with streaming updates (Server-Sent Events)
        
        Args:
            instruction: Task instruction in natural language
            **kwargs: Additional parameters
        
        Yields:
            Event dictionaries with task updates
        """
        auth = self.get_auth(kwargs.pop('api_key', None), kwargs.pop('org_id', None))
        
        data = {
            "instruction": instruction,
            "authentication": auth,
            **kwargs
        }
        
        response = requests.post(
            f"{self.base_url}/api/agent/run",
            json=data,
            stream=True,
            headers={"Accept": "text/event-stream"}
        )
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data:'):
                    try:
                        event_data = json.loads(line[5:].strip())
                        yield event_data
                    except json.JSONDecodeError:
                        continue
    
    def create_sandbox(self, shape: str, **kwargs) -> dict:
        """Create a new sandbox"""
        auth = self.get_auth(kwargs.pop('api_key', None), kwargs.pop('org_id', None))
        
        data = {
            "shape": shape,
            "authentication": auth,
            **kwargs
        }
        
        response = requests.post(f"{self.base_url}/api/sandbox/create", json=data)
        response.raise_for_status()
        return response.json()


def example_async_submission():
    """Example: Submit task asynchronously and poll for completion"""
    print("=" * 60)
    print("Example 1: Async Task Submission")
    print("=" * 60)
    
    # Initialize client (credentials from environment or args)
    import os
    client = LybicAgentClient(
        base_url=os.getenv("RESTFUL_URL", "http://localhost:8080"),
        api_key=os.getenv("LYBIC_API_KEY"),
        org_id=os.getenv("LYBIC_ORG_ID")
    )
    
    # Get server info
    print("\nGetting server info...")
    info = client.get_agent_info()
    print(f"Server version: {info['version']}")
    print(f"Max concurrent tasks: {info['max_concurrent_tasks']}")
    
    # Submit a task
    print("\nSubmitting task...")
    task_id = client.submit_task(
        instruction="Open calculator and compute 123 + 456",
        mode="fast",
        max_steps=30,
        platform="Windows"
    )
    print(f"Task submitted: {task_id}")
    
    # Poll for completion
    print("\nWaiting for task to complete...")
    try:
        final_status = client.wait_for_task(task_id, poll_interval=2.0, timeout=120.0)
        print(f"\nTask completed!")
        print(f"Status: {final_status['status']}")
        print(f"Message: {final_status['message']}")
        
        if final_status.get('execution_statistics'):
            stats = final_status['execution_statistics']
            print(f"\nExecution Statistics:")
            print(f"  Steps: {stats['steps']}")
            print(f"  Duration: {stats['duration_seconds']:.2f}s")
            print(f"  Tokens: {stats['total_tokens']} (input: {stats['input_tokens']}, output: {stats['output_tokens']})")
            print(f"  Cost: {stats['cost']} {stats['currency_symbol']}")
    
    except TimeoutError as e:
        print(f"Error: {e}")
        print("Cancelling task...")
        result = client.cancel_task(task_id)
        print(f"Cancel result: {result}")


def example_streaming():
    """Example: Use streaming endpoint for real-time updates"""
    print("\n" + "=" * 60)
    print("Example 2: Streaming Task Execution")
    print("=" * 60)
    
    import os
    client = LybicAgentClient(
        base_url=os.getenv("RESTFUL_URL", "http://localhost:8080"),
        api_key=os.getenv("LYBIC_API_KEY"),
        org_id=os.getenv("LYBIC_ORG_ID")
    )
    
    print("\nRunning task with streaming updates...")
    try:
        for event in client.run_task_stream(
            instruction="Open notepad and type 'Hello World'",
            mode="fast",
            max_steps=20
        ):
            print(f"[{event['stage']}] {event['message']}")
            
            if event['stage'] in ['finished', 'error', 'cancelled']:
                break
    
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")


def example_with_custom_model():
    """Example: Use custom LLM API key (ark_apikey parameter)"""
    print("\n" + "=" * 60)
    print("Example 3: Custom LLM API Key")
    print("=" * 60)
    
    import os
    client = LybicAgentClient(
        base_url=os.getenv("RESTFUL_URL", "http://localhost:8080"),
        api_key=os.getenv("LYBIC_API_KEY"),
        org_id=os.getenv("LYBIC_ORG_ID")
    )
    
    # Submit task with custom LLM API key
    print("\nSubmitting task with custom LLM API key...")
    task_id = client.submit_task(
        instruction="Open calculator",
        mode="fast",
        max_steps=10,
        ark_apikey=os.getenv("OPENAI_API_KEY")  # Custom API key for LLM models
    )
    print(f"Task submitted: {task_id}")
    
    # Check status
    status = client.get_task_status(task_id)
    print(f"Initial status: {status['status']}")


def example_list_tasks():
    """Example: List all tasks"""
    print("\n" + "=" * 60)
    print("Example 4: List Tasks")
    print("=" * 60)
    
    import os
    client = LybicAgentClient(
        base_url=os.getenv("RESTFUL_URL", "http://localhost:8080")
    )
    
    print("\nListing recent tasks...")
    result = client.list_tasks(limit=10)
    print(f"Total tasks: {result['total']}")
    print(f"\nShowing {len(result['tasks'])} tasks:")
    
    for task in result['tasks']:
        print(f"  - {task['task_id']}: {task['status']} - {task['instruction'][:50]}...")


def main():
    """Run all examples"""
    print("Lybic GUI Agent RESTful API - Client Examples")
    print("=" * 60)
    
    # Check if server is accessible
    import os
    base_url = os.getenv("RESTFUL_URL", "http://localhost:8080")
    
    try:
        response = requests.get(f"{base_url}/api/agent/info", timeout=5)
        response.raise_for_status()
        print(f"✓ Server is accessible at {base_url}")
    except requests.exceptions.RequestException as e:
        print(f"✗ Cannot connect to server at {base_url}")
        print(f"  Error: {e}")
        print("\nPlease ensure the server is running:")
        print("  lybic-guiagent-restful")
        sys.exit(1)
    
    # Check credentials
    if not os.getenv("LYBIC_API_KEY") or not os.getenv("LYBIC_ORG_ID"):
        print("\n⚠ Warning: LYBIC_API_KEY and LYBIC_ORG_ID not set in environment")
        print("  Some examples may fail without authentication")
        print("\nTo set credentials:")
        print("  export LYBIC_API_KEY=your_api_key")
        print("  export LYBIC_ORG_ID=your_org_id")
    
    # Run examples
    try:
        # Uncomment the examples you want to run:
        
        # Example 1: Async submission (requires authentication)
        # example_async_submission()
        
        # Example 2: Streaming (requires authentication)
        # example_streaming()
        
        # Example 3: Custom model API key (requires authentication)
        # example_with_custom_model()
        
        # Example 4: List tasks (no authentication required)
        example_list_tasks()
        
    except Exception as e:
        print(f"\nError running example: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
