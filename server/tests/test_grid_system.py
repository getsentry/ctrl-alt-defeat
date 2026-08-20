"""
Tests for grid_system.py, and for the map format it reads.

An item's shape is written as a text map. See docs/item_grid_model.md for what
each character means.
"""

import pytest

from grid_system import BadMap, Rotation, parse_map, reach, zones_of





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

    def test_aura_holds_the_map_open_to_its_own_edge(self):
        """The blank-edge check counts every square the item reaches, not only
        the ones it covers, or a map drawn around a one square item would be
        trimmed down to the item and lose its reach."""
        assert parse_map(["***", "*#*", "***"], "amulet").squares == [(0, 0)]

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



class TestTheZonesAnItemReachesInto:
    """The star and diamond squares, in the item's own frame"""

    def test_a_zone_is_kept_apart_from_the_footprint(self):
        arrow = parse_map([".*+.", "+##*", ".*+."], "arrow")
        assert sorted(arrow.squares) == [(0, 0), (1, 0)]
        assert sorted(arrow.star) == [(0, -1), (0, 1), (2, 0)]
        assert sorted(arrow.diamond) == [(-1, 0), (1, -1), (1, 1)]

    def test_a_zone_above_the_item_is_negative(self):
        """Everything is offset from the item's corner, so a square the item
        reaches above itself is above the origin."""
        potion = parse_map(["*", "^", "#"], "potion")
        assert sorted(potion.squares) == [(0, 0), (0, 1)]
        assert sorted(potion.star) == [(0, -1)]

    def test_an_item_with_no_aura_has_empty_zones(self):
        # Empty rather than None, so a caller never has to check.
        blade = parse_map(["#", "#"], "blade")
        assert blade.star == ()
        assert blade.diamond == ()
        assert blade.anchors == ()


class TestTurningAnItemTurnsItsAura:
    """The trap: three lists, one frame"""

    def test_the_zone_turns_with_the_item(self):
        """Settled against the footprint's corner, not its own. Against its own
        the zone slides onto the item, which is silent and wrong."""
        potion = parse_map(["*", "^", "#"], "potion")
        turned = potion.rotate(Rotation.CLOCKWISE_90)
        assert sorted(turned.squares) == [(0, 0), (1, 0)], "now lying down"
        assert sorted(turned.star) == [(0, -1)], "still above the anchor"
        assert not set(turned.star) & set(turned.squares), "never on itself"

    def test_a_zone_that_does_not_anchor_simply_turns(self):
        # (x, y) -> (y, -x): the square to the right ends up above.
        item = parse_map(["#*"], "reaching right")
        assert sorted(item.star) == [(1, 0)]
        assert sorted(item.rotate(Rotation.CLOCKWISE_90).star) == [(0, -1)]

    def test_four_turns_come_back_to_the_start(self):
        for item_map in (["*", "^", "#"], ["#*"], ["***", "*#*", "***"], ["##", "#."]):
            shape = parse_map(item_map, "round trip")
            there = shape
            for _ in range(4):
                there = there.rotate(Rotation.CLOCKWISE_90)
            assert sorted(there.squares) == sorted(shape.squares), item_map
            assert sorted(there.star) == sorted(shape.star), item_map

    def test_an_anchor_keeps_pointing_up_however_the_item_is_turned(self):
        """The wiki draws Strong Heroic Potion three ways, and this is why: the
        star sits above whichever square the anchor lands on."""
        potion = parse_map(["*", "^", "#"], "potion")
        assert sorted(potion.rotate(Rotation.CLOCKWISE_90).star) == [(0, -1)]
        assert sorted(potion.rotate(Rotation.CLOCKWISE_270).star) == [(1, -1)]

    def test_an_anchor_pointing_into_the_item_reaches_nothing(self):
        """Upside down, the anchor's square is under the item's other square, so
        the projection is dropped and the item has no aura at all. The wiki
        never draws this orientation, which is the same fact."""
        potion = parse_map(["*", "^", "#"], "potion")
        assert potion.rotate(Rotation.CLOCKWISE_180).star == ()

    def test_an_anchor_does_not_project_twice(self):
        """The square an anchor projects into is drawn on the map, so it is in
        the star zone already. Turning has to drop it before turning, or the
        item ends up with the old square and the new one."""
        potion = parse_map(["*", "^", "#"], "potion")
        assert len(potion.rotate(Rotation.CLOCKWISE_90).star) == 1


