"""
Pytest configuration for autobattler server tests
"""

import os

import pytest


@pytest.fixture(autouse=True)
def enable_test_mode():
    """Automatically enable TEST_MODE for all tests"""
    os.environ["TEST_MODE"] = "true"
    yield
    # Cleanup after test (optional)
    os.environ.pop("TEST_MODE", None)


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment once for all tests"""
    # Enable TEST_MODE for the entire test session
    os.environ["TEST_MODE"] = "true"
    yield
    # Cleanup is optional since process will end anyway
