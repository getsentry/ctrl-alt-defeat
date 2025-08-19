"""
Tests for the GameSession model with inventory management
"""

import pytest
from fastapi.testclient import TestClient
from inventory_manager import InventoryManager
from main import GameSession, app

client = TestClient(app)


class TestGameSessionInventory:
    """Test GameSession with inventory fields"""

    def test_session_creation_with_inventory(self):
        """Test that new sessions include inventory state"""
        response = client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )
        assert response.status_code == 200

        data = response.json()
        session = data["session"]

        # Check inventory fields exist
        assert "inventory_grid" in session
        assert "inventory_storage" in session
        assert "placed_items" in session
        assert "server_containers" in session

        # Check initial state
        assert session["inventory_storage"] == []  # Empty storage
        assert len(session["server_containers"]) == 3  # 3 initial containers

        # Check containers are at correct positions
        containers = session["server_containers"]
        expected_positions = [(2, 3), (4, 3), (6, 3)]
        actual_positions = [tuple(c["position"]) for c in containers]
        assert actual_positions == expected_positions

    def test_inventory_persistence(self):
        """Test that inventory persists across requests"""
        # Start session
        response = client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )
        data = response.json()
        player_id = data["player_id"]

        # Get initial shop
        session = data["session"]
        shop = session["current_shop"]

        # Find a non-null item in shop
        shop_item = None
        for item in shop:
            if item is not None:
                shop_item = item
                break

        assert shop_item is not None, "No items in shop"

        # Purchase item to storage
        purchase_response = client.post(
            "/purchase/item",
            json={
                "player_id": player_id,
                "item_id": shop_item["id"],
                "to_storage": True,
            },
        )

        # Check if endpoint exists, skip if not implemented yet
        if purchase_response.status_code == 404:
            pytest.skip("Purchase endpoint not yet implemented")

        assert purchase_response.status_code == 200

        # Get session again
        response = client.get(f"/session/{player_id}")
        assert response.status_code == 200

        session = response.json()

        # Check item is in storage
        assert len(session["inventory_storage"]) == 1
        assert session["inventory_storage"][0]["id"] == shop_item["id"]

    def test_inventory_grid_initialization(self):
        """Test that inventory grid is properly initialized"""
        response = client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )
        data = response.json()

        session = data["session"]

        # Grid should have container information
        containers = session["server_containers"]

        for container in containers:
            assert "id" in container
            assert "position" in container
            assert "width" in container
            assert "height" in container
            assert container["width"] == 2
            assert container["height"] == 2

    def test_placed_items_tracking(self):
        """Test that placed items are tracked separately"""
        response = client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )
        data = response.json()
        # player_id = data["player_id"]  # Will be used when purchase is implemented

        # Initially no placed items
        session = data["session"]
        assert session["placed_items"] == []

        # After purchasing and placing an item (when implemented)
        # the placed_items list should update

    def test_session_model_creation(self):
        """Test creating GameSession model directly"""
        # Create inventory manager
        manager = InventoryManager()

        # Create session with inventory state
        session = GameSession(
            player_id="test123",
            round=1,
            gold=12,
            lives=5,
            wins=0,
            losses=0,
            game_seed=12345,  # Always need a seed now
            inventory_grid=manager.get_state()["grid"],
            inventory_storage=manager.get_state()["storage"],
            placed_items=[],
            server_containers=manager.get_state()["containers"],
        )

        assert session.player_id == "test123"
        assert len(session.server_containers) == 3
        assert session.inventory_storage == []
        assert session.placed_items == []

    def test_session_inventory_to_dict(self):
        """Test that session with inventory serializes correctly"""
        manager = InventoryManager()

        session = GameSession(
            player_id="test123",
            round=1,
            gold=12,
            lives=5,
            wins=0,
            losses=0,
            game_seed=12345,  # Always need a seed now
            inventory_grid=manager.get_state()["grid"],
            inventory_storage=manager.get_state()["storage"],
            placed_items=[],
            server_containers=manager.get_state()["containers"],
        )

        # Convert to dict (for API response)
        session_dict = session.model_dump()

        assert "inventory_grid" in session_dict
        assert "inventory_storage" in session_dict
        assert "placed_items" in session_dict
        assert "server_containers" in session_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
