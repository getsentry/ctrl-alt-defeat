"""
Tests for AI opponent generation with containers
"""


from battle_engine import BattleSimulator
from containers import Container
from items import sale_price
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
            assert "item_type" in container
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
            assert "item_type" in container
            assert "position" in container
            assert "shape" in container
            assert isinstance(container["position"], list)
            assert len(container["position"]) == 2

    def test_battle_response_item_shapes(self, auth_client):
        """Test that item shapes are properly serialized"""
        response = auth_client.post(
            "/session/start",
            json={"player_name": "test_player", "seed": SHOP_SEED},
        )
        data = response.json()

        # Purchase an item
        shop = data["session"]["current_shop"]
        item = next(offer for offer in shop if offer and not offer["is_container"])
        bought = auth_client.post(
            "/purchase/item",
            json={
                "item_id": item["id"],
                "target_position": [2, 3],
            },
        )
        assert bought.status_code == 200, bought.text

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
        response = auth_client.post(
            "/session/start",
            json={"player_name": "test_player", "seed": SHOP_SEED},
        )
        data = response.json()

        # Purchase an item
        shop = data["session"]["current_shop"]
        item = next(offer for offer in shop if offer and not offer["is_container"])
        bought = auth_client.post(
            "/purchase/item",
            json={
                "item_id": item["id"],
                "target_position": [2, 3],
            },
        )
        assert bought.status_code == 200, bought.text

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
        response = auth_client.post(
            "/session/start",
            json={"player_name": "test_player", "seed": SHOP_SEED},
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

    @staticmethod
    def _seed_offering_a_non_square_container():
        """A seed whose round one shop holds a container that is not a square.

        Searched rather than written down. Which items a seed offers depends on
        what is in the catalogue, so a seed noted here goes stale the next time
        an item is added, and the test then fails for a reason it is not about.
        """
        from main import generate_shop_items

        for seed in range(500):
            for offer in generate_shop_items(1, seed):
                if not offer or not offer.is_container:
                    continue
                xs = {x for x, _ in offer.shape}
                ys = {y for _, y in offer.shape}
                if len(offer.shape) != len(xs) * len(ys) or len(xs) != len(ys):
                    return seed, offer.item_type
        raise AssertionError("No seed in 500 offers a container that is not a square")

    def test_a_bought_container_keeps_its_own_shape(self, auth_client):
        seed, container_type = self._seed_offering_a_non_square_container()

        response = auth_client.post(
            "/session/start",
            json={"player_name": "Tester", "seed": seed},
        )
        assert response.status_code == 200
        data = response.json()

        shop = data["session"]["current_shop"]
        container = next(
            item
            for item in shop
            if item and item["is_container"] and item["item_type"] == container_type
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
        assert sold["gold_gained"] == sale_price(item["cost"]), (
            "A sale pays half the cost, rounded up"
        )
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


class TestATurnIsKept:
    """An item can be turned while it is held, and that has to stick.

    The client draws the board it thinks it placed; the server keeps the board
    the battle is fought on. If a turn reaches one and not the other, the
    player sets up one board and fights with another.
    """

    def _wide_item(self, session):
        """The offer in this shop that is two squares across"""
        for item in session["current_shop"]:
            if item and sorted(map(tuple, item["shape"])) == [(0, 0), (1, 0)]:
                return item
        raise AssertionError("This seed offers nothing two squares across")

    def _start(self, auth_client):
        response = auth_client.post(
            "/session/start",
            json={"player_name": "turner", "seed": MULTI_SQUARE_SHOP_SEED},
        )
        assert response.status_code == 200
        return response.json()["session"]

    def _on_the_board(self, auth_client, item_id):
        """How the board says an item is standing, which is what the battle
        will be fought with. The purchase answers with what was bought, not
        with what was placed, so this asks the board itself."""
        board = auth_client.get("/session").json()
        return next(i for i in board["inventory_grid"] if i["id"] == item_id)

    def test_an_item_is_bought_facing_the_way_it_was_turned(self, auth_client):
        session = self._start(auth_client)
        offer = self._wide_item(session)

        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": offer["id"],
                "target_position": [2, 3],
                "rotation": 90,
            },
        )
        assert response.status_code == 200, response.json()

        assert self._on_the_board(auth_client, offer["id"])["rotation"] == 90, (
            "Bought turned, it has to be stored turned, or the player placed "
            "one thing and the server kept another"
        )

    def test_an_item_bought_flat_stays_flat(self, auth_client):
        session = self._start(auth_client)
        offer = self._wide_item(session)

        response = auth_client.post(
            "/purchase/item",
            json={"item_id": offer["id"], "target_position": [2, 3]},
        )
        assert response.status_code == 200, response.json()

        assert self._on_the_board(auth_client, offer["id"])["rotation"] == 0

    def test_a_turn_only_fits_where_a_turn_fits(self, auth_client):
        """The containers end at x 7, so a two-wide item hangs off the last
        column lying flat and fits stood on end. That is what turning is for."""
        session = self._start(auth_client)
        offer = self._wide_item(session)

        flat = auth_client.post(
            "/purchase/item",
            json={"item_id": offer["id"], "target_position": [7, 3]},
        )
        assert flat.status_code == 400, "Lying flat it runs off the containers"

        turned = auth_client.post(
            "/purchase/item",
            json={
                "item_id": offer["id"],
                "target_position": [7, 3],
                "rotation": 90,
            },
        )
        assert turned.status_code == 200, turned.json()

    def test_a_turn_reaches_the_battle(self, auth_client):
        # The board the battle is fought on is the server's, so a turn that
        # does not reach it is a turn the player loses when the fighting starts.
        session = self._start(auth_client)
        offer = self._wide_item(session)
        auth_client.post(
            "/purchase/item",
            json={
                "item_id": offer["id"],
                "target_position": [2, 3],
                "rotation": 90,
            },
        )

        response = auth_client.post("/battle/simulate", json={})

        assert response.status_code == 200, response.json()
        items = response.json()["battle_result"]["player_inventory"]["items"]
        assert [i["rotation"] for i in items] == [90], (
            "The battle should be fought with the item facing the way the "
            "player left it"
        )

    def test_a_move_that_is_only_a_move_leaves_the_turn_alone(self, auth_client):
        session = self._start(auth_client)
        offer = self._wide_item(session)
        bought = auth_client.post(
            "/purchase/item",
            json={
                "item_id": offer["id"],
                "target_position": [2, 3],
                "rotation": 90,
            },
        )
        item_id = bought.json()["purchased_item"]["id"]

        response = auth_client.post(
            "/move/item", json={"item_id": item_id, "to_location": [4, 3]}
        )

        assert response.status_code == 200, response.json()
        moved = next(i for i in response.json()["inventory_grid"] if i["id"] == item_id)
        assert moved["rotation"] == 0, (
            "A move says which way the item faces when it lands, and this one "
            "said square on"
        )


