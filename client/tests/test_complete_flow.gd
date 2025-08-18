extends SceneTree
# Test the complete game flow

func _init():
	print("\n=== Testing Complete Game Flow ===")

	# Test 1: Start new game
	print("\nTest 1: Starting new game...")
	GameStateManager.start_new_game()
	assert(GameStateManager.gold == 10, "Should start with 10 gold")
	assert(GameStateManager.current_round == 1, "Should start at round 1")
	assert(GameStateManager.player_health == 100, "Should start with 100 health")
	print("✓ New game initialized correctly")

	# Test 2: Simulate inventory setup
	print("\nTest 2: Setting up inventory...")
	var test_items = [
		{"data": {"name": "CPU", "width": 1, "height": 1, "cost": 3}, "grid_pos": Vector2i(2, 2)},
		{"data": {"name": "RAM", "width": 2, "height": 1, "cost": 4}, "grid_pos": Vector2i(3, 3)}
	]
	var test_servers = [
		{"data": {"name": "Rack", "pattern": [[1,1],[1,1]], "cost": 5}, "pos": Vector2i(0, 0)}
	]

	GameStateManager.save_inventory_state(test_items, test_servers)
	var saved = GameStateManager.get_inventory_state()
	assert(saved.items.size() == 2, "Should have 2 items saved")
	assert(saved.servers.size() == 1, "Should have 1 server saved")
	print("✓ Inventory saved successfully")

	# Test 3: Simulate battle
	print("\nTest 3: Simulating battle...")
	var mock_result = {
		"battle_result": {
			"winner": 1,
			"duration": 15.0,
			"player1_quota": 15,
			"player2_quota": 0,
			"actions": [
				{"t": 0.0, "a": "s"},
				{"t": 1.0, "a": "d", "p": 2, "dmg": 10}
			]
		},
		"session_update": {
			"round": 2,
			"gold": 22,
			"wins": 1,
			"losses": 0
		},
		"health_lost": 0
	}

	GameStateManager.update_after_battle(mock_result)
	assert(GameStateManager.current_round == 2, "Should be round 2 after battle")
	assert(GameStateManager.gold == 22, "Should have 22 gold after winning")
	print("✓ Battle results processed correctly")

	# Test 4: Check inventory persistence
	print("\nTest 4: Checking inventory persistence...")
	var after_battle = GameStateManager.get_inventory_state()
	assert(after_battle.items.size() == 2, "Items should persist after battle")
	assert(after_battle.servers.size() == 1, "Servers should persist after battle")
	print("✓ Inventory persisted through battle")

	# Test 5: Simulate losing
	print("\nTest 5: Simulating loss...")
	var loss_result = {
		"battle_result": {
			"winner": 2,
			"player2_quota": 20
		},
		"health_lost": 14  # Calculated from remaining enemy HP
	}

	var health_before = GameStateManager.player_health
	GameStateManager.update_after_battle(loss_result)
	assert(GameStateManager.player_health == health_before - 14, "Should lose health on defeat")
	print("✓ Health loss calculated correctly")

	# Test 6: Check game over
	print("\nTest 6: Testing game over condition...")
	GameStateManager.player_health = 5
	assert(not GameStateManager.is_game_over(), "Should not be game over at 5 HP")
	GameStateManager.player_health = 0
	assert(GameStateManager.is_game_over(), "Should be game over at 0 HP")
	print("✓ Game over detection works")

	print("\n✅ All game flow tests passed!")
	quit(0)
