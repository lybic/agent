#!/usr/bin/env python3
import toml
import sys
from packaging import version


def read_requirements(requirements_path="requirements.txt"):
    """Read dependencies from requirements.txt and return a dict of name:version."""
    deps = {}
    try:
        with open(requirements_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '==' in line:
                    name, ver = line.split('==', 1)
                    deps[name.strip()] = ver.strip()
        return deps
    except FileNotFoundError:
        print(f"Error: {requirements_path} not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading {requirements_path}: {str(e)}")
        sys.exit(1)


def update_pyproject(pyproject_path="pyproject.toml", requirements_path="requirements.txt"):
    """Update pyproject.toml with versions from requirements.txt for matching dependencies."""
    try:
        # Read pyproject.toml
        with open(pyproject_path, 'r', encoding='utf-8') as f:
            pyproject_data = toml.load(f)

        # Read requirements.txt
        req_deps = read_requirements(requirements_path)

        # Get dependencies from pyproject.toml
        project_deps = pyproject_data.get('project', {}).get('dependencies', [])
        updated_deps = []
        modified = False

        for dep in project_deps:
            # Extract package name (remove version specifiers like >=, <=, ==, etc.)
            dep_name = dep.split('=', 1)[0].split('>', 1)[0].split('<', 1)[0].split('~', 1)[0].strip()
            if dep_name in req_deps and '==' not in dep:
                # Update dependency with version from requirements.txt
                updated_deps.append(f"{dep_name}=={req_deps[dep_name]}")
                modified = True
            else:
                updated_deps.append(dep)

        if modified:
            # Update pyproject.toml with new dependencies list
            pyproject_data['project']['dependencies'] = updated_deps
            with open(pyproject_path, 'w', encoding='utf-8') as f:
                toml.dump(pyproject_data, f)
            print(f"Updated {pyproject_path} with version numbers from {requirements_path}")
        else:
            print("No updates needed in pyproject.toml")

    except FileNotFoundError:
        print(f"Error: {pyproject_path} not found")
        sys.exit(1)
    except toml.TomlDecodeError:
        print(f"Error: Invalid TOML format in {pyproject_path}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    update_pyproject()
