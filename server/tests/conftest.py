"""
Pytest configuration file - automatically loaded by pytest
"""
import sys
from pathlib import Path

# Add the parent directory (server/) to the Python path
# so test files can import modules like battle_engine, item_effects, etc.
sys.path.insert(0, str(Path(__file__).parent.parent))
