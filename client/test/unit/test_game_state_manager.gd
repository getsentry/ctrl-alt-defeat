extends GutTest
# Comprehensive tests for GameStateManager singleton

func test_singleton_exists():
	assert_not_null(GameStateManager, "GameStateManager singleton should exist")

func test_start_new_game():
	GameStateManager.start_new_game()

	assert_eq(GameStateManager.current_round, 1, "Should start at round 1")
	assert_eq(GameStateManager.gold, 12, "Should start with 12 gold")
	assert_eq(GameStateManager.player_lives, 5, "Should start with 5 lives")
	assert_eq(GameStateManager.player_health, 100, "Should start with 100 health")
	assert_eq(GameStateManager.wins, 0, "Should have 0 wins")
	assert_eq(GameStateManager.losses, 0, "Should have 0 losses")
	assert_false(GameStateManager.game_over, "Should not be game over")
	assert_false(GameStateManager.victory, "Should not be victory")

func test_starting_containers_property_exists():
	# This tests the bug fix - GameStateManager should have starting_containers
	assert_true("starting_containers" in GameStateManager,
		"GameStateManager should have starting_containers property")

func test_can_set_and_get_starting_containers():
	var test_containers = [
		{"type": "cube_2x2", "position": Vector2i(1, 3)},
		{"type": "cube_2x2", "position": Vector2i(4, 3)}
	]

	GameStateManager.starting_containers = test_containers

	assert_eq(GameStateManager.starting_containers.size(), 2,
		"Should have 2 containers after setting")
	assert_eq(GameStateManager.starting_containers[0].type, "cube_2x2",
		"First container should be cube_2x2")

func test_start_new_game_clears_starting_containers():
	# Setup: add some containers
	GameStateManager.starting_containers = [{"type": "test"}]
	assert_eq(GameStateManager.starting_containers.size(), 1, "Setup failed")

	# Test: start_new_game should clear them
	GameStateManager.start_new_game()

	assert_eq(GameStateManager.starting_containers.size(), 0,
		"starting_containers should be empty after start_new_game()")

func test_inventory_persistence():
	GameStateManager.start_new_game()

	# Save some inventory
	var test_items = [
		{"data": {"name": "CPU", "width": 1}, "grid_pos": Vector2i(2, 2)}
	]
	var test_servers = [
		{"data": {"name": "Rack"}, "pos": Vector2i(0, 0)}
	]

	GameStateManager.save_inventory_state(test_items, test_servers)

	# Retrieve and verify
	var saved = GameStateManager.get_inventory_state()
	assert_eq(saved.items.size(), 1, "Should have 1 item saved")
	assert_eq(saved.servers.size(), 1, "Should have 1 server saved")

func test_battle_result_updates_state():
	GameStateManager.start_new_game()
	var initial_gold = GameStateManager.gold

	# Simulate battle result
	var mock_result = {
		"battle_result": {"winner": 1},
		"session_update": {
			"round": 2,
			"gold": initial_gold + 10,
			"wins": 1,
			"losses": 0
		}
	}

	GameStateManager.update_after_battle(mock_result)

	assert_eq(GameStateManager.current_round, 2, "Round should be 2")
	assert_eq(GameStateManager.gold, initial_gold + 10, "Gold should increase")
	assert_eq(GameStateManager.wins, 1, "Should have 1 win")

func test_game_over_conditions():
	GameStateManager.start_new_game()

	# Test not game over initially
	assert_false(GameStateManager.is_game_over(), "Should not be game over initially")

	# Test game over when lives reach 0
	GameStateManager.player_lives = 0
	assert_true(GameStateManager.is_game_over(), "Should be game over at 0 lives")

	# Test game over flag
	GameStateManager.player_lives = 5
	GameStateManager.game_over = true
	assert_true(GameStateManager.is_game_over(), "Should respect game_over flag")

func test_round_quota_calculations():
	# Test quota for different rounds
	GameStateManager.current_round = 1
	assert_eq(GameStateManager.get_round_quota(), 25, "Round 1 quota should be 25")

	GameStateManager.current_round = 5
	assert_eq(GameStateManager.get_round_quota(), 35, "Round 5 quota should be 35")

	GameStateManager.current_round = 10
	assert_eq(GameStateManager.get_round_quota(), 75, "Round 10 quota should be 75")
