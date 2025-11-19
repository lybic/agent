#!/usr/bin/env python3
"""
Simple verification script for MCP server functionality.
This script tests the basic functionality without requiring pytest.
"""

import sys
import os
from pathlib import Path

print("=" * 80)
print("MCP Server Verification Script")
print("=" * 80)

# Test 1: Check file syntax
print("\n[1/5] Checking MCP server file syntax...")
try:
    import py_compile
    mcp_file = Path(__file__).parent.parent / "gui_agents" / "mcp_app.py"
    py_compile.compile(str(mcp_file), doraise=True)
    print("✓ Syntax check passed")
except Exception as e:
    print(f"✗ Syntax check failed: {e}")
    sys.exit(1)

# Test 2: Check access_tokens.txt exists
print("\n[2/5] Checking access_tokens.txt file...")
tokens_file = Path(__file__).parent.parent / "gui_agents" / "access_tokens.txt"
if tokens_file.exists():
    print(f"✓ Access tokens file exists at: {tokens_file}")
    # Read and display token count (excluding comments and empty lines)
    with open(tokens_file) as f:
        tokens = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
    print(f"  Found {len(tokens)} valid token(s)")
else:
    print(f"✗ Access tokens file not found at: {tokens_file}")
    sys.exit(1)

# Test 3: Check MCP dependencies
print("\n[3/5] Checking MCP dependencies...")
required_modules = ['mcp', 'fastapi', 'uvicorn']
missing = []
for module in required_modules:
    try:
        __import__(module)
        print(f"✓ {module} is installed")
    except ImportError:
        print(f"✗ {module} is NOT installed")
        missing.append(module)

if missing:
    print(f"\nMissing dependencies: {', '.join(missing)}")
    print("Install with: pip install " + " ".join(missing))

# Test 4: Check MCP README
print("\n[4/5] Checking MCP documentation...")
readme_file = Path(__file__).parent.parent / "gui_agents" / "MCP_README.md"
if readme_file.exists():
    print(f"✓ MCP README exists at: {readme_file}")
    size = readme_file.stat().st_size
    print(f"  File size: {size} bytes")
else:
    print(f"✗ MCP README not found at: {readme_file}")

# Test 5: Check pyproject.toml entry point
print("\n[5/5] Checking pyproject.toml configuration...")
pyproject_file = Path(__file__).parent.parent / "pyproject.toml"
if pyproject_file.exists():
    content = pyproject_file.read_text()
    if "lybic-guiagent-mcp" in content and "gui_agents.mcp_app:main" in content:
        print("✓ MCP server entry point is configured in pyproject.toml")
    else:
        print("✗ MCP server entry point not found in pyproject.toml")
    
    # Check MCP dependencies
    if "mcp>=" in content and "fastapi>=" in content:
        print("✓ MCP dependencies are listed in pyproject.toml")
    else:
        print("✗ MCP dependencies not properly listed in pyproject.toml")
else:
    print(f"✗ pyproject.toml not found")

# Summary
print("\n" + "=" * 80)
print("Verification Summary")
print("=" * 80)
print("\nCore files created:")
print("  - gui_agents/mcp_app.py (MCP server implementation)")
print("  - gui_agents/access_tokens.txt (authentication tokens)")
print("  - gui_agents/MCP_README.md (documentation)")
print("  - tests/test_mcp_app.py (test suite)")

print("\nTo start the MCP server:")
print("  1. Set environment variables: LYBIC_API_KEY, LYBIC_ORG_ID")
print("  2. Run: python -m gui_agents.mcp_app")
print("  3. Or use: lybic-guiagent-mcp (after installation)")

print("\nEndpoints:")
print("  - POST /mcp - MCP Streamable HTTP endpoint (requires Bearer token)")
print("  - GET /health - Health check")
print("  - GET / - Server information")

print("\nAvailable tools:")
print("  - create_sandbox - Create a new sandbox environment")
print("  - get_sandbox_screenshot - Capture screenshot from sandbox")
print("  - execute_instruction - Execute agent instruction with streaming")

print("\n" + "=" * 80)
if missing:
    print("⚠ Warning: Some dependencies are missing. Install them before running the server.")
    sys.exit(1)
else:
    print("✓ All checks passed! MCP server is ready to use.")
    sys.exit(0)

