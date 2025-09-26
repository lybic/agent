from setuptools import find_packages, setup
from setuptools.command.build_py import build_py
import subprocess
import os
import sys
import shutil

def generate_grpc_stubs():
    """Generate gRPC stubs from .proto files."""
    PROTO_DIR = "gui_agents/proto"
    PB_DIR = os.path.join(PROTO_DIR, "pb")
    
    try:
        import grpc_tools.protoc
    except (ImportError, ModuleNotFoundError):
        # This can happen if the grpc extra is not installed.
        # The user can install it with `pip install .[grpc]`
        print("Skipping gRPC stub generation: grpcio-tools is not installed.")
        return

    proto_file = os.path.join(PROTO_DIR, "agent.proto")
    if not os.path.exists(proto_file):
        print(f"Warning: {proto_file} not found, skipping gRPC stub generation.")
        return

    if not os.path.exists(PB_DIR):
        os.makedirs(PB_DIR)
    
    # Touch __init__.py
    init_py = os.path.join(PB_DIR, '__init__.py')
    if not os.path.exists(init_py):
        open(init_py, 'a').close()

    # Copy proto file to target directory to ensure relative imports are correct
    temp_proto_file = os.path.join(PB_DIR, "agent.proto")
    shutil.copy(proto_file, temp_proto_file)

    print("Generating gRPC stubs...")
    
    command = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        "--python_out=.",
        "--grpc_python_out=.",
        "agent.proto",
    ]

    try:
        # Run from the pb directory
        subprocess.check_call(command, cwd=PB_DIR)
    except subprocess.CalledProcessError as e:
        print(f"Error generating gRPC stubs: {e}")
        # Don't exit, just warn. The user might be installing without wanting to build.
    finally:
        # Clean up copied proto file
        if os.path.exists(temp_proto_file):
            os.remove(temp_proto_file)

class CustomBuildPy(build_py):
    """Custom build command to generate gRPC stubs."""
    def run(self):
        generate_grpc_stubs()
        super().run()

setup(
    name="lybic-guiagents",
    version="1.0.0",
    description="A library for creating general purpose GUI agents using multimodal LLMs.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Lybic Development Team",
    author_email="lybic@tingyutech.com",
    packages=find_packages(),
    extras_require={
        "dev": ["pytest", "black"],
        "grpc": ["grpcio", "grpcio-tools>=1.71.2"]
    },
    entry_points={
        "console_scripts": [
            "lybic_gui_agent=gui_agents.cli_app:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS :: MacOS X",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords="ai, llm, gui, agent, multimodal",
    project_urls={
        "Source": "https://github.com/lybic/agent",
        "Bug Reports": "https://github.com/lybic/agent/issues",
    },
    python_requires=">=3.12",
    cmdclass={
        'build_py': CustomBuildPy,
    },
)
