"""What a player's items do between battles.

The battle simulator answers a clock and events; the shop answers a round
beginning and an item changing hands. Neither exists here, so the shop phase
has an applier of its own and this tests that rather than the engine.
"""
import pytest
from battle_engine import ITEM_CATALOG
from grid_system import parse_map
from item_effects import (
    GoldEffect,
    ItemSpec,
    PassiveTrigger,
    SaleChanceEffect,
    ShopEnteredTrigger,
)
from shop_phase import entering_the_shop, sale_chance_from


def _item(uid, triggers):
    return ItemSpec(
        id=uid,
        name=uid,
        category="protocol",
        cost=1,
        player_class="neutral",
        slug=uid,
        shape=parse_map(["#"], uid),
        triggers=triggers,
    )


class TestTheShopOpening:
    """ "Shop entered: Gain 3 Gold\" """

    def test_an_item_hands_over_its_gold(self):
        got = entering_the_shop(
            [_item("a", [ShopEnteredTrigger(effects=[GoldEffect(amount=3)])])]
        )
        assert got.gold == 3

    def test_every_item_that_says_so_is_counted(self):
        got = entering_the_shop(
            [
                _item("a", [ShopEnteredTrigger(effects=[GoldEffect(amount=3)])]),
                _item("b", [ShopEnteredTrigger(effects=[GoldEffect(amount=1)])]),
            ]
        )
        assert got.gold == 4

    def test_an_item_that_says_nothing_gives_nothing(self):
        assert entering_the_shop([_item("a", [])]).gold == 0

    def test_it_says_what_it_did(self):
        """The player is told, so gold appearing has a reason attached."""
        got = entering_the_shop(
            [_item("a", [ShopEnteredTrigger(effects=[GoldEffect(amount=3)])])]
        )
        assert got.said == ["a: +3 gold"]

    def test_a_battle_trigger_is_not_a_shop_trigger(self):
        """A passive is on during a battle and says nothing about the shop."""
        got = entering_the_shop(
            [_item("a", [PassiveTrigger(effects=[GoldEffect(amount=99)])])]
        )
        assert got.gold == 0


class TestTheChanceOfASale:
    """ "Sale chance +3%." It stands for as long as the item is held."""

    def test_an_item_adds_to_the_chance(self):
        assert sale_chance_from(
            [_item("a", [PassiveTrigger(effects=[SaleChanceEffect(amount=0.03)])])]
        ) == pytest.approx(0.03)

    def test_two_of_them_add_together(self):
        held = [
            _item("a", [PassiveTrigger(effects=[SaleChanceEffect(0.03)])]),
            _item("b", [PassiveTrigger(effects=[SaleChanceEffect(0.10)])]),
        ]
        assert sale_chance_from(held) == pytest.approx(0.13)

    def test_holding_nothing_changes_nothing(self):
        assert sale_chance_from([_item("a", [])]) == 0.0

    def test_the_shop_marks_more_down_when_one_is_held(self):
        """End to end: the same seed, and the shop is more generous."""
        import os

        os.environ.setdefault("TEST_MODE", "1")
        from main import generate_shop_items

        def sales(held):
            return sum(
                1
                for seed in range(300)
                for item in generate_shop_items(5, seed=seed, held=held)
                if item and item.on_sale
            )

        assert sales({"maneki_neko"}) > sales(set())


class TestTheCatalogueUsesIt:
    def test_gold_armor_pays_out_when_the_shop_opens(self):
        got = entering_the_shop([ITEM_CATALOG["gold_armor"]])
        assert got.gold == 3

    def test_the_lucky_cat_makes_sales_likelier(self):
        assert sale_chance_from([ITEM_CATALOG["maneki_neko"]]) == pytest.approx(0.03)

    def test_holding_all_three_gold_items_pays_all_three(self):
        got = entering_the_shop(
            [ITEM_CATALOG[k] for k in ("gold_armor", "bitcoin_wallet", "lucky_piggy")]
        )
        assert got.gold == 5


