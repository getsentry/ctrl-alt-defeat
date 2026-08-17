"""
Tests for items.py
"""

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
