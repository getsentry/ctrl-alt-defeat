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
        data = response.json()
        player_id = data["player_id"]

        # Try to battle with empty inventory
        battle_request = {
            "player_id": player_id,
            "round_number": 1,
            "seed": 42,
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
        player_id = data["player_id"]

        # Get shop
        session = data["session"]
        shop = session["current_shop"]

        # Purchase first non-null item to grid
        for item in shop:
            if item:
                response = auth_client.post(
                    "/purchase/item",
                    json={
                        "player_id": player_id,
                        "item_id": item["id"],
                        "target_position": [2, 3],  # Place on first container
                    },
                )
                assert response.status_code == 200
                break

        # Now battle with the purchased item
        battle_request = {
            "player_id": player_id,
            "round_number": 1,
            "seed": 42,
            "test_ai_difficulty": 1,  # Easy AI (1)
        }

        response = auth_client.post("/battle/simulate", json=battle_request)
        assert response.status_code == 200
        result = response.json()

        assert "battle_result" in result
        assert "session_update" in result

    def test_battle_uses_correct_inventory(self, auth_client):
        """Test that battle uses the items placed on grid, not storage"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )
        data = response.json()
        player_id = data["player_id"]

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
                "player_id": player_id,
                "item_id": items[0]["id"],
                "to_storage": True,
            },
        )
        assert response.status_code == 200

        # Purchase second item to grid
        response = auth_client.post(
            "/purchase/item",
            json={
                "player_id": player_id,
                "item_id": items[1]["id"],
                "target_position": [2, 3],
            },
        )
        assert response.status_code == 200

        # Battle should only use the grid item, not storage item
        battle_request = {
            "player_id": player_id,
            "round_number": 1,
            "seed": 42,
            "test_ai_difficulty": 1,  # Easy AI (1)
        }

        response = auth_client.post("/battle/simulate", json=battle_request)
        assert response.status_code == 200

        # Check session still has item in storage after battle
        session_response = auth_client.get(f"/session/{player_id}")
        updated_session = session_response.json()
        assert len(updated_session["inventory_storage"]) == 1
        assert len(updated_session["inventory_grid"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
