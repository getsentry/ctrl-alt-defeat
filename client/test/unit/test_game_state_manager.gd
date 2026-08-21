extends GutTest
# Comprehensive tests for GameStateManager singleton

const APITypes = preload("res://scripts/api_types.gd")

func test_singleton_exists():
	assert_not_null(GameStateManager, "GameStateManager singleton should exist")

func test_start_new_game():
	GameStateManager.start_new_game()

	assert_eq(GameStateManager.current_round, 1, "Should start at round 1")
	assert_eq(GameStateManager.gold, 12, "Should start with 12 gold")
	assert_eq(GameStateManager.player_lives, 5, "Should start with 5 lives")
	assert_eq(GameStateManager.wins, 0, "Should have 0 wins")
	assert_eq(GameStateManager.losses, 0, "Should have 0 losses")
	assert_false(GameStateManager.game_over, "Should not be game over")
	assert_false(GameStateManager.victory, "Should not be victory")

func test_server_containers_property_exists():
	assert_true("server_containers" in GameStateManager,
		"GameStateManager should have server_containers property")

func test_can_set_and_get_server_containers():
	var test_containers = [
		{"item_type": "cube_2x2", "position": [1, 3]},
		{"item_type": "cube_2x2", "position": [4, 3]}
	]

	GameStateManager.server_containers = test_containers

	assert_eq(GameStateManager.server_containers.size(), 2,
		"Should have 2 containers after setting")
	assert_eq(GameStateManager.server_containers[0].item_type, "cube_2x2",
		"First container should be cube_2x2")

func test_start_new_game_clears_server_containers():
	# Setup: add some containers
	GameStateManager.server_containers = [{"item_type": "test"}]
	assert_eq(GameStateManager.server_containers.size(), 1, "Setup failed")

	# Test: start_new_game should clear them
	GameStateManager.start_new_game()

	assert_eq(GameStateManager.server_containers.size(), 0,
		"server_containers should be empty after start_new_game()")

