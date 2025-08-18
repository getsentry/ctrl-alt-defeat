#!/usr/bin/env python3
"""
Sync script for autobattler development environment.
This script ensures all dependencies are properly installed.
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd, cwd=None, check=True):
    """Run a shell command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)
    if result.stdout:
        print(result.stdout)
    if result.stderr and result.returncode != 0:
        print(result.stderr, file=sys.stderr)
    return result


def ensure_venv():
    """Ensure Python virtual environment exists."""
    venv_path = Path(".venv")
    if not venv_path.exists():
        print("Creating Python virtual environment...")
        run_command([sys.executable, "-m", "venv", ".venv"])
    return venv_path


def install_python_deps():
    """Install Python dependencies."""
    venv_path = ensure_venv()
    pip_path = venv_path / "bin" / "pip" if sys.platform != "win32" else venv_path / "Scripts" / "pip.exe"

    print("Upgrading pip...")
    run_command([str(pip_path), "install", "--upgrade", "pip"])

    requirements_file = Path("server") / "requirements.txt"
    if requirements_file.exists():
        print("Installing Python dependencies...")
        run_command([str(pip_path), "install", "-r", str(requirements_file)])

    # Install development dependencies
    print("Installing development dependencies...")
    dev_deps = ["pytest", "pytest-asyncio", "black", "isort", "flake8", "mypy", "pre-commit"]
    run_command([str(pip_path), "install"] + dev_deps)


def setup_pre_commit():
    """Setup pre-commit hooks."""
    venv_path = Path(".venv")
    pre_commit_path = venv_path / "bin" / "pre-commit" if sys.platform != "win32" else venv_path / "Scripts" / "pre-commit.exe"

    if pre_commit_path.exists():
        print("Installing pre-commit hooks...")
        run_command([str(pre_commit_path), "install"], check=False)


def main(context=None):
    """Main sync function compatible with devenv."""
    # Change to project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    print("Syncing autobattler development environment...")

    # Install Python dependencies
    install_python_deps()

    # Setup pre-commit
    setup_pre_commit()

    print("\n✅ Development environment synced successfully!")
    print("Run 'direnv allow' to activate the environment.")

    return 0  # Return success code


if __name__ == "__main__":
    sys.exit(main())
