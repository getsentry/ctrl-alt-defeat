"""
Tests for items.py
"""

import json
import re
from pathlib import Path
from typing import Dict, Set

import pytest
from pydantic import ValidationError

from config_loader import config_loader
from item_looks import CATEGORY_COLOR, PALETTE, PATTERNS
from items import ZONE_FIELDS, ZoneWants, SALE_CHANCE, Item, sale_price


class TestSalePrice:
    """Half price, rounded up, as Backpack Battles does it"""

    def test_even_cost_halves(self):
        assert sale_price(8) == 4

    def test_odd_cost_rounds_up(self):
        # Rounding down would let a 3 gold item sell for 1 and buy for 1,
        # and a 1 gold item sell for nothing at all.
        assert sale_price(3) == 2
        assert sale_price(1) == 1

    def test_never_free(self):
        assert sale_price(0) == 0
        for cost in range(1, 40):
            assert sale_price(cost) >= 1


class TestItemPricing:
    """What an item costs to buy and what it pays to sell"""

    def test_full_price_by_default(self):
        item = Item.of("null_blade", "test")
        assert item.on_sale is False
        assert item.price == item.cost

    def test_a_sale_halves_the_price(self):
        item = Item.of("null_blade", "test", on_sale=True)
        assert item.price == sale_price(item.cost)
        assert item.price < item.cost or item.cost <= 1

    def test_selling_pays_half_whether_or_not_it_was_on_sale(self):
        full = Item.of("null_blade", "test")
        discounted = Item.of("null_blade", "test", on_sale=True)
        assert full.sell_value == discounted.sell_value == sale_price(full.cost)

    def test_cost_comes_from_the_catalogue(self):
        # Not from a rarity table. Costs are the source item's.
        from config_loader import config_loader

        item = Item.of("null_blade", "test")
        assert item.cost == config_loader.items["null_blade"].cost

    def test_buying_ends_the_sale(self):
        """A sale belongs to the shop offer, not to the item.

        Once bought, the item is worth what it has always been worth. Leaving
        the flag on meant a bought item reported the discounted price for the
        rest of the game.
        """
        offer = Item.of("null_blade", "test", on_sale=True)
        owned = offer.model_copy(update={"on_sale": False})
        assert owned.price == owned.cost
        assert owned.sell_value == sale_price(owned.cost)


class TestShopSales:
    """The shop rolls sales from its own seed"""

    def test_the_same_seed_gives_the_same_sales(self):
        from main import generate_shop_items

        first = generate_shop_items(1, 777)
        second = generate_shop_items(1, 777)
        assert [(i.item_type, i.on_sale, i.price) for i in first] == [
            (i.item_type, i.on_sale, i.price) for i in second
        ]

    def test_roughly_one_item_in_ten_is_on_sale(self):
        from main import generate_shop_items

        items = [item for seed in range(400) for item in generate_shop_items(1, seed)]
        rate = sum(item.on_sale for item in items) / len(items)
        # 2000 items, so a wide band still catches a mechanic that is off by
        # a factor rather than by noise.
        assert SALE_CHANCE - 0.03 < rate < SALE_CHANCE + 0.03

    def test_an_item_on_sale_is_offered_at_half_price(self):
        from main import generate_shop_items

        for seed in range(200):
            for item in generate_shop_items(1, seed):
                if item.on_sale:
                    assert item.price == sale_price(item.cost)
                    return
        raise AssertionError("200 seeds produced no sale, which cannot be right")


class TestTheLookOnTheWire:
    """What the client receives, as against what the catalogue holds.

    Item.of is the one place that reads a spec, so it is where the catalogue's
    shorthand turns into what the client is actually sent.
    """

    def test_the_colour_is_sent_as_a_value(self):
        """The catalogue says "red". The client is sent "#BE0032", so that it
        needs no palette of its own and a colour can be retuned without
        shipping a new client."""
        item = Item.of("null_blade", "test_id")
        assert item.color == PALETTE[CATEGORY_COLOR["problem"]]
        assert item.color.startswith("#")

    def test_the_pattern_is_sent_as_a_name(self):
        """A pattern cannot be sent as a value. The client draws it, so it can
        only be told which one to draw."""
        item = Item.of("null_blade", "test_id")
        assert item.pattern == "solid"

    def test_two_items_of_a_category_share_the_colour(self):
        one = Item.of("null_blade", "one")
        another = Item.of("denier_of_service", "another")
        assert one.category == another.category == "problem"
        assert one.color == another.color
        assert one.pattern != another.pattern

    def test_a_container_has_no_look(self):
        """A container is the ground the items sit on, and is drawn as such."""
        container = Item.of("standard_vm", "test_id")
        assert container.is_container
        assert container.color == ""
        assert container.pattern == ""

    def test_a_placed_item_keeps_its_look(self):
        placed = Item.of("null_blade", "test_id").placed_at((2, 3))
        assert placed.color == PALETTE[CATEGORY_COLOR["problem"]]
        assert placed.pattern == "solid"

    def test_an_item_put_back_in_the_chest_keeps_its_look(self):
        stored = Item.of("null_blade", "test_id").placed_at((2, 3)).stored()
        assert stored.color == PALETTE[CATEGORY_COLOR["problem"]]
        assert stored.pattern == "solid"


