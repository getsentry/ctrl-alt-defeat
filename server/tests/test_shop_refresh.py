"""
Test shop refresh functionality
"""

import os

# Enable TEST_MODE for testing
os.environ["TEST_MODE"] = "true"

from tests.conftest import SHOP_SEED  # noqa: E402


class TestShopRefresh:
    def test_shop_always_has_five_items(self, auth_client):
        """Test that shop always generates exactly 5 items"""
        # Start session with deterministic seed
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )
        data = response.json()

        # Check initial shop
        shop = data["session"]["current_shop"]
        assert len(shop) == 5, "Shop should have exactly 5 slots"

        # Count non-null items
        item_count = sum(1 for item in shop if item is not None)
        assert item_count == 5, f"Shop should have 5 items, but has {item_count}"

        # Eight refreshes is what 13 gold buys once the price steps up after
        # the fourth, so this covers both prices without running dry.
        for i in range(8):
            response = auth_client.post("/shop/refresh", json={"round": 1})
            assert response.status_code == 200
            shop = response.json()["shop"]

            assert len(shop) == 5, f"Refresh {i}: Shop should have exactly 5 slots"
            item_count = sum(1 for item in shop if item is not None)
            assert (
                item_count == 5
            ), f"Refresh {i}: Shop should have 5 items, but has {item_count}"

    def test_shop_refresh_produces_different_items(self, auth_client):
        """Test that refreshing the shop produces different items"""
        # Start session with deterministic seed
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 100}
        )
        data = response.json()

        # Get initial shop
        initial_shop = data["session"]["current_shop"]
        initial_names = [item["name"] if item else None for item in initial_shop]

        # Refresh shop
        response = auth_client.post("/shop/refresh", json={"round": 1})
        assert response.status_code == 200

        refreshed_shop = response.json()["shop"]
        refreshed_names = [item["name"] if item else None for item in refreshed_shop]

        # Shops should be different
        assert (
            initial_names != refreshed_names
        ), "Shop refresh should produce different items"

        # Count how many items are the same
        same_count = sum(1 for i in range(5) if initial_names[i] == refreshed_names[i])
        assert same_count < 3, f"Too many items are the same ({same_count}/5)"

    def test_shop_refresh_costs_gold(self, auth_client):
        """Test that refreshing the shop costs 1 gold"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": None}
        )
        data = response.json()
        initial_gold = data["session"]["gold"]

        # First refresh (after initial shop) should cost 1 gold
        response = auth_client.post("/shop/refresh", json={"round": 1})
        assert response.status_code == 200

        new_gold = response.json()["gold"]
        assert new_gold == initial_gold - 1, "Shop refresh should cost 1 gold"

    def test_shop_refresh_deterministic_with_seed(self, auth_client):
        """Test that shop generation is deterministic with the same seed"""
        from fastapi.testclient import TestClient
        from main import app

        # Create two different guest accounts
        client1 = TestClient(app)
        client2 = TestClient(app)

        # Get guest tokens for both
        resp1 = client1.post("/auth/guest")
        resp2 = client2.post("/auth/guest")

        client1.headers["Authorization"] = f"Bearer {resp1.json()['access_token']}"
        client2.headers["Authorization"] = f"Bearer {resp2.json()['access_token']}"

        # Start two sessions with the same seed
        response1 = client1.post(
            "/session/start", json={"player_name": "test_player", "seed": 999}
        )
        shop1_initial = response1.json()["session"]["current_shop"]

        response2 = client2.post(
            "/session/start", json={"player_name": "test_player", "seed": 999}
        )
        shop2_initial = response2.json()["session"]["current_shop"]

        # Initial shops should be identical
        assert len(shop1_initial) == len(shop2_initial)
        for i in range(5):
            if shop1_initial[i] and shop2_initial[i]:
                assert shop1_initial[i]["name"] == shop2_initial[i]["name"]

        # Refresh both shops
        response1 = client1.post("/shop/refresh", json={"round": 1})
        shop1_refresh = response1.json()["shop"]

        response2 = client2.post("/shop/refresh", json={"round": 1})
        shop2_refresh = response2.json()["shop"]

        # Refreshed shops should also be identical
        for i in range(5):
            if shop1_refresh[i] and shop2_refresh[i]:
                assert shop1_refresh[i]["name"] == shop2_refresh[i]["name"]

        # But different from initial
        different_count = 0
        for i in range(5):
            if shop1_initial[i] and shop1_refresh[i]:
                if shop1_initial[i]["name"] != shop1_refresh[i]["name"]:
                    different_count += 1
        assert different_count > 0, "Refresh should produce different items"

    def test_shop_reset_on_new_round(self, auth_client):
        """Test that shop refresh counter resets when advancing to a new round"""
        # Start session with seed
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 500}
        )

        # Refresh shop a few times in round 1
        for _ in range(3):
            auth_client.post("/shop/refresh", json={"round": 1})

        # Get the third refresh shop
        response = auth_client.post("/shop/refresh", json={"round": 1})
        round1_shop = response.json()["shop"]

        # Purchase some items and battle to advance round
        session = auth_client.get("/session").json()
        shop = session["current_shop"]
        for i, item in enumerate(shop[:3]):
            if item:
                auth_client.post(
                    "/purchase/item",
                    json={
                        "item_id": item["id"],
                        "target_position": [2 + i, 3],
                    },
                )

        # Battle with easy AI to ensure win
        response = auth_client.post(
            "/battle/simulate",
            json={
                "seed": 42,
                "test_ai_difficulty": 1,  # Easy AI (1)
            },
        )
        assert response.status_code == 200
        result = response.json()

        # If we won, we should be on round 2 with reset counter
        if result["battle_result"]["winner"] == 1:
            # Get new round's shop
            new_shop = result["new_shop"]

            # This should be different from the heavily refreshed round 1 shop
            same_count = sum(
                1
                for i in range(5)
                if round1_shop[i]
                and new_shop[i]
                and round1_shop[i].get("name") == new_shop[i].get("name")
            )
            assert (
                same_count < 5
            ), "New round should have different shop than old round's refreshed shop"


if __name__ == "__main__":
    test = TestShopRefresh()
    test.test_shop_always_has_five_items()
    test.test_shop_refresh_produces_different_items()
    test.test_shop_refresh_costs_gold()
    test.test_shop_refresh_deterministic_with_seed()
    test.test_shop_reset_on_new_round()
    print("✅ All shop refresh tests passed!")


class TestRefreshCountAcrossRounds:
    """The roll counter belongs to a round, not to a winning streak"""

    def test_losing_a_battle_still_resets_the_roll_count(self, auth_client):
        """A loss used to carry the count into the next round.

        Rolls cost more once you have had four in a round, so carrying the
        count charged the higher price from the first roll of the next round,
        on top of the life the player had just lost.
        """
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": SHOP_SEED}
        )
        assert response.status_code == 200

        # Roll a few times so the count is definitely not zero
        for _ in range(3):
            assert (
                auth_client.post("/shop/refresh", json={"round": 1}).status_code == 200
            )
        assert auth_client.get("/session").json()["shop_refresh_count"] == 3

        # One cheap item, because a battle needs a non-empty grid, then lose
        # it. Difficulty 2 fields two items against our one; difficulty 3 is
        # unimplemented and returns None, which crashes the battle endpoint.
        shop = auth_client.get("/session").json()["current_shop"]
        cheapest = min(
            (i for i in shop if i and not i["is_container"]), key=lambda i: i["cost"]
        )
        assert (
            auth_client.post(
                "/purchase/item",
                json={"item_id": cheapest["id"], "target_position": [2, 3]},
            ).status_code
            == 200
        )

        response = auth_client.post(
            "/battle/simulate", json={"seed": 7, "test_ai_difficulty": 2}
        )
        assert response.status_code == 200
        assert response.json()["battle_result"]["winner"] == 2, "expected a loss"

        assert auth_client.get("/session").json()["shop_refresh_count"] == 0
