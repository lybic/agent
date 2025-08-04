# Makefile for lybic-guiagents
#
# Copyright (c) 2019-2025   Beijing Tingyu Technology Co., Ltd.
# Copyright (c) 2025        Lybic Development Team <team@lybic.ai, lybic@tingyutech.com>
#
# These Terms of Service ("Terms") set forth the rules governing your access to and use of the website lybic.ai
# ("Website"), our web applications, and other services (collectively, the "Services") provided by Beijing Tingyu
# Technology Co., Ltd. ("Company," "we," "us," or "our"), a company registered in Haidian District, Beijing. Any
# breach of these Terms may result in the suspension or termination of your access to the Services.
# By accessing and using the Services and/or the Website, you represent that you are at least 18 years old,
# acknowledge that you have read and understood these Terms, and agree to be bound by them. By using or accessing
# the Services and/or the Website, you further represent and warrant that you have the legal capacity and authority
# to agree to these Terms, whether as an individual or on behalf of a company. If you do not agree to all of these
# Terms, do not access or use the Website or Services.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
.PHONY: help build publish clean clean-build-cache clean-venv create-venv

# Variables
PYTHON := python3
VENV_DIR := .venv

help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  help               	Display this help message"
	@echo "  build              	Build the python package"
	@echo "  create-venv        	Create a virtual environment in .venv/ via uv"
	@echo "  clean              	Remove build artifacts"
	@echo "  clean-build-cache  	Remove Python cache files"
	@echo "  clean-venv         	Remove the virtual environment"
	@echo "  convert-dependencies	Convert dependency formats"
	@echo "  install-uv         	Install the uv package"
	@echo "  publish            	Publish the package to PyPI"

convert-dependencies:
	rm -f requirements.txt
	$(PYTHON) scripts/covert_dependencies.py

create-venv:
	@echo "Creating a virtual environment via uv..."
	uv python install 3.12.11
	uv venv -p 3.12.11
	source .venv/bin/activate
	uv sync

install-uv:
	@echo "Installing uv..."
	$(PYTHON) -m pip install uv

build:
	@echo "Building the package..."
	uv -m build

publish:
	@echo "Publishing the package..."
	twine upload dist/*

clean: clean-build-cache
	@echo "Cleaning build artifacts..."
	rm -rf build dist *.egg-info

clean-build-cache:
	@echo "Cleaning Python cache files..."
	find . -type f -name '*.py[co]' -delete -o -type d -name __pycache__ -delete

clean-venv:
	@echo "Removing virtual environment..."
	rm -rf $(VENV_DIR)