class TestTheLookIsCheckedOnTheWayOut:
    """The client draws what it is given without checking it.

    It has no palette to compare a colour against and no way to ask what a
    pattern name means, so a look it cannot draw has to be refused here.
    """

    def _rebuilt(self, **changes) -> Item:
        """An item put back through validation with something changed."""
        fields = Item.of("null_blade", "test_id").model_dump()
        fields.update(changes)
        return Item.model_validate(fields)

    def test_refuses_a_colour_that_is_not_a_value(self):
        # The name is what the catalogue holds. Sending it would leave the
        # client with a string it cannot turn into a colour.
        with pytest.raises(ValidationError):
            self._rebuilt(color="red")

    def test_refuses_a_colour_that_is_not_six_digits(self):
        with pytest.raises(ValidationError):
            self._rebuilt(color="#BE003")

    def test_refuses_something_that_is_not_a_colour_at_all(self):
        with pytest.raises(ValidationError):
            self._rebuilt(color="rgb(190, 0, 50)")

    def test_allows_no_colour_at_all(self):
        # A container has none, and that is not an error.
        assert self._rebuilt(color="").color == ""

    def test_refuses_a_pattern_the_client_cannot_draw(self):
        with pytest.raises(ValidationError, match="not a pattern the client can draw"):
            self._rebuilt(pattern="tartan")

    def test_allows_no_pattern_at_all(self):
        assert self._rebuilt(pattern="").pattern == ""

    def test_allows_every_pattern_there_is(self):
        for name in PATTERNS:
            assert self._rebuilt(pattern=name).pattern == name


