"""
Tests for grid_system.py, and for the map format it reads.

An item's shape is written as a text map. See docs/item_grid_model.md for what
each character means.
"""

import pytest

from grid_system import BadMap, parse_map





class TestParsingAMap:
    """Reading the squares an item covers out of its text map"""

    def test_a_rectangle(self):
        assert sorted(parse_map(["##", "##"], "square").squares) == [(0, 0), (0, 1), (1, 0), (1, 1)]

    def test_a_plus(self):
        # The shape a 2x2 could never say. Four arms and a middle, five squares
        # inside a 3x3 box.
        plus = parse_map([".#.", "###", ".#."], "plus")
        assert sorted(plus.squares) == [(0, 1), (1, 0), (1, 1), (1, 2), (2, 1)]

    def test_an_l(self):
        assert sorted(parse_map(["#.", "#.", "##"], "L").squares) == [
            (0, 0), (0, 1), (0, 2), (1, 2)
        ]

    def test_a_shape_with_a_hole(self):
        # Utility Pouch is a 3x3 ring. The hole is not covered, so nothing can
        # be placed on it and nothing of the item sits there.
        ring = parse_map(["###", "###", "#.#"], "ring")
        assert (1, 2) not in ring.squares
        assert len(ring.squares) == 8

    def test_aura_is_not_part_of_the_item(self):
        """A star or diamond square is one the item reaches into, not one it
        covers. Counting them would make every item too big to place."""
        arrow = parse_map([".*+.", "+##*", ".*+."], "arrow")
        assert sorted(arrow.squares) == [(0, 0), (1, 0)]

    def test_offsets_start_at_the_item_not_the_map(self):
        # The map is taller than the potion, because the star sits above it.
        potion = parse_map(["*", "^", "#"], "potion")
        assert sorted(potion.squares) == [(0, 0), (0, 1)]

    def test_an_anchor_is_a_covered_square(self):
        assert len(parse_map(["*", "^", "^"], "stones").squares) == 2


class TestRefusingABadMap:
    """A mistyped map is refused, never guessed at"""

    def test_rows_of_different_widths(self):
        with pytest.raises(BadMap, match="wide"):
            parse_map(["##", "#"], "ragged")

    def test_nothing_covered(self):
        with pytest.raises(BadMap, match="no covered squares"):
            parse_map(["**", "**"], "aura only")

    def test_squares_in_two_pieces(self):
        # Two separate blobs are two items, and placing them as one would
        # occupy a square between them that the item does not cover.
        with pytest.raises(BadMap, match="more than one piece"):
            parse_map(["#.#"], "split")

    def test_a_blank_edge(self):
        # Trimmed, so that two maps of the same shape are the same text.
        with pytest.raises(BadMap, match="Trim"):
            parse_map(["..", "##"], "padded")

    def test_a_character_that_means_nothing(self):
        with pytest.raises(BadMap, match="not a character"):
            parse_map(["#?"], "typo")

    def test_no_rows_at_all(self):
        with pytest.raises(BadMap):
            parse_map([], "empty")


class TestTheCatalogueLoads:
    """Every item in the game has a map that parses"""

    def test_every_item_has_a_shape(self):
        from config_loader import config_loader

        for item_id, spec in config_loader.items.items():
            assert spec.shape.squares, f"{item_id} covers no squares"

    def test_the_catalogue_holds_irregular_shapes(self):
        """The point of the map format. If this ever finds none, either the
        catalogue lost them or something flattened them back to rectangles."""
        from config_loader import config_loader

        irregular = []
        for item_id, spec in config_loader.items.items():
            squares = spec.shape.squares
            width = max(x for x, _ in squares) + 1
            height = max(y for _, y in squares) + 1
            if len(squares) != width * height:
                irregular.append(item_id)
        assert len(irregular) > 3, f"Only {irregular} are not rectangles"

