"""
Tests for items.py
"""

import pytest
from pydantic import ValidationError

from item_looks import CATEGORY_COLOR, PALETTE, PATTERNS
from items import SALE_CHANCE, Item, sale_price


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