class TestEveryAnchoredItemInTheCatalogue:
    """The anchor rule against the maps themselves.

    An anchor projects one square up and the projection is dropped where it
    lands on the item. If that is right, it reproduces the star squares each map
    already draws -- so the catalogue checks the rule rather than the other way
    round, and a thirteenth anchored item is covered the day it arrives.
    """

    @staticmethod
    def _anchored():
        import json
        from pathlib import Path

        items_dir = Path(__file__).parent.parent / "data" / "items"
        for path in sorted(items_dir.glob("*.json")):
            data = json.loads(path.read_text())
            for item_id, config in (data.get("items") or data["containers"]).items():
                if any("^" in row for row in config["map"]):
                    yield item_id, config["map"]

    def test_there_are_anchored_items_to_check(self):
        assert len(list(self._anchored())) >= 12

    def test_the_rule_draws_what_the_map_draws(self):
        def cells(item_map, wanted):
            return {
                (x, y)
                for y, row in enumerate(item_map)
                for x, c in enumerate(row)
                if c in wanted
            }

        for item_id, item_map in self._anchored():
            covered = cells(item_map, "#^")
            projected = {(x, y - 1) for x, y in cells(item_map, "^")} - covered
            assert projected == cells(item_map, "*"), item_id

    def test_each_one_parses_to_the_star_squares_it_draws(self):
        for item_id, item_map in self._anchored():
            shape = parse_map(item_map, item_id)
            assert shape.star, f"{item_id} draws a star and parsed to none"
            assert not set(shape.star) & set(shape.squares), item_id


