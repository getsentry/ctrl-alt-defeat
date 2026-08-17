"""
Tests for server/item_looks.py, and for the catalogue it governs.

Most of an item's look is a promise about the whole catalogue rather than about
one item: no two items may look the same. That cannot be checked from inside a
single item, so it is checked here, over every item at once.

The JSON files are read straight from disk rather than through ConfigLoader.
The loader catches and logs an exception per file, so a broken item would drop
its whole category quietly and leave nothing for a test to find.
"""

import json
from collections import Counter
from pathlib import Path
from typing import Dict, Iterator, Tuple

import pytest

from item_looks import CATEGORY_COLOR, PALETTE, PATTERNS, hex_of

ITEMS_DIR = Path(__file__).parent.parent / "data" / "items"


def catalogue() -> Iterator[Tuple[str, Dict]]:
    """Every item in the catalogue, as (item_id, config). Containers are not
    items here: they are drawn as the ground, so they have no look."""
    for path in sorted(ITEMS_DIR.glob("*.json")):
        if path.name == "containers.json":
            continue
        data = json.loads(path.read_text())
        for item_id, config in data["items"].items():
            yield item_id, config


ITEMS = dict(catalogue())


class TestThePalette:
    """The names the catalogue is allowed to use"""

    def test_every_colour_is_a_hex_value(self):
        for name, value in PALETTE.items():
            assert value.startswith("#"), f"{name} is not a hex colour"
            assert len(value) == 7, f"{name} is not a six digit hex colour"
            int(value[1:], 16)

    def test_no_two_names_share_a_colour(self):
        repeated = [v for v, n in Counter(PALETTE.values()).items() if n > 1]
        assert not repeated, f"Two names for one colour: {repeated}"

    def test_no_two_patterns_share_a_name(self):
        assert len(set(PATTERNS)) == len(PATTERNS), "A pattern name is repeated"

    def test_every_category_colour_is_in_the_palette(self):
        for category, color in CATEGORY_COLOR.items():
            assert color in PALETTE, f"{category} wears {color}, which does not exist"

    def test_no_two_categories_share_a_colour(self):
        repeated = [c for c, n in Counter(CATEGORY_COLOR.values()).items() if n > 1]
        assert not repeated, f"Two categories wear the same colour: {repeated}"


class TestHexOf:
    """The catalogue names a colour; the client is sent the value"""

    def test_gives_the_value_behind_a_name(self):
        assert hex_of("red") == "#BE0032"

    def test_refuses_a_name_that_is_not_in_the_palette(self):
        with pytest.raises(KeyError, match="not a colour in the palette"):
            hex_of("puce")

    def test_refuses_an_empty_name(self):
        # A container has no colour. The caller decides what that means rather
        # than getting a value back for a colour that was never chosen.
        with pytest.raises(KeyError):
            hex_of("")


class TestTheCatalogue:
    """Every item can be told apart from every other item"""

    def test_there_are_items_to_check(self):
        # A glob that matched nothing would make every test below pass.
        assert len(ITEMS) > 50, f"Only found {len(ITEMS)} items"

    def test_no_two_items_look_the_same(self):
        """The promise. Colour and pattern together name exactly one item."""
        looks: Dict[Tuple[str, str], str] = {}
        for item_id, config in ITEMS.items():
            look = (config["color"], config["pattern"])
            assert look not in looks, (
                f"{item_id} and {looks[look]} are both {look[0]} {look[1]}"
            )
            looks[look] = item_id

    def test_every_item_has_a_look(self):
        for item_id, config in ITEMS.items():
            assert config.get("color"), f"{item_id} has no colour"
            assert config.get("pattern"), f"{item_id} has no pattern"

    def test_every_colour_is_one_the_client_knows(self):
        for item_id, config in ITEMS.items():
            color = config["color"]
            assert color in PALETTE, f"{item_id} is {color}, not in the palette"

    def test_every_pattern_is_one_the_client_knows(self):
        for item_id, config in ITEMS.items():
            pattern = config["pattern"]
            assert pattern in PATTERNS, f"{item_id} is {pattern}, which does not exist"

    def test_every_item_wears_the_colour_of_its_category(self):
        """Colour says what kind of thing this is. Pattern says which one."""
        for item_id, config in ITEMS.items():
            category = config["category"]
            assert category in CATEGORY_COLOR, f"{category} has no colour of its own"
            assert config["color"] == CATEGORY_COLOR[category], (
                f"{item_id} is a {category}, so it should be "
                f"{CATEGORY_COLOR[category]}, not {config['color']}"
            )

    def test_a_category_still_fits_in_the_patterns(self):
        """One colour per category only works while a category is smaller than
        the pattern list. When this fails, give the extra items a spare colour
        from the palette rather than repeating a pair."""
        counts = Counter(config["category"] for config in ITEMS.values())
        for category, count in counts.items():
            assert count <= len(PATTERNS), (
                f"{category} has {count} items and there are only "
                f"{len(PATTERNS)} patterns"
            )


class TestContainers:
    """A container is the ground, not a thing standing on it"""

    def test_no_container_has_a_look(self):
        data = json.loads((ITEMS_DIR / "containers.json").read_text())
        for container_id, config in data["containers"].items():
            assert "color" not in config, f"{container_id} should have no colour"
            assert "pattern" not in config, f"{container_id} should have no pattern"
