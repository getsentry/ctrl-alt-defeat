"""
Tests for AI opponent generation with containers
"""


from battle_engine import BattleSimulator
from containers import Container
from main import generate_ai_opponent
from tests.conftest import MULTI_SQUARE_SHOP_SEED, SHOP_SEED
from tests.test_utils import find_bad_positions


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

        # Containers should be Container instances
        for container in containers:
            assert isinstance(container, Container)

    def test_ai_opponent_passes_validation(self):
        """Test that AI opponent items and containers pass battle validation"""
        # Generate AI opponent for various rounds
        for round_num in range(1, 11):
            items, containers = generate_ai_opponent(round_number=round_num)

            # Create a battle simulator
            simulator = BattleSimulator(seed=42)

            # Should be able to validate placement
            # This would raise ValueError if validation fails
            assert simulator._validate_placement_with_containers(
                items, containers
            ), f"Failed validation for round {round_num}"

    def test_ai_containers_cover_item_positions(self):
        """Test that generated containers cover all AI item positions"""
        # Generate AI opponent
        items, containers = generate_ai_opponent(round_number=5)

        # Get all container squares
        container_squares = set()
        for container in containers:
            for square in container.covered_squares():
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
        """A battle request names no opponent; the server picks one"""
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
            "/session/start",
            json={"player_name": "test_player", "seed": MULTI_SQUARE_SHOP_SEED},
        )
        assert response.status_code == 200
        data = response.json()

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
                        "item_id": item["id"],
                        "target_position": positions[idx],
                    },
                )
                assert response.status_code == 200
                purchased_items.append({"item": item, "position": positions[idx]})

        assert len(purchased_items) >= 1, "Should have purchased at least one item"

        # Simulate battle
        battle_request = {
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
            assert "shape" in container

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
            assert "shape" in container
            assert isinstance(container["position"], list)
            assert len(container["position"]) == 2

    def test_battle_response_item_shapes(self, auth_client):
        """Test that item shapes are properly serialized"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": None}
        )
        data = response.json()

        # Purchase an item
        shop = data["session"]["current_shop"]
        for item in shop:
            if item:
                auth_client.post(
                    "/purchase/item",
                    json={
                        "item_id": item["id"],
                        "target_position": [2, 3],
                    },
                )
                break

        # Battle
        response = auth_client.post(
            "/battle/simulate",
            json={"test_ai_difficulty": 1, "seed": None},
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

        # Don't purchase any items, just battle
        response = auth_client.post(
            "/battle/simulate",
            json={"test_ai_difficulty": 1, "seed": None},
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

        # Purchase specific items
        shop = data["session"]["current_shop"]
        purchased = []

        for item in shop:
            if item and len(purchased) < 2:
                response = auth_client.post(
                    "/purchase/item",
                    json={
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

        # Purchase an item
        shop = data["session"]["current_shop"]
        for item in shop:
            if item:
                auth_client.post(
                    "/purchase/item",
                    json={
                        "item_id": item["id"],
                        "target_position": [2, 3],
                    },
                )
                break

        # Battle round 1
        response1 = auth_client.post(
            "/battle/simulate",
            json={"test_ai_difficulty": 1, "seed": None},
        )
        enemy_inv1 = response1.json()["battle_result"]["enemy_inventory"]

        # Battle round 5 (should have more/different items)
        response5 = auth_client.post(
            "/battle/simulate",
            json={"seed": None, "test_ai_difficulty": None},
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

        shop = data["session"]["current_shop"]
        # Filter out containers since they can't be placed in storage (only on grid)
        items = [item for item in shop if not item.get("is_container", False)][:2]
        assert len(items) >= 2, "Need at least 2 non-container items in shop"

        # Purchase one item to storage
        response = auth_client.post(
            "/purchase/item",
            json={
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
                "item_id": items[1]["id"],
                "target_position": [2, 3],
            },
        )
        assert response.status_code == 200

        # Battle
        response = auth_client.post(
            "/battle/simulate",
            json={"test_ai_difficulty": 1, "seed": None},
        )

        result = response.json()
        player_items = result["battle_result"]["player_inventory"]["items"]

        # Should only have the grid item, not the storage item
        assert len(player_items) == 1
        assert player_items[0]["position"] == [2, 3]


class TestContainerPurchase:
    """A bought container keeps the shape of its type"""

    # Seed 11 puts a packet_buffer, which is 1x2 rather than 2x2, in round 1.
    NON_SQUARE_CONTAINER_SEED = 11

    def test_a_bought_container_keeps_its_own_shape(self, auth_client):
        response = auth_client.post(
            "/session/start",
            json={"player_name": "Tester", "seed": self.NON_SQUARE_CONTAINER_SEED},
        )
        assert response.status_code == 200
        data = response.json()

        shop = data["session"]["current_shop"]
        container = next(
            item
            for item in shop
            if item and item["is_container"] and item["item_type"] == "packet_buffer"
        )

        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": container["id"],
                "target_position": [0, 0],
            },
        )
        assert response.status_code == 200, response.text

        bought = next(
            c
            for c in response.json()["server_containers"]
            if c["id"] == container["id"]
        )
        assert bought["shape"] == container["shape"], (
            "A container should cover the squares of its own shape, " "not a 2x2 block"
        )


class TestOnePlayerCannotActAsAnother:
    def _player(self, name):
        from fastapi.testclient import TestClient

        from main import app

        client = TestClient(app)
        token = client.post("/auth/guest").json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        started = client.post(
            "/session/start", json={"player_name": name, "seed": SHOP_SEED}
        ).json()
        return client, started["player_id"]

    def test_the_player_is_taken_from_the_token(self):
        """A request carries no player id. The token says who is asking."""
        from schemas import (
            MoveItemRequest,
            PurchaseRequest,
            SellRequest,
            ShopRefreshRequest,
            SimpleBattleRequest,
        )

        for model in (
            PurchaseRequest,
            SellRequest,
            MoveItemRequest,
            ShopRefreshRequest,
            SimpleBattleRequest,
        ):
            assert "player_id" not in model.model_fields, model.__name__

    def test_each_player_reads_only_their_own_session(self):
        alice, alice_id = self._player("Alice")
        bob, bob_id = self._player("Bob")

        assert alice_id != bob_id, "Setup: two different players"
        assert alice.get("/session").json()["player_id"] == alice_id
        assert bob.get("/session").json()["player_id"] == bob_id

    def test_a_stranger_cannot_spend_your_gold(self):
        alice, _alice_id = self._player("Alice")
        bob, _bob_id = self._player("Bob")
        gold_before = alice.get("/session").json()["gold"]

        # Bob refreshes a shop. It can only ever be his own.
        assert bob.post("/shop/refresh", json={}).status_code == 200

        assert alice.get("/session").json()["gold"] == gold_before

    def test_every_session_endpoint_requires_a_token(self):
        from fastapi.testclient import TestClient

        from main import app

        anonymous = TestClient(app)

        for method, path, body in [
            ("get", "/session", None),
            ("post", "/shop/refresh", {}),
            ("post", "/battle/simulate", {}),
            ("post", "/purchase/item", {"item_id": "x"}),
            ("post", "/sell/item", {"item_id": "x"}),
            ("post", "/move/item", {"item_id": "x", "to_location": "storage"}),
            ("get", "/battle/history", None),
        ]:
            response = (
                anonymous.get(path)
                if method == "get"
                else anonymous.post(path, json=body)
            )
            assert response.status_code in (
                401,
                403,
            ), f"{path} answered {response.status_code}"


class TestHealthEndpoint:
    """/health reports whether the database is reachable. The deploy watches it."""

    def test_a_reachable_database_reports_healthy(self, auth_client):
        response = auth_client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["database"] == "healthy", body["database"]
        assert body["status"] == "healthy", body

    def test_an_unreachable_database_reports_degraded(self, auth_client, monkeypatch):
        async def cannot_reach():
            return False

        monkeypatch.setattr("main.db_manager.health_check", cannot_reach)

        body = auth_client.get("/health").json()

        assert body["database"] == "unhealthy"
        assert body["status"] == "degraded"


class TestSellItemAPI:
    """Test the /sell/item endpoint."""

    def _buy_one(self, auth_client):
        """Start a session and put one item on the grid. Returns the details."""
        start = auth_client.post(
            "/session/start", json={"player_name": "Tester", "seed": SHOP_SEED}
        ).json()
        player_id = start["player_id"]
        item = next(
            i for i in start["session"]["current_shop"] if i and not i["is_container"]
        )
        bought = auth_client.post(
            "/purchase/item",
            json={
                "item_id": item["id"],
                "target_position": [2, 3],
            },
        )
        assert bought.status_code == 200, bought.text
        return player_id, item, bought.json()["gold"]

    def test_selling_pays_half_and_takes_the_item(self, auth_client):
        player_id, item, gold_after_buying = self._buy_one(auth_client)

        response = auth_client.post("/sell/item", json={"item_id": item["id"]})

        assert response.status_code == 200, response.text
        sold = response.json()
        assert sold["gold_gained"] == item["cost"] // 2, "A sale pays half the cost"
        assert sold["gold"] == gold_after_buying + sold["gold_gained"]
        assert sold["sold_item"]["id"] == item["id"], "The sold item comes back"

        session = auth_client.get("/session").json()
        assert session["inventory_grid"] == [], "The item leaves the grid"
        assert session["gold"] == sold["gold"], "The gold is kept on the session"

    def test_selling_an_item_you_do_not_own_is_refused(self, auth_client):
        player_id, _item, _gold = self._buy_one(auth_client)

        response = auth_client.post("/sell/item", json={"item_id": "no_such_item"})

        assert response.status_code == 404, response.text
        session = auth_client.get("/session").json()
        assert len(session["inventory_grid"]) == 1, "The real item is untouched"

    def test_purchase_sell_and_move_name_the_item_the_same_way(self):
        """All three call it item_id, matching Item.id."""
        from schemas import MoveItemRequest, PurchaseRequest, SellRequest

        for model in (PurchaseRequest, SellRequest, MoveItemRequest):
            assert "item_id" in model.model_fields, model.__name__
            assert "item_uid" not in model.model_fields, model.__name__


class TestMoveItemAPI:
    """Test the /move/item endpoint functionality"""

    def test_move_item_grid_to_grid(self, auth_client):
        """Test moving an item from one grid position to another"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 42}
        )
        data = response.json()

        # Purchase an item
        shop = data["session"]["current_shop"]
        item = next(item for item in shop if item)
        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": item["id"],
                "target_position": [2, 3],
            },
        )
        assert response.status_code == 200
        purchase_data = response.json()
        item_id = purchase_data["purchased_item"]["id"]

        # Move item to different position
        response = auth_client.post(
            "/move/item",
            json={
                "item_id": item_id,
                "to_location": [4, 3],  # Second container
            },
        )
        assert response.status_code == 200
        result = response.json()

        # Success is indicated by 200 status

        # Verify item is at new position in inventory
        found = False
        for grid_item in result["inventory_grid"]:
            if grid_item["id"] == item_id:
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

        # Purchase item to grid
        shop = data["session"]["current_shop"]
        item = next(item for item in shop if item)
        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": item["id"],
                "target_position": [2, 3],
            },
        )
        item_id = response.json()["purchased_item"]["id"]

        # Move to storage
        response = auth_client.post(
            "/move/item",
            json={
                "item_id": item_id,
                "to_location": "storage",
            },
        )
        assert response.status_code == 200
        result = response.json()

        # Success is indicated by 200 status
        assert len(result["inventory_storage"]) == 1
        assert len(result["inventory_grid"]) == 0
        # An item in the chest has no position field
        assert "position" not in result["inventory_storage"][0]

    def test_move_item_storage_to_grid(self, auth_client):
        """Test moving an item from storage to grid"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": None}
        )
        data = response.json()

        # Purchase item to storage
        shop = data["session"]["current_shop"]
        item = next(item for item in shop if item)
        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": item["id"],
                "target_position": None,
                "to_storage": True,
            },
        )
        item_id = response.json()["purchased_item"]["id"]

        # Move to grid
        response = auth_client.post(
            "/move/item",
            json={
                "item_id": item_id,
                "to_location": [2, 3],
            },
        )
        assert response.status_code == 200
        result = response.json()

        # Success is indicated by 200 status
        assert len(result["inventory_storage"]) == 0
        assert len(result["inventory_grid"]) == 1
        assert result["inventory_grid"][0]["position"] == [2, 3]

    def test_move_item_storage_to_storage_noop(self, auth_client):
        """Test that moving from storage to storage is a no-op"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": None}
        )
        data = response.json()

        # Purchase item to storage
        shop = data["session"]["current_shop"]
        item = next(item for item in shop if item)
        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": item["id"],
                "target_position": None,
                "to_storage": True,
            },
        )
        item_id = response.json()["purchased_item"]["id"]

        # Try to move from storage to storage (should be no-op, not error)
        response = auth_client.post(
            "/move/item",
            json={
                "item_id": item_id,
                "to_location": "storage",
            },
        )
        assert response.status_code == 200  # Should succeed as no-op
        result = response.json()
        # Success is indicated by 200 status
        assert len(result["inventory_storage"]) == 1
        assert "position" not in result["inventory_storage"][0]

    def test_move_item_to_invalid_position(self, auth_client):
        """Test moving an item to a position not on a container"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": SHOP_SEED}
        )
        data = response.json()

        # Purchase item
        shop = data["session"]["current_shop"]
        item = next(item for item in shop if item)
        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": item["id"],
                "target_position": [2, 3],
            },
        )
        item_id = response.json()["purchased_item"]["id"]

        # Try to move to invalid position (not on container)
        response = auth_client.post(
            "/move/item",
            json={
                "item_id": item_id,
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

        # Purchase two items
        shop = data["session"]["current_shop"]
        items = [item for item in shop if item][:2]

        # Place first item
        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": items[0]["id"],
                "target_position": [2, 3],
            },
        )
        assert response.status_code == 200

        # Place second item
        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": items[1]["id"],
                "target_position": [4, 3],
            },
        )
        item2_uid = response.json()["purchased_item"]["id"]

        # Try to move second item to first item's position
        response = auth_client.post(
            "/move/item",
            json={
                "item_id": item2_uid,
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

        # Try to move non-existent item
        response = auth_client.post(
            "/move/item",
            json={
                "item_id": "fake-item-id-12345",
                "to_location": [4, 3],
            },
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_move_item_same_position_noop(self, auth_client):
        """Test moving an item to the same position (no-op)"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": SHOP_SEED}
        )
        data = response.json()

        # Purchase item
        shop = data["session"]["current_shop"]
        item = next(item for item in shop if item)
        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": item["id"],
                "target_position": [2, 3],
            },
        )
        item_id = response.json()["purchased_item"]["id"]

        # Move to same position
        response = auth_client.post(
            "/move/item",
            json={
                "item_id": item_id,
                "to_location": [2, 3],
            },
        )
        assert response.status_code == 200
        result = response.json()

        # Success is indicated by 200 status
        assert result["inventory_grid"][0]["position"] == [2, 3]

    def test_move_item_preserves_metadata(self, auth_client):
        """Test that moving an item preserves all its metadata"""
        # Start session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 123}
        )
        data = response.json()

        # Purchase item
        shop = data["session"]["current_shop"]
        item = next(item for item in shop if item)
        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": item["id"],
                "target_position": [2, 3],
            },
        )
        purchased = response.json()["purchased_item"]
        item_id = purchased["id"]
        original_type = purchased["item_type"]
        original_name = purchased["name"]

        # Move item
        response = auth_client.post(
            "/move/item",
            json={
                "item_id": item_id,
                "to_location": [4, 3],
            },
        )
        result = response.json()

        # Find moved item in grid
        moved_item = None
        for grid_item in result["inventory_grid"]:
            if grid_item["id"] == item_id:
                moved_item = grid_item
                break

        assert moved_item is not None
        assert moved_item["item_type"] == original_type
        assert moved_item["name"] == original_name
        assert moved_item["position"] == [4, 3]

    def test_move_multi_square_item(self, auth_client):
        """
        Test moving an item that occupies multiple squares.

        The shop is seeded so the item it offers is known, and containers are
        skipped because one cannot be bought onto a square another already
        covers.
        """
        response = auth_client.post(
            "/session/start",
            json={"player_name": "test_player", "seed": MULTI_SQUARE_SHOP_SEED},
        )
        data = response.json()

        shop = data["session"]["current_shop"]
        multi_square_item = next(
            (
                item
                for item in shop
                if item and not item["is_container"] and len(item["shape"]) > 1
            ),
            None,
        )
        assert multi_square_item, "Seed should offer a multi-square item to move"

        # Purchase multi-square item
        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": multi_square_item["id"],
                "target_position": [2, 3],
            },
        )
        assert response.status_code == 200, response.text
        item_id = response.json()["purchased_item"]["id"]

        # Move to different container
        response = auth_client.post(
            "/move/item",
            json={
                "item_id": item_id,
                "to_location": [6, 3],  # Third container
            },
        )

        # Should succeed if item fits, or fail with appropriate message
        if response.status_code == 200:
            result = response.json()
            assert result["inventory_grid"][0]["position"] == [6, 3]
        else:
            # If it doesn't fit, should get appropriate error
            assert response.status_code == 400
            detail = response.json()["detail"]
            assert "invalid placement" in detail.lower() or "not on" in detail.lower()

    def test_move_item_without_session(self):
        """A move needs a session, so a player who has not started one is refused."""
        from fastapi.testclient import TestClient

        from main import app

        client = TestClient(app)
        token = client.post("/auth/guest").json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"

        response = client.post(
            "/move/item", json={"item_id": "some-item", "to_location": [4, 3]}
        )

        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]

    def test_a_move_without_a_token_is_refused(self):
        """Every endpoint that touches a session needs to know who is asking."""
        from fastapi.testclient import TestClient

        from main import app

        response = TestClient(app).post(
            "/move/item", json={"item_id": "some-item", "to_location": [4, 3]}
        )

        assert response.status_code in (401, 403), response.text


