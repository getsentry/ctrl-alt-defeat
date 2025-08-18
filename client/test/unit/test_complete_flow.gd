extends GutTest
# Test the complete game flow using GUT

func before_each():
	# Reset state before each test
	GameStateManager.start_new_game()

func test_new_game_initialization():
	# Test 1: Start new game
	GameStateManager.start_new_game()
	assert_eq(GameStateManager.gold, 12, "Should start with 12 gold")
	assert_eq(GameStateManager.current_round, 1, "Should start at round 1")
	assert_eq(GameStateManager.player_lives, 5, "Should start with 5 lives")

func test_inventory_setup_and_save():
	# Test 2: Setting up inventory
	var test_items = [
		{"data": {"name": "CPU", "width": 1, "height": 1, "cost": 3}, "grid_pos": Vector2i(2, 2)},
		{"data": {"name": "RAM", "width": 2, "height": 1, "cost": 4}, "grid_pos": Vector2i(3, 3)}
	]
	var test_servers = [
		{"data": {"name": "Rack", "pattern": [[1,1],[1,1]], "cost": 5}, "pos": Vector2i(0, 0)}
	]
	
	GameStateManager.save_inventory_state(test_items, test_servers)
	var saved = GameStateManager.get_inventory_state()
	assert_eq(saved.items.size(), 2, "Should have 2 items saved")
	assert_eq(saved.servers.size(), 1, "Should have 1 server saved")

func test_battle_simulation():
	# Test 3: Simulating battle
	var initial_round = GameStateManager.current_round
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
			"round": initial_round + 1,
			"gold": 22,
			"wins": 1,
			"losses": 0
		},
		"health_lost": 0
	}
	
	GameStateManager.update_after_battle(mock_result)
	assert_eq(GameStateManager.current_round, initial_round + 1, "Should advance round after battle")
	assert_eq(GameStateManager.gold, 22, "Should have 22 gold after winning")
	assert_eq(GameStateManager.wins, 1, "Should have 1 win")

func test_inventory_persistence_after_battle():
	# Test 4: Check inventory persistence
	# Setup inventory
	var test_items = [
		{"data": {"name": "CPU", "width": 1, "height": 1}, "grid_pos": Vector2i(2, 2)}
	]
	var test_servers = [
		{"data": {"name": "Rack", "pattern": [[1,1],[1,1]]}, "pos": Vector2i(0, 0)}
	]
	GameStateManager.save_inventory_state(test_items, test_servers)
	
	# Simulate battle
	var mock_result = {
		"battle_result": {"winner": 1},
		"session_update": {"round": 2, "gold": 20}
	}
	GameStateManager.update_after_battle(mock_result)
	
	# Check inventory still exists
	var after_battle = GameStateManager.get_inventory_state()
	assert_eq(after_battle.items.size(), 1, "Items should persist after battle")
	assert_eq(after_battle.servers.size(), 1, "Servers should persist after battle")

func test_losing_battle():
	# Test 5: Simulate losing
	var lives_before = GameStateManager.player_lives
	var loss_result = {
		"battle_result": {
			"winner": 2,
			"player2_quota": 20
		},
		"session_update": {
			"losses": 1,
			"lives": lives_before - 1
		}
	}
	
	GameStateManager.update_after_battle(loss_result)
	assert_eq(GameStateManager.player_lives, lives_before - 1, "Should lose a life on defeat")
	assert_eq(GameStateManager.losses, 1, "Should have 1 loss")

func test_game_over_detection():
	# Test 6: Check game over
	GameStateManager.player_lives = 5
	assert_false(GameStateManager.is_game_over(), "Should not be game over at 5 lives")
	
	GameStateManager.player_lives = 0
	assert_true(GameStateManager.is_game_over(), "Should be game over at 0 lives")
	
	# Also test game_over flag
	GameStateManager.player_lives = 3
	GameStateManager.game_over = true
	assert_true(GameStateManager.is_game_over(), "Should be game over when flag is set")