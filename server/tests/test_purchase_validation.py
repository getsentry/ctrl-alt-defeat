"""
Tests for purchase validation and placement
"""

import pytest


class TestPurchaseValidation:
    """Test purchase request validation and item placement"""

    def test_purchase_to_storage(self, auth_client):
        """Test purchasing an item to storage"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )
        data = response.json()
        player_id = data["player_id"]

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
                "player_id": player_id,
                "item_id": shop_item["id"],
                "to_storage": True,
            },
        )

        assert response.status_code == 200
        result = response.json()

        # Check response
        assert result["success"] is True
        assert result["gold"] == initial_gold - shop_item["cost"]

        # Verify item is in storage
        session_response = auth_client.get(f"/session/{player_id}")
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
        player_id = data["player_id"]

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
                "player_id": player_id,
                "item_id": shop_item["id"],
                "target_position": [2, 3],  # Top-left of first container
            },
        )

        assert response.status_code == 200
        result = response.json()

        assert result["success"] is True

        # Verify item is on grid
        session_response = auth_client.get(f"/session/{player_id}")
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
        player_id = data["player_id"]

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
                "player_id": player_id,
                "item_id": shop_item["id"],
                "target_position": [0, 0],  # Not on any container
            },
        )

        assert response.status_code == 400
        assert "invalid placement" in response.json()["detail"].lower()

    def test_purchase_overlapping_item(self, auth_client):
        """Test that overlapping items are rejected"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )
        data = response.json()
        player_id = data["player_id"]

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
                "player_id": player_id,
                "item_id": items[0]["id"],
                "target_position": [2, 3],
            },
        )
        assert response1.status_code == 200

        # Try to purchase second item at same location
        response2 = auth_client.post(
            "/purchase/item",
            json={
                "player_id": player_id,
                "item_id": items[1]["id"],
                "target_position": [2, 3],  # Same position
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
        data = response.json()
        player_id = data["player_id"]

        # Try to purchase non-existent item
        response = auth_client.post(
            "/purchase/item",
            json={
                "player_id": player_id,
                "item_id": "fake-item-id",
                "to_storage": True,
            },
        )

        assert response.status_code == 404
        assert "not in shop" in response.json()["detail"].lower()

    def test_purchase_insufficient_gold(self, auth_client):
        """Test purchasing when player doesn't have enough gold"""
        # Start session with deterministic seed
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )
        data = response.json()
        player_id = data["player_id"]

        # Get shop
        session = data["session"]
        shop = session["current_shop"]

        # Buy items until we run out of gold
        for item in shop:
            if item:
                response = auth_client.post(
                    "/purchase/item",
                    json={
                        "player_id": player_id,
                        "item_id": item["id"],
                        "to_storage": True,
                    },
                )

                if response.status_code == 400:
                    # Should fail due to insufficient gold
                    assert "not enough gold" in response.json()["detail"].lower()
                    return  # Test passed!

        # If all items were free or we had enough gold, try again with any remaining item
        # Get updated shop
        session_response = auth_client.get(f"/session/{player_id}")
        updated_session = session_response.json()

        # Find any non-null item still in shop and try to buy it
        for item in updated_session["current_shop"]:
            if item:
                response = auth_client.post(
                    "/purchase/item",
                    json={
                        "player_id": player_id,
                        "item_id": item["id"],
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
        player_id = data["player_id"]

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
                "player_id": player_id,
                "item_id": shop_item["id"],
                "to_storage": True,
            },
        )
        assert response.status_code == 200

        # Check shop has one less item
        session_response = auth_client.get(f"/session/{player_id}")
        updated_session = session_response.json()
        updated_shop = updated_session["current_shop"]

        new_count = sum(1 for item in updated_shop if item is not None)
        assert new_count == initial_count - 1

        # Verify specific item is gone
        for item in updated_shop:
            if item is not None:
                assert item["id"] != shop_item["id"]

    def test_purchase_updates_placed_items(self, auth_client):
        """Test that purchasing to grid updates placed_items list"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )
        data = response.json()
        player_id = data["player_id"]

        # Get shop
        session = data["session"]
        shop = session["current_shop"]

        # Initially no placed items
        assert session["placed_items"] == []

        # Find and purchase item to grid
        shop_item = None
        for item in shop:
            if item is not None:
                shop_item = item
                break

        response = auth_client.post(
            "/purchase/item",
            json={
                "player_id": player_id,
                "item_id": shop_item["id"],
                "target_position": [2, 3],
            },
        )
        assert response.status_code == 200

        # Check placed_items updated
        session_response = auth_client.get(f"/session/{player_id}")
        updated_session = session_response.json()

        assert len(updated_session["placed_items"]) == 1
        assert updated_session["placed_items"][0]["id"] == shop_item["id"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