# ============ Position contract ============
#
# Every endpoint that returns a position must return it as [x, y]. The check
# walks the response tree rather than naming fields, so an endpoint added later
# is covered without touching these tests.

# The three starting containers sit at (2,3), (4,3) and (6,3), each 2x2.
FREE_SQUARE = [2, 3]
SECOND_SQUARE = [4, 3]


def assert_positions_are_canonical(payload, endpoint: str):
    """Fail with a readable message if any position in the payload is wrong"""
    problems = find_bad_positions(payload)
    assert not problems, "{} returned {} bad position(s):\n  {}".format(
        endpoint, len(problems), "\n  ".join(problems)
    )


def buy_an_item(client, session, position):
    """Buy the first shop item and place it at the given square."""
    return client.post(
        "/purchase/item",
        json={
            "item_id": session["current_shop"][0]["id"],
            "target_position": position,
        },
    )


class TestPositionContractOverHttp:
    """Every endpoint must return positions as [x, y]"""

    def test_session_start_positions_are_canonical(self, auth_client):
        response = auth_client.post(
            "/session/start", json={"player_name": "Tester", "seed": SHOP_SEED}
        )
        assert response.status_code == 200
        assert_positions_are_canonical(response.json(), "POST /session/start")

    def test_session_start_containers_use_lists(self, auth_client):
        """Starting containers report their position as a list"""
        response = auth_client.post(
            "/session/start", json={"player_name": "Tester", "seed": SHOP_SEED}
        )
        containers = response.json()["session"]["server_containers"]
        assert len(containers) == 3
        for container in containers:
            assert isinstance(container["position"], list)
            assert len(container["position"]) == 2

    def test_get_session_positions_are_canonical(self, auth_client):
        """
        GET /session/{player_id} reads state straight from the database, so it
        shows what was actually stored.
        """
        auth_client.post(
            "/session/start", json={"player_name": "Tester", "seed": SHOP_SEED}
        )

        response = auth_client.get("/session")
        assert response.status_code == 200
        assert_positions_are_canonical(response.json(), "GET /session/{player_id}")

    def test_purchase_positions_are_canonical(self, auth_client):
        start = auth_client.post(
            "/session/start", json={"player_name": "Tester", "seed": SHOP_SEED}
        )
        session = start.json()["session"]

        response = buy_an_item(auth_client, session, FREE_SQUARE)
        assert response.status_code == 200, response.text
        assert_positions_are_canonical(response.json(), "POST /purchase/item")

    def test_move_positions_are_canonical(self, auth_client):
        start = auth_client.post(
            "/session/start", json={"player_name": "Tester", "seed": SHOP_SEED}
        )
        session = start.json()["session"]

        bought = buy_an_item(auth_client, session, FREE_SQUARE)
        assert bought.status_code == 200, bought.text
        item_id = bought.json()["purchased_item"]["id"]

        response = auth_client.post(
            "/move/item",
            json={
                "item_id": item_id,
                "to_location": SECOND_SQUARE,
            },
        )
        assert response.status_code == 200, response.text
        assert_positions_are_canonical(response.json(), "POST /move/item")

        # The moved item must report the position we asked for
        assert response.json()["inventory_grid"][0]["position"] == SECOND_SQUARE

    def test_an_item_in_the_chest_carries_no_position(self, auth_client):
        """An item in the chest carries no position; only a placed one has one."""
        start = auth_client.post(
            "/session/start", json={"player_name": "Tester", "seed": SHOP_SEED}
        )
        session = start.json()["session"]

        bought = buy_an_item(auth_client, session, FREE_SQUARE)
        item_id = bought.json()["purchased_item"]["id"]

        response = auth_client.post(
            "/move/item",
            json={
                "item_id": item_id,
                "to_location": "storage",
            },
        )
        assert response.status_code == 200, response.text
        assert "position" not in response.json()["inventory_storage"][0]
        assert_positions_are_canonical(response.json(), "POST /move/item (storage)")

    def test_battle_positions_are_canonical(self, auth_client):
        """The battle response holds both inventories, so it carries the most positions"""
        start = auth_client.post(
            "/session/start", json={"player_name": "Tester", "seed": SHOP_SEED}
        )
        session = start.json()["session"]

        bought = buy_an_item(auth_client, session, FREE_SQUARE)
        assert bought.status_code == 200, bought.text

        response = auth_client.post("/battle/simulate", json={})
        assert response.status_code == 200, response.text
        payload = response.json()
        assert_positions_are_canonical(payload, "POST /battle/simulate")

        # Both inventories must actually be present, or the walk proves nothing
        battle = payload["battle_result"]
        assert battle["player_inventory"]["items"], "No player items to check"

    def test_a_full_turn_keeps_every_position_canonical(self, auth_client):
        """
        Play one complete turn the way the client does:
        start, buy, move, refresh the shop, battle.
        Every response is checked.
        """
        responses = []

        start = auth_client.post(
            "/session/start", json={"player_name": "Tester", "seed": SHOP_SEED}
        )
        assert start.status_code == 200
        session = start.json()["session"]
        responses.append(("POST /session/start", start.json()))

        bought = buy_an_item(auth_client, session, FREE_SQUARE)
        assert bought.status_code == 200, bought.text
        responses.append(("POST /purchase/item", bought.json()))
        item_id = bought.json()["purchased_item"]["id"]

        moved = auth_client.post(
            "/move/item",
            json={
                "item_id": item_id,
                "to_location": SECOND_SQUARE,
            },
        )
        assert moved.status_code == 200, moved.text
        responses.append(("POST /move/item", moved.json()))

        refreshed = auth_client.post("/shop/refresh", json={})
        assert refreshed.status_code == 200, refreshed.text
        responses.append(("POST /shop/refresh", refreshed.json()))

        fetched = auth_client.get("/session")
        assert fetched.status_code == 200
        responses.append(("GET /session/{player_id}", fetched.json()))

        battle = auth_client.post("/battle/simulate", json={})
        assert battle.status_code == 200, battle.text
        responses.append(("POST /battle/simulate", battle.json()))

        for endpoint, payload in responses:
            assert_positions_are_canonical(payload, endpoint)


