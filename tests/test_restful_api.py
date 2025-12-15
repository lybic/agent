"""
Test the RESTful API implementation
"""
import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_restful_app_syntax():
    """Test that restful_app.py has valid Python syntax"""
    import ast
    
    restful_app_path = Path(__file__).parent.parent / "gui_agents" / "restful_app.py"
    with open(restful_app_path, 'r') as f:
        code = f.read()
        try:
            ast.parse(code)
        except SyntaxError as e:
            pytest.fail(f"Syntax error in restful_app.py: {e}")


def test_required_models():
    """Test that all required Pydantic models are defined"""
    import ast
    
    restful_app_path = Path(__file__).parent.parent / "gui_agents" / "restful_app.py"
    with open(restful_app_path, 'r') as f:
        code = f.read()
        tree = ast.parse(code)
    
    # Find all class definitions
    classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    
    required_models = [
        'LybicAuthentication',
        'RunAgentRequest',
        'SubmitTaskRequest',
        'CancelRequest',
        'CreateSandboxRequest',
        'TaskStatusResponse',
        'AgentInfoResponse',
        'RestfulAgentService'
    ]
    
    for model in required_models:
        assert model in classes, f"Required model {model} not found in restful_app.py"


def test_required_endpoints():
    """Test that all required API endpoints are defined"""
    import ast
    
    restful_app_path = Path(__file__).parent.parent / "gui_agents" / "restful_app.py"
    with open(restful_app_path, 'r') as f:
        code = f.read()
    
    required_endpoints = [
        '/api/agent/info',
        '/api/agent/run',
        '/api/agent/submit',
        '/api/agent/status',
        '/api/agent/cancel',
        '/api/agent/tasks',
        '/api/sandbox/create',
    ]
    
    for endpoint in required_endpoints:
        assert f'"{endpoint}"' in code or f"'{endpoint}'" in code, \
            f"Required endpoint {endpoint} not found in restful_app.py"


def test_ark_apikey_support():
    """Test that ark_apikey parameter is supported"""
    import ast
    
    restful_app_path = Path(__file__).parent.parent / "gui_agents" / "restful_app.py"
    with open(restful_app_path, 'r') as f:
        code = f.read()
    
    # Check that ark_apikey is mentioned in the code
    assert 'ark_apikey' in code, "ark_apikey parameter not found in restful_app.py"
    
    # Check that it's in the request models
    assert 'ark_apikey: Optional[str]' in code or 'ark_apikey:Optional[str]' in code, \
        "ark_apikey not properly defined in request models"


def test_authentication_model():
    """Test that LybicAuthentication model has required fields"""
    import ast
    
    restful_app_path = Path(__file__).parent.parent / "gui_agents" / "restful_app.py"
    with open(restful_app_path, 'r') as f:
        code = f.read()
    
    # Check for required authentication fields
    required_fields = ['api_key', 'org_id', 'api_endpoint']
    for field in required_fields:
        assert field in code, f"Required authentication field {field} not found"


def test_fastapi_imports():
    """Test that FastAPI is properly imported"""
    import ast
    
    restful_app_path = Path(__file__).parent.parent / "gui_agents" / "restful_app.py"
    with open(restful_app_path, 'r') as f:
        code = f.read()
        tree = ast.parse(code)
    
    # Check for FastAPI imports
    has_fastapi_import = False
    has_pydantic_import = False
    has_sse_import = False
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and 'fastapi' in node.module:
                has_fastapi_import = True
            if node.module and 'pydantic' in node.module:
                has_pydantic_import = True
            if node.module and 'sse_starlette' in node.module:
                has_sse_import = True
    
    assert has_fastapi_import, "FastAPI import not found"
    assert has_pydantic_import, "Pydantic import not found"
    assert has_sse_import, "SSE Starlette import not found"


def test_streaming_support():
    """Test that streaming functionality is implemented"""
    import ast
    
    restful_app_path = Path(__file__).parent.parent / "gui_agents" / "restful_app.py"
    with open(restful_app_path, 'r') as f:
        code = f.read()
    
    # Check for EventSourceResponse (SSE streaming)
    assert 'EventSourceResponse' in code, "EventSourceResponse not found - streaming not implemented"
    
    # Check for event generator
    assert 'event_generator' in code or 'async def' in code, "Event generator function not found"


def test_service_implementation():
    """Test that RestfulAgentService class is properly implemented"""
    import ast
    
    restful_app_path = Path(__file__).parent.parent / "gui_agents" / "restful_app.py"
    with open(restful_app_path, 'r') as f:
        code = f.read()
        tree = ast.parse(code)
    
    # Find RestfulAgentService class
    service_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'RestfulAgentService':
            service_class = node
            break
    
    assert service_class is not None, "RestfulAgentService class not found"
    
    # Check for required methods
    method_names = [method.name for method in service_class.body if isinstance(method, ast.FunctionDef) or isinstance(method, ast.AsyncFunctionDef)]
    
    required_methods = [
        '__init__',
        '_make_agent',
        '_make_backend_kwargs',
        '_run_task',
        '_create_sandbox',
    ]
    
    for method in required_methods:
        assert method in method_names, f"Required method {method} not found in RestfulAgentService"


def test_mode_support():
    """Test that both 'normal' and 'fast' modes are supported"""
    import ast
    
    restful_app_path = Path(__file__).parent.parent / "gui_agents" / "restful_app.py"
    with open(restful_app_path, 'r') as f:
        code = f.read()
    
    # Check for mode handling
    assert '"normal"' in code or "'normal'" in code, "Normal mode not found"
    assert '"fast"' in code or "'fast'" in code, "Fast mode not found"
    assert 'mode' in code.lower(), "Mode parameter handling not found"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