class TestMoveContainerAPI:
    """A container moves through /move/item, because it is an item.

    A new session starts with three 2x2 containers at (2,3), (4,3) and (6,3).
    See docs/moving_containers.md.
    """

    def _start(self, auth_client):
        response = auth_client.post(
            "/session/start", json={"player_name": "mover", "seed": 42}
        )
        assert response.status_code == 200
        return response.json()["session"]

    def _buy_onto(self, auth_client, session, position):
        """Buy the first shop item that is not a container, onto a square"""
        offer = next(
            item
            for item in session["current_shop"]
            if item and not item["is_container"] and item["shape"] == [[0, 0]]
        )
        response = auth_client.post(
            "/purchase/item",
            json={"item_id": offer["id"], "target_position": position},
        )
        assert response.status_code == 200, response.json()
        return response.json()["purchased_item"]["id"]

    def test_a_container_moves_and_takes_its_item_with_it(self, auth_client):
        session = self._start(auth_client)
        item_id = self._buy_onto(auth_client, session, [2, 3])

        response = auth_client.post(
            "/move/item", json={"item_id": "container_a", "to_location": [0, 0]}
        )

        assert response.status_code == 200, response.json()
        result = response.json()
        moved = next(
            c for c in result["server_containers"] if c["id"] == "container_a"
        )
        assert moved["position"] == [0, 0]
        item = next(i for i in result["inventory_grid"] if i["id"] == item_id)
        assert item["position"] == [0, 0], "The item travelled with the container"
        assert result["inventory_storage"] == [], "Nothing was set down"

    def test_a_displaced_item_arrives_in_the_chest(self, auth_client):
        """An item left with nowhere to stand goes to the chest, and is named.

        The multi-square seed offers an item two squares wide. Placed at (3,3)
        it straddles containers A and B. Moving A to (0,0) carries it to (1,0),
        where its left square is on A and its right square is over bare floor.
        """
        response = auth_client.post(
            "/session/start",
            json={"player_name": "mover", "seed": MULTI_SQUARE_SHOP_SEED},
        )
        session = response.json()["session"]
        wide = [
            item
            for item in session["current_shop"]
            if item and sorted(map(tuple, item["shape"])) == [(0, 0), (1, 0)]
        ]
        assert wide, (
            "This seed no longer offers an item two squares wide, so it cannot "
            "straddle two containers. Pick a seed that does."
        )
        offer = wide[0]
        bought = auth_client.post(
            "/purchase/item",
            json={"item_id": offer["id"], "target_position": [3, 3]},
        )
        assert bought.status_code == 200, bought.json()
        item_id = bought.json()["purchased_item"]["id"]

        response = auth_client.post(
            "/move/item", json={"item_id": "container_a", "to_location": [0, 0]}
        )

        assert response.status_code == 200, response.json()
        result = response.json()
        assert item_id in [i["id"] for i in result["inventory_storage"]], (
            "The chest arrives whole, so what is in it now and was not before "
            "is what this move set down"
        )
        assert item_id not in [i["id"] for i in result["inventory_grid"]]


    def test_a_container_cannot_land_on_another_container(self, auth_client):
        self._start(auth_client)

        response = auth_client.post(
            "/move/item", json={"item_id": "container_a", "to_location": [4, 3]}
        )

        assert response.status_code == 400
        assert "overlap" in response.json()["detail"].lower()

    def test_a_container_cannot_leave_the_grid(self, auth_client):
        self._start(auth_client)

        response = auth_client.post(
            "/move/item", json={"item_id": "container_a", "to_location": [8, 3]}
        )

        assert response.status_code == 400
        assert "leave the grid" in response.json()["detail"]

    def test_a_container_cannot_go_in_the_chest(self, auth_client):
        self._start(auth_client)

        response = auth_client.post(
            "/move/item", json={"item_id": "container_a", "to_location": "storage"}
        )

        assert response.status_code == 400
        assert "chest" in response.json()["detail"]

    def test_a_refused_move_changes_nothing(self, auth_client):
        session = self._start(auth_client)
        item_id = self._buy_onto(auth_client, session, [2, 3])

        auth_client.post(
            "/move/item", json={"item_id": "container_a", "to_location": [8, 3]}
        )

        response = auth_client.post(
            "/move/item", json={"item_id": item_id, "to_location": [3, 3]}
        )
        assert response.status_code == 200, "The grid is still where it was"
        moved = next(
            c for c in response.json()["server_containers"] if c["id"] == "container_a"
        )
        assert moved["position"] == [2, 3]


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
        # Not simply the first slot: a container cannot be bought into
        # storage, and with an unseeded shop any slot may hold one.
        item = next(item for item in shop if item and not item["is_container"])
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
        response = auth_client.post(
            "/session/start",
            json={"player_name": "test_player", "seed": SHOP_SEED},
        )
        data = response.json()

        # Purchase item to grid
        shop = data["session"]["current_shop"]
        item = next(offer for offer in shop if offer and not offer["is_container"])
        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": item["id"],
                "target_position": [2, 3],
            },
        )
        assert response.status_code == 200, response.text
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
        response = auth_client.post(
            "/session/start",
            json={"player_name": "test_player", "seed": SHOP_SEED},
        )
        data = response.json()

        # Purchase item to storage
        shop = data["session"]["current_shop"]
        item = next(offer for offer in shop if offer and not offer["is_container"])
        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": item["id"],
                "target_position": None,
                "to_storage": True,
            },
        )
        assert response.status_code == 200, response.text
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
        response = auth_client.post(
            "/session/start",
            json={"player_name": "test_player", "seed": SHOP_SEED},
        )
        data = response.json()

        # Purchase item to storage
        shop = data["session"]["current_shop"]
        item = next(offer for offer in shop if offer and not offer["is_container"])
        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": item["id"],
                "target_position": None,
                "to_storage": True,
            },
        )
        assert response.status_code == 200, response.text
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
        # Not simply the first slot: a container cannot be bought into
        # storage, and with an unseeded shop any slot may hold one.
        item = next(item for item in shop if item and not item["is_container"])
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
        response = auth_client.post(
            "/session/start",
            json={"player_name": "test_player", "seed": SHOP_SEED},
        )
        data = response.json()

        # Two items, and never a container: one bought at [2, 3] would overlap a
        # container already there, and the first two offers of an unseeded shop
        # could be anything.
        shop = data["session"]["current_shop"]
        items = [offer for offer in shop if offer and not offer["is_container"]][:2]

        # Place first item
        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": items[0]["id"],
                "target_position": [2, 3],
            },
        )
        assert response.status_code == 200, response.text

        # Place second item
        response = auth_client.post(
            "/purchase/item",
            json={
                "item_id": items[1]["id"],
                "target_position": [4, 3],
            },
        )
        assert response.status_code == 200, response.text
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
        # Not simply the first slot: a container cannot be bought into
        # storage, and with an unseeded shop any slot may hold one.
        item = next(item for item in shop if item and not item["is_container"])
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
        # Not simply the first slot: a container cannot be bought into
        # storage, and with an unseeded shop any slot may hold one.
        item = next(item for item in shop if item and not item["is_container"])
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


