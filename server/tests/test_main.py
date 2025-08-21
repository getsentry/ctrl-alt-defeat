"""
Tests for AI opponent generation with containers
"""

import pytest
from battle_engine import BattleSimulator
from main import generate_ai_opponent
from server_containers import ServerContainer


class TestAIOpponentGeneration:
    """Test AI opponent generation returns valid items and containers"""

    def test_generate_ai_opponent_returns_items_and_containers(self):
        """Test that generate_ai_opponent returns both items and containers"""
        # Generate AI opponent for round 3
        items, containers = generate_ai_opponent(round_number=3)

        # Should return items
        assert items is not None
        assert len(items) > 0

        # Should return containers
        assert containers is not None
        assert len(containers) > 0

        # Containers should be ServerContainer instances
        for container in containers:
            assert isinstance(container, ServerContainer)

    def test_ai_opponent_passes_validation(self):
        """Test that AI opponent items and containers pass battle validation"""
        # Generate AI opponent for various rounds
        for round_num in [1, 3, 5, 7, 10]:
            items, containers = generate_ai_opponent(round_number=round_num)

            # Create a battle simulator
            simulator = BattleSimulator(seed=42)

            # Should be able to validate placement
            # This would raise ValueError if validation fails
            assert simulator._validate_placement_with_containers(items, containers)

    def test_ai_containers_cover_item_positions(self):
        """Test that generated containers cover all AI item positions"""
        # Generate AI opponent
        items, containers = generate_ai_opponent(round_number=5)

        # Get all container squares
        container_squares = set()
        for container in containers:
            for square in container.get_occupied_squares():
                container_squares.add(square)

        # Check that all item positions are on container squares
        for item in items:
            item_squares = item.get_occupied_squares()
            for square in item_squares:
                assert (
                    square in container_squares
                ), f"Item square {square} not on any container"

    def test_test_ai_difficulty_none_by_default(self):
        """Test that test_ai_difficulty is None by default in SimpleBattleRequest"""
        from schemas import SimpleBattleRequest

        # Create request without test_ai_difficulty
        request = SimpleBattleRequest(
            player_id="test_player", seed=None, test_ai_difficulty=None
        )

        # Should be None as specified
        assert request.test_ai_difficulty is None
        assert request.seed is None

    def test_no_opponent_id_in_battle_request(self):
        """Test that opponent_id is no longer in SimpleBattleRequest"""
        from schemas import SimpleBattleRequest

        # Should not have opponent_id field
        assert not hasattr(SimpleBattleRequest, "opponent_id")

        # Create request - should work without opponent_id
        request = SimpleBattleRequest(
            player_id="test_player", seed=None, test_ai_difficulty=None
        )

        # Should not have opponent_id attribute
        assert not hasattr(request, "opponent_id")