class TestWhatAnAuraReaches:
    """Whose squares a zone lands on.

    `reach` answers in uids, because that is what tells two of the same item
    apart. The fixtures below use uid-shaped strings for the same reason: a
    readable word in that slot reads like a name, and a name would not do.
    """

    # Uid-shaped, and each one says what it is for while still being a uid.
    AMULET = "a0amulet"
    BLADE = "b1blade0"
    LONG = "c2long00"
    ARROW = "d3arrow0"
    POTION = "e4potion"
    LEFT = "f5left00"
    RIGHT = "a6right0"
    IN_STAR = "b7star00"
    IN_DIAMOND = "c8diamond"
    ONE = "d9one000"

    @staticmethod
    def _placed(*items):
        return [(uid, shape, at, Rotation.NONE) for uid, shape, at in items]

    def test_a_zone_landing_on_an_item_reaches_it(self):
        amulet = parse_map(["***", "*#*", "***"], "amulet")
        blade = parse_map(["#", "#"], "blade")
        reached = reach(self._placed((self.AMULET, amulet, (2, 2)), (self.BLADE, blade, (3, 1))))
        assert reached[self.AMULET]["star"] == [self.BLADE]

    def test_a_zone_landing_on_nothing_reaches_nothing(self):
        amulet = parse_map(["***", "*#*", "***"], "amulet")
        blade = parse_map(["#", "#"], "blade")
        reached = reach(self._placed((self.AMULET, amulet, (2, 2)), (self.BLADE, blade, (9, 9))))
        assert reached[self.AMULET]["star"] == []

    def test_an_item_never_reaches_itself(self):
        amulet = parse_map(["***", "*#*", "***"], "amulet")
        reached = reach(self._placed((self.AMULET, amulet, (2, 2))))
        assert reached[self.AMULET]["star"] == []

    def test_reaching_one_square_of_an_item_reaches_all_of_it(self):
        """An item is one thing. A zone clipping its corner has it."""
        amulet = parse_map(["***", "*#*", "***"], "amulet")
        long_item = parse_map(["####"], "long")
        reached = reach(self._placed((self.AMULET, amulet, (2, 2)), (self.LONG, long_item, (3, 1))))
        assert reached[self.AMULET]["star"] == [self.LONG]

    def test_the_two_zones_are_answered_separately(self):
        arrow = parse_map([".*+.", "+##*", ".*+."], "arrow")
        one = parse_map(["#"], "one")
        # (2, 0) of the arrow's star, and (-1, 0) of its diamond.
        reached = reach(self._placed(
            (self.ARROW, arrow, (4, 4)), (self.IN_STAR, one, (6, 4)), (self.IN_DIAMOND, one, (3, 4))
        ))
        assert reached[self.ARROW] == {"star": [self.IN_STAR], "diamond": [self.IN_DIAMOND]}

    def test_two_zones_crossing_is_not_a_reach(self):
        """A zone reaches the squares an item stands on, never its zone.

        Two amulets two apart share three squares of aura and neither stands in
        the other's, so neither reaches the other. If a zone reached a zone,
        every aura item on a board would reach every other one.
        """
        amulet = parse_map(["***", "*#*", "***"], "amulet")
        placements = self._placed((self.LEFT, amulet, (2, 5)), (self.RIGHT, amulet, (4, 5)))
        overlap = zones_of(amulet, (2, 5))["star"] & zones_of(amulet, (4, 5))["star"]
        assert overlap, "the fixture is wrong if the zones do not cross"

        reached = reach(placements)
        assert reached[self.LEFT]["star"] == []
        assert reached[self.RIGHT]["star"] == []

    def test_and_one_square_closer_they_do_reach(self):
        """The control. Without it the test above passes if reach never fires."""
        amulet = parse_map(["***", "*#*", "***"], "amulet")
        reached = reach(self._placed((self.LEFT, amulet, (2, 5)), (self.RIGHT, amulet, (3, 5))))
        assert reached[self.LEFT]["star"] == [self.RIGHT]
        assert reached[self.RIGHT]["star"] == [self.LEFT]

    def test_an_item_reached_several_times_is_listed_once(self):
        """A zone landing on three squares of one item has reached one item.

        It holds because the answer is built by walking the items and asking
        whether the zone touches each. Built by walking the zone instead it
        would list the same item once per square, and an effect reading it
        would apply three times.
        """
        cross = parse_map(["..*..", ".***.", "**#**", ".***.", "..*.."], "cross")
        long_item = parse_map(["####"], "long")

        landing_on_it = zones_of(cross, (4, 4))["star"] & {
            (2, 3), (3, 3), (4, 3), (5, 3)
        }
        assert len(landing_on_it) == 3, "the fixture wants several squares to land"

        reached = reach(self._placed((self.ARROW, cross, (4, 4)), (self.LONG, long_item, (2, 3))))
        assert reached[self.ARROW]["star"] == [self.LONG]

    def test_two_of_the_same_item_are_told_apart(self):
        """Copies share a type and a name, so the answer is in uids.

        BattleItem gives each instance a fresh uid for exactly this: two Health
        Potions on one board are two things, and a zone can reach one without
        reaching the other.
        """
        amulet = parse_map(["***", "*#*", "***"], "amulet")
        one = parse_map(["#"], "one")
        near, far = "aa11near", "bb22far0"

        reached = reach(self._placed(
            (self.AMULET, amulet, (2, 2)), (near, one, (3, 2)), (far, one, (9, 9))
        ))
        assert reached[self.AMULET]["star"] == [near], "the same shape, told apart"
        assert far in reached, "and the far copy still gets its own answer"

    def test_a_zone_reaching_several_items_lists_them_all(self):
        """One zone, several separate items in it.

        The amulet's ring covers eight squares and three different items are
        standing in it, so all three come back. Every other case here has at
        most one item in a zone, which would pass just as well if the answer
        stopped at the first one it found.
        """
        amulet = parse_map(["***", "*#*", "***"], "amulet")
        one = parse_map(["#"], "one")
        # Three of the eight ring squares around (2, 2).
        north, east, corner = "aa11north", "bb22east0", "cc33corner"

        reached = reach(self._placed(
            (self.AMULET, amulet, (2, 2)),
            (north, one, (2, 1)),
            (east, one, (3, 2)),
            (corner, one, (1, 3)),
        ))
        assert reached[self.AMULET]["star"] == sorted([north, east, corner])

    def test_each_zone_lists_everything_in_it_separately(self):
        """Both zones at once, with more than one item in each.

        The arrow reaches three squares with its star and three with its
        diamond. Two items stand in each, and neither zone borrows from the
        other.
        """
        arrow = parse_map([".*+.", "+##*", ".*+."], "arrow")
        one = parse_map(["#"], "one")
        # star at (4, 3) (4, 5) (6, 4); diamond at (3, 4) (5, 3) (5, 5).
        star_a, star_b = "aa11star0", "bb22star0"
        diamond_a, diamond_b = "cc33diam0", "dd44diam0"

        reached = reach(self._placed(
            (self.ARROW, arrow, (4, 4)),
            (star_a, one, (4, 3)),
            (star_b, one, (6, 4)),
            (diamond_a, one, (3, 4)),
            (diamond_b, one, (5, 5)),
        ))
        assert reached[self.ARROW] == {
            "star": sorted([star_a, star_b]),
            "diamond": sorted([diamond_a, diamond_b]),
        }

    def test_a_zone_reaching_two_items_and_one_of_its_own_squares(self):
        """A big item and a small one in the same zone.

        Sizes differ, so this also says the answer is one entry per item rather
        than per square: the long item fills three of the ring's squares and is
        listed once beside the single-square item.
        """
        amulet = parse_map(["***", "*#*", "***"], "amulet")
        one = parse_map(["#"], "one")
        long_item = parse_map(["###"], "long")
        small, big = "aa11small", "bb22big00"

        reached = reach(self._placed(
            (self.AMULET, amulet, (2, 2)),
            (small, one, (2, 1)),
            (big, long_item, (1, 3)),
        ))
        assert reached[self.AMULET]["star"] == sorted([small, big])

    def test_every_item_gets_an_answer(self):
        """Even one with no aura, so a caller never guesses what a missing key
        means."""
        blade = parse_map(["#", "#"], "blade")
        reached = reach(self._placed((self.BLADE, blade, (0, 0))))
        assert reached == {self.BLADE: {"star": [], "diamond": []}}

    def test_turning_an_item_changes_what_it_reaches(self):
        potion = parse_map(["*", "^", "#"], "potion")
        one = parse_map(["#"], "one")
        above = [(self.POTION, potion, (4, 4), Rotation.NONE), (self.ONE, one, (4, 3))]
        # Upright the star is above the anchor at (4, 3).
        assert reach([above[0], (*above[1], Rotation.NONE)])[self.POTION]["star"] == [self.ONE]
        # Turned upside down it has no aura at all, so it reaches nothing.
        assert reach([
            (self.POTION, potion, (4, 4), Rotation.CLOCKWISE_180),
            (self.ONE, one, (4, 3), Rotation.NONE),
        ])[self.POTION]["star"] == []