def rack_holding(user_id, *placements):
    """Put these items on the player's grid, as if they had bought them.

    A module function rather than a method, so every class that needs a rig
    calls the same one.
    """
    import asyncio

    from items import Item
    from session_manager import session_manager

    async def rig():
        session = await session_manager.get_session(str(user_id))
        session.inventory_grid = [
            Item.of(item_type, f"item{n}").placed_at(position)
            for n, (item_type, position) in enumerate(placements)
        ]
        await session_manager.update_session(session)

    asyncio.run(rig())


class TestItemsCombineAfterTheBattle:
    """GDD 5.3, over the wire.

    The unit tests cover which items combine. This covers that it happens at
    all when a battle ends, and that the client is told.
    """

    def test_a_rack_that_can_craft_does_so_when_the_battle_ends(self, auth_client):
        auth_client.post(
            "/session/start", json={"player_name": "Tester", "seed": SHOP_SEED}
        )
        rack_holding(
            auth_client.user_id,
            ("neural_link_collar", [2, 3]), ("cpu_booster", [3, 3]),
        )

        result = auth_client.post(
            "/battle/simulate", json={"test_ai_difficulty": 1, "seed": 7}
        )
        assert result.status_code == 200, result.text
        combinations = result.json()["session_update"]["combinations"]

        assert [c["made"] for c in combinations] == ["blue_sage_collar"]
        # Whole items, not names: the client has no catalogue to draw from, and
        # with two of a kind on the rack a name would not say which was eaten.
        eaten = combinations[0]["consumed"]
        assert [i["item_type"] for i in eaten] == ["neural_link_collar", "cpu_booster"]
        assert [i["position"] for i in eaten] == [[2, 3], [3, 3]]
        assert all(i["shape"] and i["color"] for i in eaten), "enough to draw them"

        after = auth_client.get("/session").json()
        assert [i["item_type"] for i in after["inventory_grid"]] == ["blue_sage_collar"]

    def test_the_client_is_told_where_to_play_the_animation(self, auth_client):
        auth_client.post(
            "/session/start", json={"player_name": "Tester", "seed": SHOP_SEED}
        )
        rack_holding(
            auth_client.user_id,
            ("neural_link_collar", [2, 3]), ("cpu_booster", [3, 3]),
        )
        made = auth_client.post(
            "/battle/simulate", json={"test_ai_difficulty": 1, "seed": 7}
        ).json()["session_update"]["combinations"][0]

        assert sorted(made["freed"]) == [[2, 3], [3, 3]], "the squares to play over"
        assert made["position"] == [2, 3], "and where the result ends up"
        assert made["made_id"], "the item it becomes"

    def test_the_response_says_what_the_player_holds_now(self, auth_client):
        """The client has no other way to find out.

        Nothing on the client fetches the session, and it restores the rack from
        its own cache, so without this the crafted item would never appear.
        battle_result.player_inventory is no help: that is the rack that fought.
        """
        auth_client.post(
            "/session/start", json={"player_name": "Tester", "seed": SHOP_SEED}
        )
        rack_holding(
            auth_client.user_id,
            ("neural_link_collar", [2, 3]), ("cpu_booster", [3, 3]),
        )
        body = auth_client.post(
            "/battle/simulate", json={"test_ai_difficulty": 1, "seed": 7}
        ).json()

        fought_with = [
            i["item_type"] for i in body["battle_result"]["player_inventory"]["items"]
        ]
        holds_now = [i["item_type"] for i in body["inventory"]["inventory_grid"]]
        assert fought_with == ["neural_link_collar", "cpu_booster"], "the rack before"
        assert holds_now == ["blue_sage_collar"], "and the rack after"
        assert body["inventory"]["server_containers"], "the racks come too"

    def test_a_result_that_does_not_fit_is_in_the_chest(self, auth_client):
        """The one case where the result is not on the grid at all.

        Long Poll is three squares tall and its ingredients free a two by two,
        so it has nowhere to stand. The client is told it went to the chest by
        `position` being null, and finds it there under the id it was given.
        """
        auth_client.post(
            "/session/start", json={"player_name": "Tester", "seed": SHOP_SEED}
        )
        rack_holding(
            auth_client.user_id,
            ("hero_sword", [2, 3]), ("whetstone", [3, 3]), ("whetstone", [3, 4]),
        )
        body = auth_client.post(
            "/battle/simulate", json={"test_ai_difficulty": 1, "seed": 7}
        ).json()

        made = body["session_update"]["combinations"][0]
        assert made["made"] == "hero_longsword"
        assert made["position"] is None, "null means it went to the chest"

        assert body["inventory"]["inventory_grid"] == [], "nothing left on the rack"
        chest = body["inventory"]["inventory_storage"]
        assert [i["id"] for i in chest] == [made["made_id"]], (
            "and it is in the chest under the id the client was told"
        )


    def test_a_rack_that_cannot_craft_reports_nothing(self, auth_client):
        auth_client.post(
            "/session/start", json={"player_name": "Tester", "seed": SHOP_SEED}
        )
        rack_holding(
            auth_client.user_id,
            ("null_blade", [2, 3])
        )
        result = auth_client.post(
            "/battle/simulate", json={"test_ai_difficulty": 1, "seed": 7}
        ).json()
        assert result["session_update"]["combinations"] == []


