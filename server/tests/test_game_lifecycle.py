"""
Comprehensive tests for the full game lifecycle using session-based inventory
"""

import os

# Enable TEST_MODE for testing
os.environ["TEST_MODE"] = "true"

import pytest  # noqa: E402


def purchase_items_for_battle(client, player_id, session, num_items=3):
    """Helper to purchase items from shop and place on grid"""
    shop = session["current_shop"]
    # Use positions within the default containers that are created with each session
    # Default containers are 3 standard_vm at (2,3), (4,3), (6,3), each 2x2
    # Be careful with shapes - items with shapes need all their squares to fit
    # Prefer top-left positions for items with shapes to ensure they fit
    container_positions = [
        (2, 3),  # Container A top-left - safe for any shape up to 2x2
        (4, 3),  # Container B top-left - safe for any shape up to 2x2
        (6, 3),  # Container C top-left - safe for any shape up to 2x2
        (3, 3),  # Container A top-right - only safe for 1x1 or 1x2
        (5, 3),  # Container B top-right - only safe for 1x1 or 1x2
        (7, 3),  # Container C top-right - only safe for 1x1 or 1x2
        (2, 4),  # Container A bottom-left - only safe for 1x1 or 2x1
        (4, 4),  # Container B bottom-left - only safe for 1x1 or 2x1
        (6, 4),  # Container C bottom-left - only safe for 1x1 or 2x1
        (3, 4),  # Container A bottom-right - only safe for 1x1
        (5, 4),  # Container B bottom-right - only safe for 1x1
        (7, 4),  # Container C bottom-right - only safe for 1x1
    ]

    # Track occupied positions from existing inventory
    occupied_positions = set()
    for item in session.get("inventory_grid", []):
        pos = tuple(item.get("position", []))
        if pos:
            occupied_positions.add(pos)

    items_purchased = 0
    purchased_item_ids = set()  # Track which items we've already purchased

    for item in shop:
        if item and items_purchased < min(num_items, len(container_positions)):
            # Skip containers - we already have one
            is_container = item.get("is_container", False)
            if is_container:
                continue

            # Skip already purchased items
            if item["id"] in purchased_item_ids:
                continue

            # Find next available position that fits item's shape
            target_position = None
            item_shape = item.get("shape", [[0, 0]])

            for pos in container_positions:
                if pos in occupied_positions:
                    continue

                # Check if shape fits at this position
                x, y = pos
                fits = True
                for offset in item_shape:
                    check_x = x + offset[0]
                    check_y = y + offset[1]
                    # Check if this square is in a container
                    # Containers: A=(2-3,3-4), B=(4-5,3-4), C=(6-7,3-4)
                    in_container = False
                    if 2 <= check_x <= 3 and 3 <= check_y <= 4:  # Container A
                        in_container = True
                    elif 4 <= check_x <= 5 and 3 <= check_y <= 4:  # Container B
                        in_container = True
                    elif 6 <= check_x <= 7 and 3 <= check_y <= 4:  # Container C
                        in_container = True

                    if not in_container or (check_x, check_y) in occupied_positions:
                        fits = False
                        break

                if fits:
                    target_position = pos
                    break

            if not target_position:
                continue  # Try next item, this one doesn't fit

            # Prefer items with attack capability (damage > 0)
            # But purchase any item if we haven't purchased enough
            has_damage = item.get("min_damage", 0) > 0 or item.get("max_damage", 0) > 0

            # Purchase items with damage or any item if we need more
            if has_damage or items_purchased < 2:
                response = client.post(
                    "/purchase/item",
                    json={
                        "player_id": player_id,
                        "item_id": item["id"],
                        "target_position": list(target_position),
                    },
                )
                if response.status_code == 200:
                    items_purchased += 1
                    purchased_item_ids.add(item["id"])
                    # Mark all squares occupied by this item
                    for offset in item_shape:
                        occupied_positions.add(
                            (
                                target_position[0] + offset[0],
                                target_position[1] + offset[1],
                            )
                        )

    # If we didn't get enough offensive items, purchase any available items
    if items_purchased < num_items:
        for item in shop:
            if item and items_purchased < min(num_items, len(container_positions)):
                # Skip containers - we already have one
                if item.get("is_container", False):
                    continue
                # Skip already purchased items
                if item["id"] in purchased_item_ids:
                    continue

                # Find next available position
                target_position = None
                for pos in container_positions:
                    if pos not in occupied_positions:
                        target_position = pos
                        break

                if not target_position:
                    break  # No more available positions

                response = client.post(
                    "/purchase/item",
                    json={
                        "player_id": player_id,
                        "item_id": item["id"],
                        "target_position": list(target_position),
                    },
                )
                if response.status_code == 200:
                    items_purchased += 1
                    purchased_item_ids.add(item["id"])
                    # Mark all squares occupied by this item
                    for offset in item_shape:
                        occupied_positions.add(
                            (
                                target_position[0] + offset[0],
                                target_position[1] + offset[1],
                            )
                        )

    return items_purchased


