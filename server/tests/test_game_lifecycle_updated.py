"""
Updated game lifecycle tests using session-based inventory
"""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def purchase_items_to_grid(player_id, shop, positions):
    """Helper to purchase items to specific grid positions"""
    items_purchased = 0
    for i, item in enumerate(shop):
        if item and items_purchased < len(positions):
            # Skip containers as they can't be placed yet
            if item.get("is_container", False):
                continue
            response = client.post(
                "/purchase/item",
                json={
                    "player_id": player_id,
                    "item_id": item["id"],
                    "placement": list(positions[items_purchased]),
                },
            )
            if response.status_code == 200:
                items_purchased += 1
    return items_purchased


class TestGameLifecycleUpdated:
    """Test complete game scenarios with session-based inventory"""

    def test_simple_victory_run(self):
        """Test winning battles with purchased items"""
        # Start new session with seed that gives offensive items
        response = client.post("/session/start?game_seed=2")
        assert response.status_code == 200
        data = response.json()
        player_id = data["player_id"]

        # Purchase some items for battle
        session = data["session"]
        shop = session["current_shop"]

        # Purchase items to containers
        container_positions = [(2, 3), (3, 3), (4, 3)]
        items_purchased = purchase_items_to_grid(player_id, shop, container_positions)
        assert items_purchased > 0

        # Battle with purchased items
        battle_request = {
            "player_id": player_id,
            "round_number": 1,
            "seed": 42,
            "test_ai_difficulty": "easy",
        }

        response = client.post("/battle/simulate", json=battle_request)
        assert response.status_code == 200
        result = response.json()

        # Should win against easy AI
        assert result["battle_result"]["winner"] == 1
        assert result["session_update"]["round"] == 2  # Advanced to round 2

    def test_defeat_with_weak_inventory(self):
        """Test losing with insufficient items"""
        # Start new session
        response = client.post("/session/start?game_seed=42")
        data = response.json()
        player_id = data["player_id"]

        # Purchase only defensive item
        session = data["session"]
        shop = session["current_shop"]

        # Find a defensive item (firewall)
        for item in shop:
            if item and item.get("item_type") == "firewall":
                response = client.post(
                    "/purchase/item",
                    json={
                        "player_id": player_id,
                        "item_id": item["id"],
                        "placement": [2, 3],
                    },
                )
                break

        # Check if we actually purchased an item
        response = client.get(f"/session/{player_id}")
        session_data = response.json()

        if len(session_data["inventory_grid"]) == 0:
            # No items purchased, skip test
            pytest.skip("No defensive items in shop to test with")

        # Battle with just defensive item against normal AI
        battle_request = {
            "player_id": player_id,
            "round_number": 1,
            "seed": 42,
        }

        response = client.post("/battle/simulate", json=battle_request)
        assert response.status_code == 200
        result = response.json()

        # Should lose with just defensive item
        assert result["battle_result"]["winner"] == 2
        assert result["session_update"]["lives"] == 4  # Lost one life


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
