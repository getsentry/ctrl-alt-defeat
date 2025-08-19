"""
Pytest configuration file - automatically loaded by pytest
"""
import os
import sys
from pathlib import Path

import pytest

# Add the parent directory (server/) to the Python path
# so test files can import modules like battle_engine, item_effects, etc.
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set TEST_MODE environment variable for all tests
os.environ["TEST_MODE"] = "true"

# Configure test database if not already set
if "DB_NAME" not in os.environ:
    os.environ["DB_NAME"] = "autobattler_test"
if "DB_HOST" not in os.environ:
    os.environ["DB_HOST"] = "localhost:5432"


@pytest.fixture(autouse=True)
def setup_test_mode():
    """Ensure TEST_MODE and test database are configured for all tests"""
    os.environ["TEST_MODE"] = "true"
    # Tests will use test database configured above
    yield
    # Keep TEST_MODE set after test
