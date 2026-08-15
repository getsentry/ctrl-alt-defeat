"""
Utility functions for the server
"""

from datetime import datetime, timezone
from typing import Sequence, Tuple


def utc_now():
    """Get current UTC time (naive datetime for PostgreSQL compatibility)"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ============ Positions ============
#
# A position is an (x, y) pair. The type carries the arity, so nothing has to
# check the length. JSON has no tuple, so it travels the wire as [x, y] and
# Pydantic converts in both directions.
Position = Tuple[int, int]


def to_position(value: Sequence[int]) -> Position:
    """
    Normalise a position to an (x, y) pair.

    JSON decoding gives lists, so anything read back from the database or a
    request body comes through here first.
    """
    if isinstance(value, dict):
        raise TypeError(f"A position is an (x, y) pair, not a mapping: {value!r}")

    if not isinstance(value, (list, tuple)):
        raise TypeError(f"A position is an (x, y) pair, got {type(value).__name__}")

    if len(value) != 2:
        raise ValueError(f"A position has exactly 2 items, got {len(value)}: {value!r}")

    return (int(value[0]), int(value[1]))
