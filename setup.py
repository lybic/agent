from setuptools import find_packages, setup

setup(
    name="lybicguiagents",
    version="0.1.0",
    description="A library for creating general purpose GUI agents using multimodal LLMs.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Lybic Development Team",
    author_email="lybic@tingyutech.com",
    packages=find_packages(),
    extras_require={"dev": ["black"]},  # Code formatter for linting
    entry_points={
        "console_scripts": [
            "lybic_gui_agent=gui_agents.cli_app:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
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
    python_requires=">=3.9, <=3.12",
)
