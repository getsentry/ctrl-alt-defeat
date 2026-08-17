"""
Test battles using session-based inventory
"""

import pytest


class TestBattleWithSession:
    """Test battle simulation using inventory from session"""

    def test_battle_with_empty_inventory_fails(self, auth_client):
        """Test that battling with empty inventory fails"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )

        # Try to battle with empty inventory
        battle_request = {
            "seed": 42,
            "test_ai_difficulty": None,
        }

        response = auth_client.post("/battle/simulate", json=battle_request)
        assert response.status_code == 400
        assert "empty inventory" in response.json()["detail"].lower()

    def test_battle_with_purchased_items(self, auth_client):
        """Test battle after purchasing items"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )
        data = response.json()

        # Get shop
        session = data["session"]
        shop = session["current_shop"]

        # Purchase first non-null item to grid
        for item in shop:
            if item:
                response = auth_client.post(
                    "/purchase/item",
                    json={
                        "item_id": item["id"],
                        "target_position": [2, 3],
                    },
                )
                assert response.status_code == 200
                break

        # Now battle with the purchased item
        battle_request = {
            "seed": 42,
            "test_ai_difficulty": 1,  # Easy AI (1)
        }

        response = auth_client.post("/battle/simulate", json=battle_request)
        assert response.status_code == 200
        result = response.json()

        assert "battle_result" in result
        assert "session_update" in result

        # Validate inventories are included in battle result
        battle_result = result["battle_result"]

        # Check player inventory
        assert "player_inventory" in battle_result
        player_inv = battle_result["player_inventory"]
        assert isinstance(player_inv["items"], list)
        assert isinstance(player_inv["servers"], list)
        assert len(player_inv["items"]) == 1  # We purchased one item
        assert player_inv["items"][0]["position"] == [2, 3]

        # Check enemy inventory
        assert "enemy_inventory" in battle_result
        enemy_inv = battle_result["enemy_inventory"]
        assert isinstance(enemy_inv["items"], list)
        assert isinstance(enemy_inv["servers"], list)
        assert len(enemy_inv["items"]) >= 1  # AI has items
        assert len(enemy_inv["servers"]) >= 1  # AI has containers

    def test_battle_uses_correct_inventory(self, auth_client):
        """Test that battle uses the items placed on grid, not storage"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )
        data = response.json()

        # Get shop
        session = data["session"]
        shop = session["current_shop"]

        # Find two items
        items = [item for item in shop if item][:2]
        assert len(items) >= 2

        # Purchase first item to storage
        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": items[0]["id"],
                "target_position": None,
                "to_storage": True,
            },
        )
        assert response.status_code == 200

        # Purchase second item to grid
        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": items[1]["id"],
                "target_position": [2, 3],
            },
        )
        assert response.status_code == 200

        # Battle should only use the grid item, not storage item
        battle_request = {
            "seed": 42,
            "test_ai_difficulty": 1,  # Easy AI (1)
        }

        response = auth_client.post("/battle/simulate", json=battle_request)
        assert response.status_code == 200

        battle_data = response.json()
        assert "battle_result" in battle_data
        battle_result = battle_data["battle_result"]

        # Validate that player inventory is included
        assert "player_inventory" in battle_result
        player_inv = battle_result["player_inventory"]
        assert "items" in player_inv
        assert "servers" in player_inv
        assert len(player_inv["items"]) == 1  # Only the grid item (not storage)
        assert len(player_inv["servers"]) >= 3  # Player should have containers

        # Validate item structure
        item = player_inv["items"][0]
        assert "id" in item
        assert "item_type" in item
        assert "name" in item
        assert "position" in item
        assert item["position"] == [2, 3]  # Should match where we placed it

        # Validate that enemy inventory is included
        assert "enemy_inventory" in battle_result
        enemy_inv = battle_result["enemy_inventory"]
        assert "items" in enemy_inv
        assert "servers" in enemy_inv
        assert len(enemy_inv["items"]) >= 1  # AI should have at least 1 item
        assert len(enemy_inv["servers"]) >= 1  # AI should have containers

        # Validate enemy item structure
        enemy_item = enemy_inv["items"][0]
        assert "id" in enemy_item
        assert "item_type" in enemy_item
        assert "name" in enemy_item
        assert "position" in enemy_item

        # Check session still has item in storage after battle
        session_response = auth_client.get("/session")
        updated_session = session_response.json()
        assert len(updated_session["inventory_storage"]) == 1
        assert len(updated_session["inventory_grid"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