class TestWhatAnAuraActsOn:
    """GDD 4.4: a zone reaches everything standing in it, or only the items
    carrying a tag. The client is sent both, so it can show a player which
    items an aura would really act on rather than which squares it covers.
    """

    @staticmethod
    def _named(name: str) -> str:
        return next(
            slug for slug, spec in config_loader.items.items() if spec.name == name
        )

    def test_a_narrowed_zone_says_what_it_wants(self):
        # Script Kitty: "Star Pets and Star Scripts trigger faster".
        item = Item.of(self._named("Script Kitty"), "x")

        assert item.aura["star"][0].any_of == ["pet", "script"]
        assert item.aura["star"][0].all_of == []

    def test_a_zone_that_reaches_everything_is_present_and_empty(self):
        """Present and empty is not the same as absent: one lights up when
        anything stands in it, the other never lights up at all."""
        # Klaxon: "Triggers 10% faster for each Star item".
        item = Item.of(self._named("Klaxon"), "x")

        assert item.aura["star"] == [ZoneWants()]

    def test_a_zone_nothing_acts_through_is_absent(self):
        """68 of the 117 items that draw a zone have no aura clause built
        yet. Their zone is real and does nothing, and the client has to be
        able to tell that from a zone that acts on everything."""
        # Cold Wallet draws four squares and has no trigger at all.
        item = Item.of(self._named("Cold Wallet"), "x")

        assert item.star, "it draws a zone"
        assert item.aura == {}, "and nothing acts through it"

    def test_a_zone_an_effect_lands_on_says_what_it_wants(self):
        """The commonest way to write an aura, and the one that was silent.

        "Star Weapons gain 1 damage" is a gain_damage landing on `target:
        star`, not a trigger watching a `zone`. 21 items are written that way,
        and every one of them drew a zone the client could make nothing of --
        so no weapon ever lit up under an Edge Cache.
        """
        item = Item.of(self._named("Edge Cache"), "x")

        assert set(item.aura["star"][0].any_of) == {"melee", "ranged", "magic"}, (
            "the three kinds a player calls a weapon"
        )

    def test_a_zone_counted_in_says_what_it_wants(self):
        """The third field, `where`: an effect counting what stands in the
        zone rather than reaching into it.

        Halo Crystal blocks once for each Star Holy item. Nothing reaches out
        of the zone, so nothing named it a `zone` or a `target`, and the
        client was left with twelve squares and no reason for them.
        """
        item = Item.of(self._named("Halo Crystal"), "x")

        assert item.aura["star"], "twelve squares, and now a reason for them"

    def test_both_zones_are_answered_separately(self):
        # CI Cauldron counts Star Potions and Diamond Foods separately.
        item = Item.of(self._named("CI Cauldron"), "x")

        assert item.aura["star"][0].any_of == ["patch"]
        assert item.aura["diamond"][0].any_of == ["script"]

    def test_an_item_carries_its_kinds_lowered(self):
        """A tag is a kind or a category, so the client needs the kinds to
        match one. Lowered here, so the catalogue's casing never reaches it."""
        item = Item.of(self._named("Thermal Throttle"), "x")

        # `weapon` among them because the wiki's own `type` field is imported
        # as a kind now, which is what gives "Star Weapons", "Star Food" and
        # "Star Potion" something to match on.
        assert item.kinds == ["fire", "ranged", "treasure", "weapon"]
        assert item.category == "problem", "and the category it matches on too"

    def test_the_client_is_told_about_every_zone_the_engine_reaches_through(self):
        """The rule that stops this going quiet again.

        An effect names its zone in whichever field reads as English for that
        effect, and the engine reads all of them: it reaches through
        `target_type` and `where`, and watches a `zone`. `aura_of` read only
        `zone`, so what the client was told and what the engine did had
        drifted apart -- 21 items lit up nothing while their effect landed
        every battle.

        Read off the engine rather than restated here: a new effect that names
        its zone in a fourth field fails this the day it is written, instead
        of shipping an aura the player can see no reason for.
        """
        engine = (Path(__file__).parent.parent / "battle_engine.py").read_text()
        reached_through = set(
            re.findall(r"(?:_reached_by|aura_squares)\(\s*\n?\s*\w+\.(\w+)", engine)
        )

        assert reached_through, "setup: the engine reaches through a zone somewhere"
        assert reached_through <= set(ZONE_FIELDS), (
            f"the engine reaches through {sorted(reached_through - set(ZONE_FIELDS))}, "
            f"which aura_of never looks at, so the client is never told about it"
        )

    def test_every_zone_the_catalogue_acts_through_is_answered(self):
        """A clause with a zone the client is never told about is an aura the
        player cannot see the point of.

        Read off the JSON rather than off the loaded spec, so this asks what
        the catalogue says and not what the loader made of it. An effect names
        its zone in whichever of `zone`, `target` and `where` reads as English
        for that effect -- a modifier lands on a target, a count is taken
        where, an aura trigger watches a zone -- and all three are the same
        two words. Reading only `zone` is how Edge Cache came to send a client
        a star it could make nothing of.
        """
        acting = 0
        for slug, zones in self._zones_in_the_json().items():
            acting += 1
            assert set(Item.of(slug, "x").aura) == zones, slug
        assert acting > 10, "setup: some items really do act through a zone"

    @staticmethod
    def _zones_in_the_json() -> Dict[str, Set[str]]:
        """Which zones each item's own JSON names, by slug.

        Every value of every field, at any depth: an effect can sit behind a
        chance roll, and the JSON is the same shape either way.
        """
        found: Dict[str, Set[str]] = {}
        for path in sorted((Path(__file__).parent.parent / "data" / "items").glob("*.json")):
            data = json.loads(path.read_text())
            # The containers file keeps its own key, and no container carries
            # a trigger, so there is nothing in it to find.
            for item_id, config in (data.get("items") or {}).items():
                zones = set()

                def walk(node):
                    if isinstance(node, dict):
                        for field in ("zone", "target", "where"):
                            if node.get(field) in ("star", "diamond"):
                                zones.add(node[field])
                        for value in node.values():
                            walk(value)
                    elif isinstance(node, list):
                        for value in node:
                            walk(value)

                walk(config.get("triggers"))
                if zones:
                    found[item_id] = zones
        return found