class TestTheCatalogueAgreesWithTheDesign:
    """GDD 4.3 quotes two numbers. They came from here, so they can drift."""

    @staticmethod
    def _shapes():
        from config_loader import config_loader

        return {slug: spec.shape for slug, spec in config_loader.items.items()}

    def test_the_number_of_items_projecting_an_aura(self):
        projecting = [s for s in self._shapes().values() if s.star or s.diamond]
        assert len(projecting) == 117, (
            f"{len(projecting)} items project an aura; GDD 4.3 says 117"
        )

    def test_the_number_reaching_past_their_own_neighbours(self):
        """The figure the design uses to say adjacency is not a substitute."""
        beyond = 0
        for shape in self._shapes().values():
            zone = set(shape.star) | set(shape.diamond)
            if not zone:
                continue
            covered = set(shape.squares)
            neighbours = {
                (x + dx, y + dy)
                for x, y in covered
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            } - covered
            if zone - neighbours:
                beyond += 1
        assert beyond == 41, f"{beyond} reach past their neighbours; GDD 4.3 says 41"


class TestAnAnchorIsStillPartOfTheItem:
    """An `^` marks a square the item stands on, not a separate kind of square.

    Everything about placement follows from that: an item covers its anchors, so
    nothing else can be put there. It holds because `parse_map` reads `#` and `^`
    into one set of covered squares, which is easy to break by accident, so it is
    asserted here rather than left to be noticed in play.
    """

    def test_an_anchor_is_one_of_the_squares_the_item_covers(self):
        potion = parse_map(["*", "^", "#"], "potion")
        assert len(potion.squares) == 2, "the ^ and the # are both squares"
        assert set(potion.anchors) <= set(potion.squares)

    def test_every_anchored_item_in_the_catalogue_covers_its_anchors(self):
        from config_loader import config_loader

        checked = 0
        for slug, spec in config_loader.items.items():
            if not spec.shape.anchors:
                continue
            checked += 1
            assert set(spec.shape.anchors) <= set(spec.shape.squares), (
                f"{slug} anchors a square it does not stand on"
            )
        assert checked >= 12, f"only {checked} anchored items found"

    def test_an_anchor_stays_in_the_footprint_through_a_turn(self):
        potion = parse_map(["*", "^", "#"], "potion")
        for rotation in Rotation:
            turned = potion.rotate(rotation)
            assert set(turned.anchors) <= set(turned.squares), rotation

    def test_nothing_can_be_placed_on_an_anchor_square(self):
        """The reason any of the above matters."""
        from containers import Container, PlacementValidator

        validator = PlacementValidator()
        validator.add_container(Container.of("mesh_network_hub", (0, 0), "hub"))

        potion = parse_map(["*", "^", "#"], "potion")
        assert validator.place_item((1, 1), potion)

        one = parse_map(["#"], "one square")
        assert not validator.validate_item_placement((1, 1), one), "the anchor square"
        assert not validator.validate_item_placement((1, 2), one), "the other square"
        # The zone is not the item, so an item may stand where an aura reaches.
        assert validator.validate_item_placement((1, 0), one), "the star square"