class TestTheClientIsWarnedBeforeItemsCombine:
    """GDD 5.3, the warning half.

    Combining happens when the battle starts, and by then it is too late to
    change your mind. So every response that can change the rack says what the
    rack is now on the way to, and the client draws the glow and the progress
    from it. The unit tests cover which recipes are reported; this covers that
    the field reaches the wire on each of them.
    """

    def _started(self, auth_client):
        auth_client.post(
            "/session/start", json={"player_name": "Tester", "seed": SHOP_SEED}
        )
        return auth_client

    def test_a_rack_that_will_combine_says_so_before_the_battle(self, auth_client):
        self._started(auth_client)
        rack_holding(
            auth_client.user_id,
            ("neural_link_collar", [2, 3]),
            ("cpu_booster", [3, 3]),
        )

        pending = auth_client.get("/session").json()["pending"]

        assert len(pending) == 1, pending
        [warned] = pending
        assert warned["makes"] == "blue_sage_collar"
        assert (warned["have"], warned["need"]) == (2, 2), "all there: this will happen"
        assert sorted(warned["ingredients"]) == ["item0", "item1"], "which items glow"
        assert warned["missing"] == []

    def test_a_part_way_rack_reports_its_progress(self, auth_client):
        """Two of the three parts of a Hero Longsword.

        This is what a "Hero Longsword 2/3" label is drawn from, and `missing`
        is what the player still has to find.
        """
        self._started(auth_client)
        rack_holding(
            auth_client.user_id,
            ("hero_sword", [2, 3]),
            ("whetstone", [3, 3]),
        )

        [warned] = auth_client.get("/session").json()["pending"]

        assert warned["makes"] == "hero_longsword"
        assert (warned["have"], warned["need"]) == (2, 3)
        assert warned["missing"] == ["whetstone"]

    def test_parts_that_do_not_touch_are_not_reported(self, auth_client):
        """Owning the parts is not enough. They have to be together."""
        self._started(auth_client)
        rack_holding(
            auth_client.user_id,
            ("neural_link_collar", [2, 3]),
            ("cpu_booster", [6, 6]),
        )

        assert auth_client.get("/session").json()["pending"] == []

    def test_moving_a_part_next_to_another_reports_it_at_once(self, auth_client):
        """The move that makes the pair is the move that must say so.

        The client has no catalogue of recipes and no rules for what combines,
        so if this response were silent nothing would light up until the round
        after.
        """
        self._started(auth_client)
        rack_holding(
            auth_client.user_id,
            ("neural_link_collar", [2, 3]),
            ("cpu_booster", [6, 6]),
        )

        moved = auth_client.post(
            "/move/item", json={"item_id": "item1", "to_location": [3, 3]}
        )

        assert moved.status_code == 200, moved.text
        assert [p["makes"] for p in moved.json()["pending"]] == ["blue_sage_collar"]

    def test_moving_a_part_away_takes_the_warning_back(self, auth_client):
        self._started(auth_client)
        rack_holding(
            auth_client.user_id,
            ("neural_link_collar", [2, 3]),
            ("cpu_booster", [3, 3]),
        )

        moved = auth_client.post(
            "/move/item", json={"item_id": "item1", "to_location": "storage"}
        )

        assert moved.status_code == 200, moved.text
        assert moved.json()["pending"] == [], "the chest is not the rack"

    def test_selling_a_part_takes_the_warning_back(self, auth_client):
        self._started(auth_client)
        rack_holding(
            auth_client.user_id,
            ("neural_link_collar", [2, 3]),
            ("cpu_booster", [3, 3]),
        )

        sold = auth_client.post("/sell/item", json={"item_id": "item1"})

        assert sold.status_code == 200, sold.text
        assert sold.json()["pending"] == []

    def test_buying_anything_reports_the_rack_as_it_now_stands(self, auth_client):
        """A purchase can complete a recipe, so its response carries it too.

        What is bought here does not matter -- the shop is rolled, not chosen.
        The pair is already on the rack, and the point is that the purchase
        response knows about it.
        """
        self._started(auth_client)
        rack_holding(
            auth_client.user_id,
            ("neural_link_collar", [2, 3]),
            ("cpu_booster", [3, 3]),
        )
        offered = auth_client.get("/session").json()["current_shop"][0]

        bought = auth_client.post(
            "/purchase/item", json={"item_id": offered["id"], "to_storage": True}
        )

        assert bought.status_code == 200, bought.text
        assert [p["makes"] for p in bought.json()["pending"]] == ["blue_sage_collar"]

    def test_what_was_promised_is_what_happens(self, auth_client):
        """The warning and the combining read one plan, so they cannot differ."""
        self._started(auth_client)
        rack_holding(
            auth_client.user_id,
            ("neural_link_collar", [2, 3]),
            ("cpu_booster", [3, 3]),
            ("hero_sword", [5, 3]),
            ("whetstone", [6, 3]),
        )
        promised = [
            p["makes"] for p in auth_client.get("/session").json()["pending"]
            if p["have"] == p["need"]
        ]

        happened = auth_client.post(
            "/battle/simulate", json={"test_ai_difficulty": 1, "seed": 7}
        ).json()["session_update"]["combinations"]

        assert promised == ["blue_sage_collar"]
        assert [c["made"] for c in happened] == promised

    def test_the_battle_answer_says_what_the_rack_is_on_the_way_to_now(
        self, auth_client
    ):
        """The rack changes under the player while they watch the battle.

        Combining runs as the shop phase begins, so the first sight of the new
        rack is the shop screen. Without this it would show no glow and no
        progress until the player moved something.
        """
        auth_client.post(
            "/session/start", json={"player_name": "Tester", "seed": SHOP_SEED}
        )
        rack_holding(
            auth_client.user_id,
            # These two combine.
            ("neural_link_collar", [2, 3]), ("cpu_booster", [3, 3]),
            # These two do not: a Long Poll wants a second Edge Cache.
            ("hero_sword", [6, 3]), ("whetstone", [7, 3]),
        )

        after = auth_client.post(
            "/battle/simulate", json={"test_ai_difficulty": 1, "seed": 7}
        ).json()["session_update"]

        assert [c["made"] for c in after["combinations"]] == ["blue_sage_collar"]
        assert [(p["makes"], p["have"], p["need"]) for p in after["pending"]] == [
            ("hero_longsword", 2, 3)
        ]


