#!/usr/bin/env python3
"""
Sync script for autobattler development environment.
This script ensures all dependencies are properly installed.
"""

import configparser
import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd, cwd=None, check=True):
    """Run a shell command and return the result.

    The output is printed before anything is raised. `check=True` raises from
    inside subprocess.run, so a version of this that printed afterwards showed
    a bare CalledProcessError and threw away the reason pip had failed.
    """
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr and result.returncode != 0:
        print(result.stderr, file=sys.stderr)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=result.stderr
        )
    return result


def required_python_version():
    """The Python devenv/config.ini asks for, as a string like "3.11"."""
    config = configparser.ConfigParser()
    config.read(Path(__file__).parent / "config.ini")
    return config.get("python", "version", fallback=None)


def venv_python_version(venv_path):
    """The version of the Python in `venv_path`, or None if unreadable."""
    bin_dir = "Scripts" if sys.platform == "win32" else "bin"
    python = venv_path / bin_dir / "python"
    if not python.exists():
        return None
    say_version = "import sys; print('%d.%d' % sys.version_info[:2])"
    result = subprocess.run(
        [str(python), "-c", say_version],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or None


def ensure_venv():
    """Ensure Python virtual environment exists, on the right Python.

    A venv built on the wrong version is worse than no venv at all: pip then
    tries to build every pinned dependency from source, and the ones with no
    wheel for that version (pydantic-core, greenlet) fail deep inside a Rust
    build. Nothing in that output says "wrong Python", so this checks first
    and says it plainly.

    It refuses rather than rebuilding. Deleting somebody's environment is a
    bigger surprise than a message, and the fix is one line to paste.
    """
    venv_path = Path(".venv")
    if not venv_path.exists():
        print("Creating Python virtual environment...")
        run_command([sys.executable, "-m", "venv", ".venv"])
        return venv_path

    wanted = required_python_version()
    found = venv_python_version(venv_path)
    if wanted and found and found != wanted:
        raise SystemExit(
            f"\n.venv is Python {found}, but this project needs"
            f" Python {wanted} (devenv/config.ini).\n"
            f"Installing into it fails while building pydantic-core.\n\n"
            f"Rebuild it:\n"
            f"    rm -rf .venv && python{wanted} -m venv .venv"
            f" && devenv sync\n"
        )
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