class TestPositionContractRejectsBadInput:
    """A bad position must fail at the boundary with a 422, not corrupt state"""

    def test_purchase_rejects_a_dictionary_position(self, auth_client):
        start = auth_client.post(
            "/session/start", json={"player_name": "Tester", "seed": SHOP_SEED}
        )
        session = start.json()["session"]
        shop_item = next(
            item
            for item in session["current_shop"]
            if item and not item.get("is_container", False)
        )

        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": shop_item["id"],
                "target_position": {"x": 2, "y": 3},
            },
        )
        assert response.status_code == 422, response.text

    def test_purchase_rejects_a_three_item_position(self, auth_client):
        start = auth_client.post(
            "/session/start", json={"player_name": "Tester", "seed": SHOP_SEED}
        )
        session = start.json()["session"]
        shop_item = next(
            item
            for item in session["current_shop"]
            if item and not item.get("is_container", False)
        )

        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": shop_item["id"],
                "target_position": [2, 3, 4],
            },
        )
        assert response.status_code == 422, response.text

    def test_move_rejects_a_dictionary_position(self, auth_client):
        auth_client.post(
            "/session/start", json={"player_name": "Tester", "seed": SHOP_SEED}
        )

        response = auth_client.post(
            "/move/item",
            json={
                "item_id": "does-not-matter",
                "to_location": {"x": 2, "y": 3},
            },
        )
        assert response.status_code == 422, response.text


class TestOpenApiDeclaresThePositionShape:
    """
    The generated schema is the contract the client reads, so a position has to
    be declared as a two-item array for the client to rely on it.
    """

    def test_placed_item_position_is_a_bounded_array(self):
        from fastapi.testclient import TestClient

        from main import app

        schema = TestClient(app).get("/openapi.json").json()
        position = schema["components"]["schemas"]["PlacedItem"]["properties"][
            "position"
        ]
        assert position["type"] == "array"
        assert position["minItems"] == 2
        assert position["maxItems"] == 2

    def test_server_container_position_is_a_bounded_array(self):
        from fastapi.testclient import TestClient

        from main import app

        schema = TestClient(app).get("/openapi.json").json()
        position = schema["components"]["schemas"]["Container"]["properties"][
            "position"
        ]
        assert position["type"] == "array"
        assert position["minItems"] == 2
        assert position["maxItems"] == 2
