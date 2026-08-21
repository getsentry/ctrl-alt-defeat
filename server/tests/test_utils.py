"""
Tests for server/utils.py

Also holds the response walker that the endpoint contract tests use, since it
is a utility over decoded JSON rather than a test of any one endpoint.
"""

from typing import Any, Iterator, List, Tuple

import pytest
from utils import to_position


class TestToPosition:
    """to_position() turns anything arriving into an (x, y) pair"""

    def test_converts_a_json_list(self):
        assert to_position([2, 3]) == (2, 3)

    def test_leaves_a_pair_alone(self):
        assert to_position((2, 3)) == (2, 3)

    def test_always_returns_a_pair_of_ints(self):
        result = to_position([2, 3])
        assert isinstance(result, tuple)
        assert all(isinstance(v, int) for v in result)

    def test_rejects_a_mapping(self):
        with pytest.raises(TypeError, match="not a mapping"):
            to_position({"x": 2, "y": 3})

    def test_rejects_the_wrong_length(self):
        with pytest.raises(ValueError, match="exactly 2 items"):
            to_position([2, 3, 4])
        with pytest.raises(ValueError, match="exactly 2 items"):
            to_position([2])

    def test_rejects_a_string(self):
        with pytest.raises(TypeError):
            to_position("storage")

    def test_rejects_none(self):
        with pytest.raises(TypeError):
            to_position(None)


def walk(value: Any, path: str = "$") -> Iterator[Tuple[str, Any]]:
    """Yield (path, value) for every node in a decoded JSON tree"""
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, f"{path}[{index}]")


def find_bad_positions(payload: Any) -> List[str]:
    """
    Return a message for every "position" key that is not a two-item list of ints.

    This is the guard. It does not name any endpoint or any field, so it keeps
    working when the API grows.
    """
    problems = []
    for path, value in walk(payload):
        if not path.endswith(".position"):
            continue
        if value is None:
            continue  # None means "in storage", which is allowed
        if not isinstance(value, list):
            problems.append(
                f"{path} is a {type(value).__name__}; a response carries [x, y]"
            )
            continue
        if len(value) != 2:
            problems.append(f"{path} has {len(value)} items, expected 2")
            continue
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in value):
            problems.append(f"{path} holds non-integer values: {value!r}")
    return problems


class TestFindBadPositions:
    """The guard must actually catch each bad format"""

    def test_accepts_the_canonical_form(self):
        assert find_bad_positions({"position": [2, 3]}) == []

    def test_allows_null_for_storage(self):
        assert find_bad_positions({"position": None}) == []

    def test_catches_a_dictionary_position(self):
        assert find_bad_positions({"position": {"x": 2, "y": 3}})

    def test_catches_a_wrong_length(self):
        assert find_bad_positions({"position": [2, 3, 4]})

    def test_catches_a_nested_bad_position(self):
        payload = {"session": {"items": [{"position": {"x": 1, "y": 1}}]}}
        assert find_bad_positions(payload)

    def test_walks_into_lists_and_dicts(self):
        payload = {"a": [{"b": {"position": [1, 2]}}]}
        assert find_bad_positions(payload) == []