class TestTheGoldReachesThePlayer:
    """The applier is one thing and the shop actually paying is another.

    Every test above asks `entering_the_shop` what should happen. None of them
    asked whether the session ever sees it, and a mutation that dropped the
    gold on the floor went unnoticed because of that.
    """

    def _session(self, auth_client, name="shopper"):
        response = auth_client.post("/session/start", json={"player_name": name})
        assert response.status_code == 200
        return response.json()["session"]

    def _fight(self, auth_client):
        response = auth_client.post("/battle/simulate", json={})
        assert response.status_code == 200, response.json()
        return response.json()

    def test_a_gold_item_pays_out_over_the_round_reward(self, auth_client):
        """Bitcoin Wallet says "Shop entered: Gain 1 Gold", so a round with
        it on the rack ends one richer than a round without.

        Not Gold Armor, which says 3 and is two squares by three: the starting
        racks are two rows tall and it does not fit on one.
        """

        # Both sides need something to fight with, so they differ only in
        # whether the armour is there.
        def gold_after(items):
            session = self._session(auth_client, name=f"p{len(items)}")
            got = auth_client.post(
                "/test/rack",
                json={
                    "player_id": session["player_id"],
                    "items": [{"item_type": t, "position": p} for t, p in items],
                },
            )
            assert got.status_code == 200, got.json()
            before = auth_client.get("/session").json()["gold"]
            self._fight(auth_client)
            return auth_client.get("/session").json()["gold"] - before

        plain = gold_after([("firewall", [2, 3])])
        with_wallet = gold_after([("firewall", [2, 3]), ("bitcoin_wallet", [4, 3])])
        assert (
            with_wallet == plain + 1
        ), "the round's gold, and the one the wallet says it gives"


class TestItOnlyPaysOnceARound:
    """The shop opening is a moment in the round, not a screen being looked at.

    A player who leaves the shop and comes back has not entered a new round,
    and an item that pays on entering must not pay again. This holds here for
    a structural reason rather than a guard: it fires where the round advances,
    and nothing else fires it.
    """

    def _start(self, auth_client, name):
        r = auth_client.post("/session/start", json={"player_name": name})
        assert r.status_code == 200
        session = r.json()["session"]
        got = auth_client.post(
            "/test/rack",
            json={
                "player_id": session["player_id"],
                "items": [
                    {"item_type": "firewall", "position": [2, 3]},
                    {"item_type": "bitcoin_wallet", "position": [4, 3]},
                ],
            },
        )
        assert got.status_code == 200, got.json()
        return session

    def _gold(self, auth_client):
        return auth_client.get("/session").json()["gold"]

    def test_rerolling_the_shop_pays_nothing(self, auth_client):
        """The obvious way to abuse it: roll the shop over and over.

        Counted exactly rather than "no more than before". A reroll costs a
        gold, so an item paying one on every roll would come out even, and a
        test asking only that the player is no richer would see nothing wrong.
        """
        self._start(auth_client, "roller")
        auth_client.post("/battle/simulate", json={})
        after_battle = self._gold(auth_client)
        rolls = 3
        for _ in range(rolls):
            got = auth_client.post("/shop/refresh", json={})
            assert got.status_code == 200, got.json()
        # A gold each for the first four rolls of a round, and nothing back.
        assert self._gold(auth_client) == after_battle - rolls

    def test_looking_at_the_session_again_pays_nothing(self, auth_client):
        """Reading the session is what a client does on every screen."""
        self._start(auth_client, "looker")
        auth_client.post("/battle/simulate", json={})
        first = self._gold(auth_client)
        for _ in range(4):
            auth_client.get("/session")
        assert self._gold(auth_client) == first

    def test_a_second_round_pays_a_second_time(self, auth_client):
        """It is once a round, not once a game."""
        self._start(auth_client, "twice")
        before = self._gold(auth_client)
        auth_client.post("/battle/simulate", json={})
        one = self._gold(auth_client) - before
        auth_client.post("/battle/simulate", json={})
        two = self._gold(auth_client) - before - one
        # The round's own gold differs between rounds; the wallet's 1 does not.
        assert one >= 1 and two >= 1