func test_inventory_persistence():
	GameStateManager.start_new_game()

	# Save some inventory
	var test_items = [
		{"data": {"name": "CPU", "shape": [[0, 0]], "width": 1}, "grid_pos": Vector2i(2, 2)}
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

	# Create typed BattleResponse
	var mock_response = APITypes.BattleResponse.new({
		"battle_result": {
			"winner": 1,
			"duration": 10.0,
			"player1_quota": 100,
			"player2_quota": 0,
			"actions": [],
			"seed": 12345,
			"opponent_name": "AI Opponent",
			"opponent_type": "ai",
			"player_inventory": {"items": [], "servers": []},
			"enemy_inventory": {"items": [], "servers": []}
		},
		"session_update": {
			"round": 2,
			"gold": initial_gold + 10,
			"gold_earned": 10,
			"wins": 1,
			"losses": 0,
			"lives": 5,
			"game_over": false,
			"victory": false, "shop_refresh_cost": 1,
			"combinations": [], "pending": []
		},
		"new_shop": [TestHelpers.item_data({"id": "shop_item_1", "cost": 3})],
		"inventory": {"inventory_grid": [], "inventory_storage": [], "server_containers": []},
		"battle_id": "test-battle-123"
	})

	GameStateManager.update_after_battle(mock_response)

	assert_eq(GameStateManager.current_round, 2, "Round should be 2")
	assert_eq(GameStateManager.gold, initial_gold + 10, "Gold should increase")
	assert_eq(GameStateManager.wins, 1, "Should have 1 win")
	assert_eq(GameStateManager.losses, 0, "Should have 0 losses")
	assert_eq(GameStateManager.player_lives, 5, "Lives should come from the session update")
	assert_false(GameStateManager.game_over, "Should not be game over")
	assert_false(GameStateManager.victory, "Should not be victory")

	assert_eq(GameStateManager.last_gold_earned, 10, "Gold earned should be kept for the post-battle screen")
	assert_eq(GameStateManager.current_shop.size(), 1, "Shop should be replaced with the new one")
	assert_eq(GameStateManager.current_shop[0]["item_type"], "null_blade", "Shop should hold the new item")
	assert_not_null(GameStateManager.last_battle_result, "Battle result should be kept for the post-battle screen")
	assert_eq(GameStateManager.last_battle_result.winner, 1, "Battle result should keep the winner")


func test_a_battle_brings_back_what_the_new_round_charges_to_reroll():
	"""The round resets the count the price climbs with, and the battle is
	where the client hears the round changed. Left alone, the shop opens
	saying the last roll's price over a roll that costs less."""
	GameStateManager.start_new_game()
	GameStateManager.shop_refresh_cost = 2

	GameStateManager.update_after_battle(APITypes.BattleResponse.new({
		"battle_result": {
			"winner": 1, "duration": 10.0, "player1_quota": 100,
			"player2_quota": 0, "actions": [], "seed": 1,
			"opponent_name": "AI", "opponent_type": "ai",
			"player_inventory": {"items": [], "servers": []},
			"enemy_inventory": {"items": [], "servers": []},
		},
		"session_update": {
			"round": 2, "gold": 12, "gold_earned": 10, "wins": 1, "losses": 0,
			"lives": 5, "game_over": false, "victory": false,
			"shop_refresh_cost": 1, "combinations": [], "pending": []
		},
		"new_shop": [],
		"inventory": {
			"inventory_grid": [], "inventory_storage": [],
			"server_containers": []
		},
		"battle_id": "b1"
	}))

	assert_eq(GameStateManager.shop_refresh_cost, 1,
		"A new round rolls the shelf for a gold again")


func test_battle_result_stores_events_for_playback():
	# BattleScreen reads last_battle_events and asserts when it is empty.
	GameStateManager.start_new_game()

	var mock_response = APITypes.BattleResponse.new({
		"battle_result": {
			"winner": 1, "duration": 10.0, "player1_quota": 100, "player2_quota": 0,
			"seed": 12345,
			"actions": [
				{"timestamp": 0, "source": "system", "action": "battle_start",
					"player": 0, "target": null, "damage": null,
					"details": {"hp": [25, 25], "max_hp": [25, 25]}},
				{"timestamp": 1500, "source": "enemy", "action": "damage",
					"player": 2, "target": "player", "damage": 20,
					"details": {"hp": [25, 5], "max_hp": [25, 25]}}
			],
			"opponent_name": "AI Opponent",
			"opponent_type": "ai",
			"player_inventory": {"items": [], "servers": []},
			"enemy_inventory": {"items": [], "servers": []}
		},
		"session_update": {
			"round": 2, "gold": 20, "gold_earned": 10, "wins": 1, "losses": 0,
			"lives": 5, "game_over": false, "victory": false, "shop_refresh_cost": 1,
			"combinations": [], "pending": []
		},
		"new_shop": [],
		"inventory": {"inventory_grid": [], "inventory_storage": [], "server_containers": []},
		"battle_id": "test-battle-123"
	})

	GameStateManager.update_after_battle(mock_response)

	assert_eq(GameStateManager.last_battle_events.size(), 2, "Battle events should be stored for playback")
	assert_eq(GameStateManager.last_battle_events[0].action, "battle_start", "Events should keep their order")
	assert_eq(GameStateManager.last_battle_events[1].damage, 20, "Events should keep their damage")


func test_defeat_updates_losses_and_lives():
	GameStateManager.start_new_game()

	var mock_response = APITypes.BattleResponse.new({
		"battle_result": {
			"winner": 2, "duration": 10.0, "player1_quota": 0, "player2_quota": 50,
			"actions": [], "seed": 1,
			"opponent_name": "AI Opponent",
			"opponent_type": "ai",
			"player_inventory": {"items": [], "servers": []},
			"enemy_inventory": {"items": [], "servers": []}
		},
		"session_update": {
			"round": 1, "gold": 12, "gold_earned": 0, "wins": 0, "losses": 1,
			"lives": 4, "game_over": false, "victory": false, "shop_refresh_cost": 1,
			"combinations": [], "pending": []
		},
		"new_shop": [],
		"inventory": {"inventory_grid": [], "inventory_storage": [], "server_containers": []},
		"battle_id": "test-battle-456"
	})

	GameStateManager.update_after_battle(mock_response)

	assert_eq(GameStateManager.losses, 1, "A defeat should count as a loss")
	assert_eq(GameStateManager.player_lives, 4, "A defeat should cost a life")
	assert_eq(GameStateManager.last_gold_earned, 0, "A defeat should earn no gold")


func test_game_over_comes_from_the_session_update():
	GameStateManager.start_new_game()

	var mock_response = APITypes.BattleResponse.new({
		"battle_result": {
			"winner": 2, "duration": 10.0, "player1_quota": 0, "player2_quota": 50,
			"actions": [], "seed": 1,
			"opponent_name": "AI Opponent",
			"opponent_type": "ai",
			"player_inventory": {"items": [], "servers": []},
			"enemy_inventory": {"items": [], "servers": []}
		},
		"session_update": {
			"round": 5, "gold": 0, "gold_earned": 0, "wins": 2, "losses": 5,
			"lives": 0, "game_over": true, "victory": false, "shop_refresh_cost": 1,
			"combinations": [], "pending": []
		},
		"new_shop": [],
		"inventory": {"inventory_grid": [], "inventory_storage": [], "server_containers": []},
		"battle_id": "test-battle-789"
	})

	GameStateManager.update_after_battle(mock_response)

	assert_true(GameStateManager.game_over, "Game over should come from the server")
	assert_true(GameStateManager.is_game_over(), "is_game_over() should agree")

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