class TestStandingItemsOnTheRackForATest:
    """The hook a client test uses to set a board up. TEST MODE only.

    A test that wants two particular items together cannot buy them: the shop
    offers what the seed says it offers, and hunting for a seed that offers a
    pair is a search rather than a test.
    """

    def test_it_stands_the_items_where_it_is_told(self, auth_client):
        auth_client.post("/session/start", json={"player_name": "Tester"})

        answered = auth_client.post("/test/rack", json={
            "player_id": str(auth_client.user_id), "items": [
            {"item_type": "neural_link_collar", "position": [2, 3]},
            {"item_type": "cpu_booster", "position": [3, 3]},
        ]})

        assert answered.status_code == 200, answered.text
        rack = answered.json()["inventory_grid"]
        assert [item["item_type"] for item in rack] == [
            "neural_link_collar", "cpu_booster"
        ]
        assert [item["position"] for item in rack] == [[2, 3], [3, 3]]

    def test_the_rack_it_sets_is_the_rack_the_session_has(self, auth_client):
        auth_client.post("/session/start", json={"player_name": "Tester"})
        auth_client.post("/test/rack", json={
            "player_id": str(auth_client.user_id), "items": [
            {"item_type": "whetstone", "position": [2, 3]},
        ]})

        held = auth_client.get("/session").json()["inventory_grid"]

        assert [item["item_type"] for item in held] == ["whetstone"]

    def test_it_says_what_that_rack_is_on_the_way_to(self, auth_client):
        """So a client can set a board up and draw the glow without a move."""
        auth_client.post("/session/start", json={"player_name": "Tester"})

        answered = auth_client.post("/test/rack", json={
            "player_id": str(auth_client.user_id), "items": [
            {"item_type": "neural_link_collar", "position": [2, 3]},
            {"item_type": "cpu_booster", "position": [3, 3]},
        ]}).json()

        assert [(p["makes"], p["have"], p["need"]) for p in answered["pending"]] == [
            ("blue_sage_collar", 2, 2)
        ]

    def test_it_replaces_the_rack_rather_than_adding_to_it(self, auth_client):
        auth_client.post("/session/start", json={"player_name": "Tester"})
        auth_client.post("/test/rack", json={
            "player_id": str(auth_client.user_id), "items": [
            {"item_type": "whetstone", "position": [2, 3]},
        ]})

        answered = auth_client.post("/test/rack", json={
            "player_id": str(auth_client.user_id), "items": [
            {"item_type": "cpu_booster", "position": [4, 3]},
        ]})

        assert [item["item_type"] for item in answered.json()["inventory_grid"]] == [
            "cpu_booster"
        ], "a test setting the board up wants the board it asked for"

    def test_an_item_that_does_not_exist_is_refused(self, auth_client):
        auth_client.post("/session/start", json={"player_name": "Tester"})

        answered = auth_client.post("/test/rack", json={
            "player_id": str(auth_client.user_id), "items": [
            {"item_type": "no_such_item", "position": [2, 3]},
        ]})

        assert answered.status_code == 400, "a typo in a test is a failed test"

    def test_it_needs_a_session(self, auth_client):
        answered = auth_client.post("/test/rack", json={
            "player_id": str(auth_client.user_id), "items": []})

        assert answered.status_code == 404