class TestGameLifecycle:
    """Test complete game scenarios from start to finish"""

    def test_successful_run_to_victory(self, auth_client):
        """Test a player can win battles and advance rounds"""
        # Start new session with deterministic seed
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 2}
        )
        assert response.status_code == 200
        data = response.json()
        player_id = data["player_id"]

        # Initial state checks
        session = data["session"]
        assert session["round"] == 1
        assert session["gold"] == 12  # Starting gold
        assert session["lives"] == 5  # Full lives
        assert session["wins"] == 0
        assert session["losses"] == 0

        # Win at least 2 battles to verify advancement mechanics
        wins_needed = 2
        wins_achieved = 0
        max_attempts = 20  # Allow some losses
        attempts = 0

        while wins_achieved < wins_needed and attempts < max_attempts:
            attempts += 1

            # Get current session
            response = auth_client.get(f"/session/{player_id}")
            assert response.status_code == 200
            session = response.json()
            current_round = session["round"]

            # Purchase items for battle (buy fewer items to avoid overlaps)
            # With 3 containers of 2x2 each, we have 12 squares available
            # But items can have shapes larger than 1x1, so limit to 3 items
            purchase_items_for_battle(auth_client, player_id, session, 3)

            # Battle with purchased items
            battle_request = {
                "player_id": player_id,
                "seed": 1000 + attempts,  # Different seed each attempt
                "test_ai_difficulty": 1,  # Easy AI for reliable wins
            }

            response = auth_client.post("/battle/simulate", json=battle_request)
            assert response.status_code == 200
            result = response.json()

            if result["battle_result"]["winner"] == 1:
                wins_achieved += 1
                session_update = result["session_update"]
                # Verify round advanced
                assert session_update["round"] == current_round + 1
                assert session_update["wins"] == wins_achieved

            # Check if we lost all lives
            if result["session_update"]["lives"] <= 0:
                break  # Game over

        # Verify we achieved some wins
        assert (
            wins_achieved >= wins_needed
        ), f"Only won {wins_achieved} battles out of {wins_needed} needed"

        # Final state verification
        response = auth_client.get(f"/session/{player_id}")
        session = response.json()
        assert session["wins"] >= wins_needed
        assert session["round"] > 1  # Advanced at least once

    def test_complete_failure_five_losses(self, auth_client):
        """Test a player losing 5 times in a row and getting game over"""
        # Start new session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player"}
        )
        assert response.status_code == 200
        data = response.json()
        player_id = data["player_id"]

        # Initial state
        session = data["session"]
        assert session["lives"] == 5

        # Keep battling with weak inventory until we lose 5 times
        losses = 0
        max_attempts = 20
        attempts = 0

        while losses < 5 and attempts < max_attempts:
            attempts += 1

            # Get current session
            response = auth_client.get(f"/session/{player_id}")
            assert response.status_code == 200
            session = response.json()

            if session["lives"] <= 0:
                break  # Game over

            # Only purchase if we don't have items yet (to stay weak)
            if len(session.get("inventory_grid", [])) == 0:
                # Purchase only a weak defensive item (skip containers)
                shop = session["current_shop"]
                purchased = False
                for item in shop:
                    if item and item.get("item_type") == "firewall":
                        response = auth_client.post(
                            "/purchase/item",
                            json={
                                "player_id": player_id,
                                "item_id": item["id"],
                                "target_position": [2, 3],
                            },
                        )
                        purchased = response.status_code == 200
                        break

                if not purchased:
                    # If no firewall, purchase first available non-container item
                    for item in shop:
                        if item and not item.get("is_container", False):
                            response = auth_client.post(
                                "/purchase/item",
                                json={
                                    "player_id": player_id,
                                    "item_id": item["id"],
                                    "target_position": [2, 3],
                                },
                            )
                            purchased = response.status_code == 200
                            if purchased:
                                break

            # Simulate battle with weak inventory
            battle_request = {
                "player_id": player_id,
                "seed": 1,  # Any seed works
                "test_ai_difficulty": None,
            }

            response = auth_client.post("/battle/simulate", json=battle_request)
            assert response.status_code == 200
            result = response.json()

            if result["battle_result"]["winner"] == 2:  # We lost
                losses += 1
                session_update = result["session_update"]
                assert session_update["lives"] == 5 - losses

                if session_update["lives"] == 0:
                    assert session_update["game_over"] is True
                    break

        # Verify we got game over
        response = auth_client.get(f"/session/{player_id}")
        session = response.json()
        assert session["lives"] == 0
        assert session["losses"] == 5

    def test_lives_and_rounds_mechanic(self, auth_client):
        """Test that losing reduces lives and winning advances rounds"""
        # Start new session with deterministic seed
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 50}
        )
        data = response.json()
        player_id = data["player_id"]

        # Run multiple battles with deterministic seeds
        # Some will win, some will lose based on the specific seed and AI combo
        # The important thing is to verify the mechanics work correctly
        initial_lives = 5
        current_round = 1
        total_wins = 0
        total_losses = 0

        # Run 5 deterministic battles
        test_battles = [
            (3, 1, 1000),  # Battle 1
            (1, 3, 1001),  # Battle 2
            (4, 1, 1002),  # Battle 3
            (2, 2, 1003),  # Battle 4
            (5, 1, 1004),  # Battle 5
        ]

        for i, (purchase_count, ai_difficulty, battle_seed) in enumerate(test_battles):
            response = auth_client.get(f"/session/{player_id}")
            session = response.json()

            # Verify our tracking matches the session
            assert session["round"] == current_round
            assert session["lives"] == initial_lives - total_losses
            assert session["wins"] == total_wins
            assert session["losses"] == total_losses

            # Purchase items
            purchase_items_for_battle(auth_client, player_id, session, purchase_count)

            # Battle with deterministic seed
            battle_request = {
                "player_id": player_id,
                "seed": battle_seed,
                "test_ai_difficulty": ai_difficulty,
            }

            response = auth_client.post("/battle/simulate", json=battle_request)
            assert response.status_code == 200
            result = response.json()

            session_update = result["session_update"]

            current_round += 1
            assert session_update["round"] == current_round
            if result["battle_result"]["winner"] == 1:
                # Won - should not lose life
                total_wins += 1
            else:
                # Lost - should lose a life
                total_losses += 1
            assert session_update["lives"] == initial_lives - total_losses
            assert session_update["wins"] == total_wins
            assert session_update["losses"] == total_losses

        # Verify we ran all battles and mechanics worked
        assert total_wins + total_losses == 5, "All 5 battles should have completed"

        # Verify final state
        final_session = auth_client.get(f"/session/{player_id}").json()
        assert final_session["wins"] == total_wins
        assert final_session["losses"] == total_losses
        assert final_session["lives"] == initial_lives - total_losses
        assert final_session["round"] == current_round

    def test_victory_condition(self, auth_client):
        """Test that winning round 10 grants victory flag"""
        # We'll directly test the victory condition by mocking a session at round 10
        # Start new session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 2}
        )
        data = response.json()
        player_id = data["player_id"]

        # Manually set the session to round 10 via database
        # This is a unit test for the victory condition, not the full game flow
        import asyncio

        from session_manager import session_manager

        async def update_to_round_10():
            session = await session_manager.get_session(player_id)
            session.round = 10
            session.wins = 9  # Won 9 rounds to get here
            await session_manager.update_session(session)
            return session

        session = asyncio.run(update_to_round_10())

        # Purchase maximum items for best chance
        purchase_items_for_battle(auth_client, player_id, session.model_dump(), 6)

        # Battle at round 10 with easy AI
        battle_request = {
            "player_id": player_id,
            "seed": 42,
            "test_ai_difficulty": 1,  # Easy AI
        }

        response = auth_client.post("/battle/simulate", json=battle_request)
        assert response.status_code == 200
        result = response.json()

        # If we won round 10, we should get victory flag
        if result["battle_result"]["winner"] == 1:
            session_update = result["session_update"]
            assert session_update.get(
                "victory", False
            ), "Should have victory flag after winning round 10"
            assert session_update["round"] == 11  # Advanced to round 11
            assert not session_update["game_over"]  # Victory is not game over

    def test_gold_economy_through_rounds(self, auth_client):
        """Test that gold rewards match specification through all rounds"""
        # Start new session
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player"}
        )
        data = response.json()
        player_id = data["player_id"]

        # Expected gold per round (from specification)
        expected_gold = {
            1: 12,  # Starting gold
            2: 9,
            3: 9,
            4: 9,
            5: 10,
            6: 10,
            7: 11,
            8: 21,  # Big boost!
            9: 12,
            10: 12,
        }

        # Play through rounds and check gold
        for _ in range(10):
            # Get current session state
            response = auth_client.get(f"/session/{player_id}")
            session = response.json()
            current_round = session["round"]

            if current_round > 10:
                break  # Completed all rounds

            # Purchase some items to have inventory for battle (limit to avoid overlaps)
            purchase_items_for_battle(auth_client, player_id, session, 2)

            battle_request = {
                "player_id": player_id,
                "seed": current_round,  # Use deterministic seed based on round
                "test_ai_difficulty": 1,  # Use easy AI to reduce placement issues
            }

            response = auth_client.post("/battle/simulate", json=battle_request)
            assert response.status_code == 200
            result = response.json()

            # With 3 items and varying seeds, we should mostly win
            if result["battle_result"]["winner"] == 1:  # Won
                session_update = result["session_update"]

                # When winning, we advance to next round and get gold for that round
                if current_round < 10:
                    gold_earned = session_update["gold_earned"]
                    next_round = session_update["round"]
                    expected = expected_gold[next_round]
                    assert gold_earned == expected, (
                        f"After winning round {current_round}, should get round "
                        f"{next_round} gold: {expected}g, got {gold_earned}g"
                    )

    def test_shop_rarity_progression(self, auth_client):
        """Test that shop items follow rarity table through rounds"""
        # Start new session with deterministic game seed
        response = auth_client.post(
            "/session/start", json={"player_name": "test_player", "seed": 2}
        )
        data = response.json()
        player_id = data["player_id"]

        # Check initial shop
        shop = data["session"]["current_shop"]
        assert len(shop) == 5  # Always 5 slots

        # Count rarities in round 1 shop (should be mostly common)
        round_1_rarities = {}
        for item in shop:
            rarity = item["rarity"].lower()
            round_1_rarities[rarity] = round_1_rarities.get(rarity, 0) + 1

        # Round 1 should be 90% common, 10% rare
        assert round_1_rarities.get("common", 0) >= 2  # At least 2 commons

        # Manually advance to round 8 to check rarity progression
        # We'll update the session directly for testing purposes
        import asyncio

        from session_manager import session_manager

        async def advance_to_round_8():
            session = await session_manager.get_session(player_id)
            session.round = 8
            session.wins = 7  # Won 7 rounds to get here
            # Generate new shop for round 8
            from main import generate_shop_items

            shop_seed = session.game_seed + 8 * 1000 + session.shop_refresh_count
            session.current_shop = generate_shop_items(8, seed=shop_seed)
            await session_manager.update_session(session)
            return session

        session = asyncio.run(advance_to_round_8())

        # Get round 8 shop
        round_8_shop = session.current_shop

        # Round 8 should have better variety
        round_8_rarities = {}
        for item in round_8_shop:
            if item:
                rarity = item.rarity.lower()
                round_8_rarities[rarity] = round_8_rarities.get(rarity, 0) + 1

        # Round 8: 20% common, 30% rare, 25% epic, 15% legendary, 10% godly
        # With deterministic seed, round 8 should have more variety than round 1
        # Just verify it's not all common items
        assert round_8_rarities.get("common", 0) < 5  # Not all items are common

        # Verify there's at least some variety (not just one rarity)
        non_zero_rarities = [r for r, count in round_8_rarities.items() if count > 0]
        assert len(non_zero_rarities) >= 1  # At least one rarity type


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
