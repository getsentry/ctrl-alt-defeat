"""
Utility functions for the server
"""

from datetime import datetime, timezone


def utc_now():
    """Get current UTC time (naive datetime for PostgreSQL compatibility)"""
    return datetime.now(timezone.utc).replace(tzinfo=None)