class TestWhichItemsGoTogether:
    """GDD 5.3, the line the client draws on hover and while dragging.

    A fact about the catalogue, not about a rack, so it is answered once and
    kept. A line means these two appear in a recipe together, nothing more.
    """

    def test_the_catalogue_answers_without_a_session(self):
        """It is wanted in the shop, before a rack exists."""
        from fastapi.testclient import TestClient

        from main import app

        answered = TestClient(app).get("/catalogue/combining")

        assert answered.status_code == 200, answered.text
        assert answered.json()["partners"], "and it is not empty"

    def test_a_pair_is_named_from_both_ends(self, auth_client):
        """The player may pick up either one, so either one must draw the line."""
        partners = auth_client.get("/catalogue/combining").json()["partners"]

        assert "cpu_booster" in partners["neural_link_collar"]
        assert "neural_link_collar" in partners["cpu_booster"]

    def test_an_item_that_wants_two_of_itself_pairs_with_itself(self, auth_client):
        """A Hero Longsword eats two whetstones, so one whetstone points at another."""
        partners = auth_client.get("/catalogue/combining").json()["partners"]

        assert "whetstone" in partners["whetstone"]

    def test_an_item_in_no_recipe_is_absent(self, auth_client):
        partners = auth_client.get("/catalogue/combining").json()["partners"]

        assert "null_blade" in partners, "setup: this one is in a recipe"
        assert "bloodthorne" not in partners, "a result, and in no recipe itself"

    def test_every_partner_is_a_real_item(self, auth_client):
        """A line to an item that does not exist would be drawn to nowhere."""
        from config_loader import config_loader

        partners = auth_client.get("/catalogue/combining").json()["partners"]
        known = set(config_loader.items) | set(config_loader.containers)

        unknown = {
            slug
            for one, others in partners.items()
            for slug in [one, *others]
            if slug not in known
        }
        assert unknown == set(), f"partners nothing can be: {sorted(unknown)}"

    def test_it_carries_a_name_for_everything_it_could_have_to_name(self, auth_client):
        """The client holds no catalogue.

        It can name an item the server has sent it and nothing else, so a
        recipe's result -- which does not exist yet -- and a part still missing
        would both be a slug on screen without this.
        """
        answered = auth_client.get("/catalogue/combining").json()
        names = answered["names"]

        assert names["hero_longsword"] == "Long Poll", "what a recipe makes"
        assert names["whetstone"] == "Edge Cache", "a part still wanted"
        for one, others in answered["partners"].items():
            for slug in [one, *others]:
                assert slug in names, f"{slug} has no name to show"