class TestBattleAPIResponse:
    """Test battle API returns complete inventory data"""

    def test_battle_response_includes_inventories(self, auth_client):
        """Test that battle response includes both player and enemy inventories"""
        # Start a new session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )
        assert response.status_code == 200
        data = response.json()
        player_id = data["player_id"]

        # Get shop and purchase items
        session = data["session"]
        shop = session["current_shop"]

        # Purchase multiple items to different positions
        # Default containers should be created, let's use safe positions
        purchased_items = []
        # Based on other tests, position [2, 3] seems to work
        positions = [[2, 3], [4, 3], [2, 4]]

        for idx, item in enumerate(shop):
            if item and idx < len(positions):
                response = auth_client.post(
                    "/purchase/item",
                    json={
                        "player_id": player_id,
                        "item_id": item["id"],
                        "target_position": positions[idx],
                    },
                )
                assert response.status_code == 200
                purchased_items.append({"item": item, "position": positions[idx]})

        assert len(purchased_items) >= 1, "Should have purchased at least one item"

        # Simulate battle
        battle_request = {
            "player_id": player_id,
            "seed": 42,
            "test_ai_difficulty": 1,
        }

        response = auth_client.post("/battle/simulate", json=battle_request)
        assert response.status_code == 200

        result = response.json()

        # Verify top-level structure
        assert "battle_result" in result
        assert "session_update" in result
        assert "new_shop" in result
        assert "battle_id" in result

        battle_result = result["battle_result"]

        # Verify battle result structure
        assert "winner" in battle_result
        assert "duration" in battle_result
        assert "player1_quota" in battle_result
        assert "player2_quota" in battle_result
        assert "actions" in battle_result
        assert "seed" in battle_result

        # Verify player inventory is included
        assert "player_inventory" in battle_result
        player_inv = battle_result["player_inventory"]

        assert "items" in player_inv
        assert "servers" in player_inv
        assert isinstance(player_inv["items"], list)
        assert isinstance(player_inv["servers"], list)

        # Verify we have the items we purchased
        assert len(player_inv["items"]) == len(purchased_items)

        # Verify player item structure and positions
        for idx, item_data in enumerate(player_inv["items"]):
            assert "id" in item_data
            assert "item_type" in item_data
            assert "name" in item_data
            assert "position" in item_data
            assert "category" in item_data
            assert "shape" in item_data

            # Verify position matches what we placed
            expected_pos = purchased_items[idx]["position"]
            assert item_data["position"] == expected_pos

        # Verify player containers
        assert len(player_inv["servers"]) >= 3  # Should have default containers
        for container in player_inv["servers"]:
            assert "id" in container
            assert "type" in container
            assert "position" in container
            assert "width" in container
            assert "height" in container

        # Verify enemy inventory is included
        assert "enemy_inventory" in battle_result
        enemy_inv = battle_result["enemy_inventory"]

        assert "items" in enemy_inv
        assert "servers" in enemy_inv
        assert isinstance(enemy_inv["items"], list)
        assert isinstance(enemy_inv["servers"], list)

        # AI should have at least one item and container
        assert len(enemy_inv["items"]) >= 1
        assert len(enemy_inv["servers"]) >= 1

        # Verify enemy item structure
        for item_data in enemy_inv["items"]:
            assert "id" in item_data
            assert "item_type" in item_data
            assert "name" in item_data
            assert "position" in item_data
            assert "category" in item_data
            assert "shape" in item_data
            assert isinstance(item_data["position"], list)
            assert len(item_data["position"]) == 2

        # Verify enemy containers
        for container in enemy_inv["servers"]:
            assert "id" in container
            assert "type" in container
            assert "position" in container
            assert "width" in container
            assert "height" in container
            assert isinstance(container["position"], list)
            assert len(container["position"]) == 2

    def test_battle_response_item_shapes(self, auth_client):
        """Test that item shapes are properly serialized"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": None}
        )
        data = response.json()
        player_id = data["player_id"]

        # Purchase an item
        shop = data["session"]["current_shop"]
        for item in shop:
            if item:
                auth_client.post(
                    "/purchase/item",
                    json={
                        "player_id": player_id,
                        "item_id": item["id"],
                        "target_position": [2, 3],
                    },
                )
                break

        # Battle
        response = auth_client.post(
            "/battle/simulate",
            json={"player_id": player_id, "test_ai_difficulty": 1, "seed": None},
        )

        result = response.json()
        player_inv = result["battle_result"]["player_inventory"]

        # Check shape data
        for item in player_inv["items"]:
            assert "shape" in item
            assert isinstance(item["shape"], list)
            # Each shape should be a list of [x, y] coordinates
            for square in item["shape"]:
                assert isinstance(square, list)
                assert len(square) == 2
                assert isinstance(square[0], int)
                assert isinstance(square[1], int)

    def test_battle_response_with_no_items(self, auth_client):
        """Test battle response when player has only containers, no items"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": None}
        )
        data = response.json()
        player_id = data["player_id"]

        # Don't purchase any items, just battle
        response = auth_client.post(
            "/battle/simulate",
            json={"player_id": player_id, "test_ai_difficulty": 1, "seed": None},
        )

        # Should fail with 400 - empty inventory
        assert response.status_code == 400
        assert "empty inventory" in response.json()["detail"].lower()

    def test_battle_response_preserves_item_metadata(self, auth_client):
        """Test that item metadata is preserved in response"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 123}
        )
        data = response.json()
        player_id = data["player_id"]

        # Purchase specific items
        shop = data["session"]["current_shop"]
        purchased = []

        for item in shop:
            if item and len(purchased) < 2:
                response = auth_client.post(
                    "/purchase/item",
                    json={
                        "player_id": player_id,
                        "item_id": item["id"],
                        "target_position": [
                            2 + len(purchased),
                            3,
                        ],
                    },
                )
                assert response.status_code == 200
                purchased.append(item)

        # Battle
        response = auth_client.post(
            "/battle/simulate",
            json={
                "player_id": player_id,
                "seed": 456,
                "test_ai_difficulty": 1,
            },
        )

        result = response.json()
        player_items = result["battle_result"]["player_inventory"]["items"]

        # Verify items have expected metadata
        assert len(player_items) == len(purchased)
        for item in player_items:
            # Should have preserved item type from purchase
            matching_purchased = [p for p in purchased if p["id"] == item["id"]]
            if matching_purchased:
                original = matching_purchased[0]
                assert item["item_type"] == original["item_type"]
                assert item["name"] == original["name"]

    def test_enemy_inventory_changes_by_round(self, auth_client):
        """Test that enemy inventory is different for different rounds"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": None}
        )
        data = response.json()
        player_id = data["player_id"]

        # Purchase an item
        shop = data["session"]["current_shop"]
        for item in shop:
            if item:
                auth_client.post(
                    "/purchase/item",
                    json={
                        "player_id": player_id,
                        "item_id": item["id"],
                        "target_position": [2, 3],
                    },
                )
                break

        # Battle round 1
        response1 = auth_client.post(
            "/battle/simulate",
            json={"player_id": player_id, "test_ai_difficulty": 1, "seed": None},
        )
        enemy_inv1 = response1.json()["battle_result"]["enemy_inventory"]

        # Battle round 5 (should have more/different items)
        response5 = auth_client.post(
            "/battle/simulate",
            json={"player_id": player_id, "seed": None, "test_ai_difficulty": None},
        )
        enemy_inv5 = response5.json()["battle_result"]["enemy_inventory"]

        # Round 5 should have more items than round 1
        assert len(enemy_inv5["items"]) > len(enemy_inv1["items"])

        # Items should be different (not just more of the same)
        round1_types = {item["item_type"] for item in enemy_inv1["items"]}
        round5_types = {item["item_type"] for item in enemy_inv5["items"]}
        assert round5_types != round1_types  # Should have different item types

    def test_battle_does_not_include_storage_items(self, auth_client):
        """Test that items in storage are not included in battle inventory"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": None}
        )
        data = response.json()
        player_id = data["player_id"]

        shop = data["session"]["current_shop"]
        # Filter out containers since they can't be placed in storage (only on grid)
        items = [item for item in shop if not item.get("is_container", False)][:2]
        assert len(items) >= 2, "Need at least 2 non-container items in shop"

        # Purchase one item to storage
        response = auth_client.post(
            "/purchase/item",
            json={
                "player_id": player_id,
                "item_id": items[0]["id"],
                "target_position": None,
                "to_storage": True,
            },
        )
        assert response.status_code == 200

        # Purchase one item to grid
        response = auth_client.post(
            "/purchase/item",
            json={
                "player_id": player_id,
                "item_id": items[1]["id"],
                "target_position": [2, 3],
            },
        )
        assert response.status_code == 200

        # Battle
        response = auth_client.post(
            "/battle/simulate",
            json={"player_id": player_id, "test_ai_difficulty": 1, "seed": None},
        )

        result = response.json()
        player_items = result["battle_result"]["player_inventory"]["items"]

        # Should only have the grid item, not the storage item
        assert len(player_items) == 1
        assert player_items[0]["position"] == [2, 3]


class TestMoveItemAPI:
    """Test the /move/item endpoint functionality"""

    def test_move_item_grid_to_grid(self, auth_client):
        """Test moving an item from one grid position to another"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )
        data = response.json()
        player_id = data["player_id"]

        # Purchase an item
        shop = data["session"]["current_shop"]
        item = next(item for item in shop if item)
        response = auth_client.post(
            "/purchase/item",
            json={
                "player_id": player_id,
                "item_id": item["id"],
                "target_position": [2, 3],
            },
        )
        assert response.status_code == 200
        purchase_data = response.json()
        item_uid = purchase_data["purchased_item"]["id"]

        # Move item to different position
        response = auth_client.post(
            "/move/item",
            json={
                "player_id": player_id,
                "item_uid": item_uid,
                "to_location": [4, 3],  # Second container
            },
        )
        assert response.status_code == 200
        result = response.json()

        # Success is indicated by 200 status
        assert result["item"]["id"] == item_uid
        assert result["item"]["position"] == [4, 3]

        # Verify item is at new position in inventory
        found = False
        for grid_item in result["inventory_grid"]:
            if grid_item["id"] == item_uid:
                assert grid_item["position"] == [4, 3]
                found = True
                break
        assert found, "Item not found at new position"

    def test_move_item_grid_to_storage(self, auth_client):
        """Test moving an item from grid to storage"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": None}
        )
        data = response.json()
        player_id = data["player_id"]

        # Purchase item to grid
        shop = data["session"]["current_shop"]
        item = next(item for item in shop if item)
        response = auth_client.post(
            "/purchase/item",
            json={
                "player_id": player_id,
                "item_id": item["id"],
                "target_position": [2, 3],
            },
        )
        item_uid = response.json()["purchased_item"]["id"]

        # Move to storage
        response = auth_client.post(
            "/move/item",
            json={
                "player_id": player_id,
                "item_uid": item_uid,
                "to_location": "storage",
            },
        )
        assert response.status_code == 200
        result = response.json()

        # Success is indicated by 200 status
        assert result["item"]["position"] is None  # No position in storage
        assert len(result["inventory_storage"]) == 1
        assert len(result["inventory_grid"]) == 0

    def test_move_item_storage_to_grid(self, auth_client):
        """Test moving an item from storage to grid"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": None}
        )
        data = response.json()
        player_id = data["player_id"]

        # Purchase item to storage
        shop = data["session"]["current_shop"]
        item = next(item for item in shop if item)
        response = auth_client.post(
            "/purchase/item",
            json={
                "player_id": player_id,
                "item_id": item["id"],
                "target_position": None,
                "to_storage": True,
            },
        )
        item_uid = response.json()["purchased_item"]["id"]

        # Move to grid
        response = auth_client.post(
            "/move/item",
            json={
                "player_id": player_id,
                "item_uid": item_uid,
                "to_location": [2, 3],
            },
        )
        assert response.status_code == 200
        result = response.json()

        # Success is indicated by 200 status
        assert result["item"]["position"] == [2, 3]
        assert len(result["inventory_storage"]) == 0
        assert len(result["inventory_grid"]) == 1

    def test_move_item_storage_to_storage_noop(self, auth_client):
        """Test that moving from storage to storage is a no-op"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": None}
        )
        data = response.json()
        player_id = data["player_id"]

        # Purchase item to storage
        shop = data["session"]["current_shop"]
        item = next(item for item in shop if item)
        response = auth_client.post(
            "/purchase/item",
            json={
                "player_id": player_id,
                "item_id": item["id"],
                "target_position": None,
                "to_storage": True,
            },
        )
        item_uid = response.json()["purchased_item"]["id"]

        # Try to move from storage to storage (should be no-op, not error)
        response = auth_client.post(
            "/move/item",
            json={
                "player_id": player_id,
                "item_uid": item_uid,
                "to_location": "storage",
            },
        )
        assert response.status_code == 200  # Should succeed as no-op
        result = response.json()
        # Success is indicated by 200 status
        assert result["item"]["position"] is None  # Still in storage
        assert len(result["inventory_storage"]) == 1

    def test_move_item_to_invalid_position(self, auth_client):
        """Test moving an item to a position not on a container"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player"}
        )
        data = response.json()
        player_id = data["player_id"]

        # Purchase item
        shop = data["session"]["current_shop"]
        item = next(item for item in shop if item)
        response = auth_client.post(
            "/purchase/item",
            json={
                "player_id": player_id,
                "item_id": item["id"],
                "target_position": [2, 3],
            },
        )
        item_uid = response.json()["purchased_item"]["id"]

        # Try to move to invalid position (not on container)
        response = auth_client.post(
            "/move/item",
            json={
                "player_id": player_id,
                "item_uid": item_uid,
                "to_location": [0, 0],  # Not on any container
            },
        )
        assert response.status_code == 400
        assert (
            "not fit entirely on server containers" in response.json()["detail"]
            or "not on a server container" in response.json()["detail"]
        )

    def test_move_item_to_occupied_position(self, auth_client):
        """Test moving an item to an occupied position"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player"}
        )
        data = response.json()
        player_id = data["player_id"]

        # Purchase two items
        shop = data["session"]["current_shop"]
        items = [item for item in shop if item][:2]

        # Place first item
        response = auth_client.post(
            "/purchase/item",
            json={
                "player_id": player_id,
                "item_id": items[0]["id"],
                "target_position": [2, 3],
            },
        )
        assert response.status_code == 200

        # Place second item
        response = auth_client.post(
            "/purchase/item",
            json={
                "player_id": player_id,
                "item_id": items[1]["id"],
                "target_position": [4, 3],
            },
        )
        item2_uid = response.json()["purchased_item"]["id"]

        # Try to move second item to first item's position
        response = auth_client.post(
            "/move/item",
            json={
                "player_id": player_id,
                "item_uid": item2_uid,
                "to_location": [2, 3],  # Already occupied
            },
        )
        assert response.status_code == 400
        assert "already occupied" in response.json()["detail"]

    def test_move_nonexistent_item(self, auth_client):
        """Test moving an item that doesn't exist"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player"}
        )
        data = response.json()
        player_id = data["player_id"]

        # Try to move non-existent item
        response = auth_client.post(
            "/move/item",
            json={
                "player_id": player_id,
                "item_uid": "fake-item-id-12345",
                "to_location": [4, 3],
            },
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_move_item_same_position_noop(self, auth_client):
        """Test moving an item to the same position (no-op)"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player"}
        )
        data = response.json()
        player_id = data["player_id"]

        # Purchase item
        shop = data["session"]["current_shop"]
        item = next(item for item in shop if item)
        response = auth_client.post(
            "/purchase/item",
            json={
                "player_id": player_id,
                "item_id": item["id"],
                "target_position": [2, 3],
            },
        )
        item_uid = response.json()["purchased_item"]["id"]

        # Move to same position
        response = auth_client.post(
            "/move/item",
            json={
                "player_id": player_id,
                "item_uid": item_uid,
                "to_location": [2, 3],
            },
        )
        assert response.status_code == 200
        result = response.json()

        # Success is indicated by 200 status
        assert result["item"]["position"] == [2, 3]

    def test_move_item_preserves_metadata(self, auth_client):
        """Test that moving an item preserves all its metadata"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 123}
        )
        data = response.json()
        player_id = data["player_id"]

        # Purchase item
        shop = data["session"]["current_shop"]
        item = next(item for item in shop if item)
        response = auth_client.post(
            "/purchase/item",
            json={
                "player_id": player_id,
                "item_id": item["id"],
                "target_position": [2, 3],
            },
        )
        purchased = response.json()["purchased_item"]
        item_uid = purchased["id"]
        original_type = purchased["item_type"]
        original_name = purchased["name"]

        # Move item
        response = auth_client.post(
            "/move/item",
            json={
                "player_id": player_id,
                "item_uid": item_uid,
                "to_location": [4, 3],
            },
        )
        result = response.json()

        # Find moved item in grid
        moved_item = None
        for grid_item in result["inventory_grid"]:
            if grid_item["id"] == item_uid:
                moved_item = grid_item
                break

        assert moved_item is not None
        assert moved_item["item_type"] == original_type
        assert moved_item["name"] == original_name
        assert moved_item["position"] == [4, 3]

    def test_move_multi_square_item(self, auth_client):
        """Test moving an item that occupies multiple squares"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player"}
        )
        data = response.json()
        player_id = data["player_id"]

        # Find a multi-square item if available
        shop = data["session"]["current_shop"]
        multi_square_item = None
        for item in shop:
            if item and "shape" in item and len(item["shape"]) > 1:
                multi_square_item = item
                break

        if not multi_square_item:
            # If no multi-square item in shop, skip test
            pytest.skip("No multi-square item available in shop")

        # Purchase multi-square item
        response = auth_client.post(
            "/purchase/item",
            json={
                "player_id": player_id,
                "item_id": multi_square_item["id"],
                "target_position": [2, 3],
            },
        )
        item_uid = response.json()["purchased_item"]["id"]

        # Move to different container
        response = auth_client.post(
            "/move/item",
            json={
                "player_id": player_id,
                "item_uid": item_uid,
                "to_location": [6, 3],  # Third container
            },
        )

        # Should succeed if item fits, or fail with appropriate message
        if response.status_code == 200:
            result = response.json()
            assert result["item"]["position"] == [6, 3]
        else:
            # If it doesn't fit, should get appropriate error
            assert response.status_code == 400
            detail = response.json()["detail"]
            assert "invalid placement" in detail.lower() or "not on" in detail.lower()

    def test_move_item_without_session(self, auth_client):
        """Test moving item without valid session"""
        response = auth_client.post(
            "/move/item",
            json={
                "player_id": "invalid-player-id",
                "item_uid": "some-item",
                "to_location": [4, 3],
            },
        )
        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]
