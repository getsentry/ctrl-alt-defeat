"""
Tests for purchase validation and placement
"""

import pytest

from tests.conftest import SHOP_SEED


class TestPurchaseValidation:
    """Test purchase request validation and item placement"""

    def test_purchase_to_storage(self, auth_client):
        """Test purchasing an item to storage"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )
        data = response.json()

        # Get shop
        session = data["session"]
        shop = session["current_shop"]
        initial_gold = session["gold"]

        # Find first non-null item
        shop_item = None
        for item in shop:
            if item is not None:
                shop_item = item
                break

        assert shop_item is not None

        # Purchase to storage
        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": shop_item["id"],
                "target_position": None,
                "to_storage": True,
            },
        )

        assert response.status_code == 200
        result = response.json()

        # Check response
        assert result["gold"] == initial_gold - shop_item["cost"]

        # Verify item is in storage
        session_response = auth_client.get("/session")
        updated_session = session_response.json()

        assert len(updated_session["inventory_storage"]) == 1
        assert updated_session["inventory_storage"][0]["id"] == shop_item["id"]
        assert updated_session["gold"] == initial_gold - shop_item["cost"]

    def test_purchase_to_grid(self, auth_client):
        """Test purchasing an item to grid coordinates"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )
        data = response.json()

        # Get shop
        session = data["session"]
        shop = session["current_shop"]

        # Find first non-null item
        shop_item = None
        for item in shop:
            if item is not None:
                shop_item = item
                break

        # Purchase to grid (on first container)
        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": shop_item["id"],
                "target_position": [2, 3],
            },
        )

        assert response.status_code == 200

        # Verify item is on grid
        session_response = auth_client.get("/session")
        updated_session = session_response.json()

        assert len(updated_session["inventory_grid"]) == 1
        assert updated_session["inventory_grid"][0]["id"] == shop_item["id"]
        assert updated_session["inventory_grid"][0]["position"] == [2, 3]

    def test_purchase_invalid_coordinates(self, auth_client):
        """Test that invalid grid coordinates are rejected"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )
        data = response.json()

        # Get shop
        session = data["session"]
        shop = session["current_shop"]

        # Find first non-null item
        shop_item = None
        for item in shop:
            if item is not None:
                shop_item = item
                break

        # Try to place off the server containers
        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": shop_item["id"],
                "target_position": [0, 0],
            },
        )

        assert response.status_code == 400
        detail = response.json()["detail"].lower()
        assert (
            "not on a server container" in detail
            or "invalid placement" in detail
            or "not fit entirely on server containers" in detail
        )

    def test_purchase_overlapping_item(self, auth_client):
        """Test that overlapping items are rejected"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )
        data = response.json()

        # Get shop
        session = data["session"]
        shop = session["current_shop"]

        # Find two non-null items
        items = [item for item in shop if item is not None]
        assert len(items) >= 2

        # Purchase first item
        response1 = auth_client.post(
            "/purchase/item",
            json={
                "item_id": items[0]["id"],
                "target_position": [2, 3],
            },
        )
        assert response1.status_code == 200

        # Try to purchase second item at same location
        response2 = auth_client.post(
            "/purchase/item",
            json={
                "item_id": items[1]["id"],
                "target_position": [2, 3],
            },
        )

        assert response2.status_code == 400
        assert "occupied" in response2.json()["detail"].lower()

    def test_purchase_nonexistent_item(self, auth_client):
        """Test purchasing an item not in the shop"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )

        # Try to purchase non-existent item
        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": "fake-item-id",
                "target_position": None,
                "to_storage": True,
            },
        )

        assert response.status_code == 404
        assert "not in shop" in response.json()["detail"].lower()

    def test_purchase_insufficient_gold(self, auth_client):
        """Test purchasing when player doesn't have enough gold"""
        # Start session with a seed whose shop is all non-container items, so
        # every one of them can go to storage and gold is what runs out.
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": SHOP_SEED}
        )
        data = response.json()

        # Get shop
        session = data["session"]
        shop = session["current_shop"]

        # Buy items until we run out of gold
        for item in shop:
            if item:
                response = auth_client.post(
                    "/purchase/item",
                    json={
                        "item_id": item["id"],
                        "target_position": None,
                        "to_storage": True,
                    },
                )

                if response.status_code == 400:
                    # Should fail due to insufficient gold
                    assert "not enough gold" in response.json()["detail"].lower()
                    return  # Test passed!

        # If all items were free or we had enough gold, try again with any remaining item
        # Get updated shop
        session_response = auth_client.get("/session")
        updated_session = session_response.json()

        # Find any non-null item still in shop and try to buy it
        for item in updated_session["current_shop"]:
            if item:
                response = auth_client.post(
                    "/purchase/item",
                    json={
                        "item_id": item["id"],
                        "target_position": None,
                        "to_storage": True,
                    },
                )
                assert response.status_code == 400
                assert "not enough gold" in response.json()["detail"].lower()
                return

        # This should never happen - we should always run out of gold
        pytest.fail("Could not create insufficient gold scenario")

    def test_purchase_removes_from_shop(self, auth_client):
        """Test that purchased items are removed from shop"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )
        data = response.json()

        # Get shop
        session = data["session"]
        shop = session["current_shop"]

        # Count non-null items
        initial_count = sum(1 for item in shop if item is not None)

        # Find and purchase first item
        shop_item = None
        for item in shop:
            if item is not None:
                shop_item = item
                break

        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": shop_item["id"],
                "target_position": None,
                "to_storage": True,
            },
        )
        assert response.status_code == 200

        # Check shop has one less item
        session_response = auth_client.get("/session")
        updated_session = session_response.json()
        updated_shop = updated_session["current_shop"]

        new_count = sum(1 for item in updated_shop if item is not None)
        assert new_count == initial_count - 1

        # Verify specific item is gone
        for item in updated_shop:
            if item is not None:
                assert item["id"] != shop_item["id"]


# A seed whose round-one shop has a non-container item on sale, costing less today.
# (Reseeded when the catalogue correction changed what shops offer.)
SALE_SEED = 15


class TestBuyingOnSale:
    """A sale is the shop's, and ends when the item changes hands"""

    def _sale_item(self, auth_client):
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": SALE_SEED}
        )
        assert response.status_code == 200
        shop = response.json()["session"]["current_shop"]
        item = next(i for i in shop if i and i["on_sale"] and i["cost"] > i["price"])
        return item

    def test_the_shop_charges_the_sale_price(self, auth_client):
        item = self._sale_item(auth_client)
        before = auth_client.get("/session").json()["gold"]

        response = auth_client.post(
            "/purchase/item",
            json={"item_id": item["id"], "target_position": [2, 3]},
        )
        assert response.status_code == 200, response.text

        spent = before - response.json()["gold"]
        assert spent == item["price"]
        assert spent < item["cost"], "the sale should have saved something"

    def test_a_bought_item_is_no_longer_on_sale(self, auth_client):
        """Otherwise it reports the discounted price for the rest of the game."""
        item = self._sale_item(auth_client)

        response = auth_client.post(
            "/purchase/item",
            json={"item_id": item["id"], "target_position": [2, 3]},
        )
        assert response.status_code == 200, response.text

        bought = response.json()["purchased_item"]
        assert bought["on_sale"] is False
        assert bought["price"] == bought["cost"]

        # And the copy that was kept, not just the one handed back
        grid = auth_client.get("/session").json()["inventory_grid"]
        stored = next(i for i in grid if i["id"] == item["id"])
        assert stored["on_sale"] is False
        assert stored["price"] == stored["cost"]
