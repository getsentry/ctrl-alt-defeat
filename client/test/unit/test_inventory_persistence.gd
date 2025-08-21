extends GutTest
# Test inventory persistence between scenes

const APITypes = preload("res://scripts/api_types.gd")

func before_each():
	GameStateManager.start_new_game()

func test_save_and_load_inventory():
	# Save inventory
	var test_items = [
		{"data": {"name": "CPU", "shape": [[0, 0]], "width": 1, "height": 1, "cost": 3}, "grid_pos": Vector2i(2, 2)},
		{"data": {"name": "RAM", "shape": [[0, 0], [1, 0]], "width": 2, "height": 1, "cost": 4}, "grid_pos": Vector2i(3, 3)}
	]
	var test_servers = [
		{"data": {"name": "Rack", "pattern": [[1,1],[1,1]], "cost": 5}, "pos": Vector2i(0, 0)}
	]

	GameStateManager.save_inventory_state(test_items, test_servers)

	# Load and verify
	var loaded = GameStateManager.get_inventory_state()
	assert_eq(loaded.items.size(), 2, "Should have 2 items")
	assert_eq(loaded.servers.size(), 1, "Should have 1 server")
	assert_eq(loaded.items[0].data.name, "CPU", "First item should be CPU")
	assert_eq(loaded.servers[0].data.name, "Rack", "Server should be Rack")

func test_inventory_survives_battle():
	# Setup inventory
	var items = [{"data": {"name": "Test", "shape": [[0, 0]], "width": 1, "height": 1}, "grid_pos": Vector2i(1, 1)}]
	var servers = [{"data": {"name": "Server", "pattern": [[1,1]]}, "pos": Vector2i(0, 0)}]
	GameStateManager.save_inventory_state(items, servers)

	# Simulate battle with typed response
	var mock_response = APITypes.BattleResponse.new({
		"battle_result": {
			"winner": 1,
			"duration": 10.0,
			"player1_quota": 100,
			"player2_quota": 0,
			"actions": [],
			"seed": 12345,
			"player_inventory": {"items": [], "servers": []},
			"enemy_inventory": {"items": [], "servers": []}
		},
		"session_update": {
			"round": 2,
			"gold": 20,
			"gold_earned": 5,
			"wins": 1,
			"losses": 0,
			"lives": 5,
			"game_over": false,
			"victory": false
		},
		"new_shop": [],
		"battle_id": "test-123"
	})
	GameStateManager.update_after_battle(mock_response)

	# Check inventory still there
	var after = GameStateManager.get_inventory_state()
	assert_eq(after.items.size(), 1, "Items should persist")
	assert_eq(after.servers.size(), 1, "Servers should persist")

func test_empty_inventory_is_valid():
	GameStateManager.save_inventory_state([], [])
	var loaded = GameStateManager.get_inventory_state()
	assert_eq(loaded.items.size(), 0, "Empty items should be valid")
	assert_eq(loaded.servers.size(), 0, "Empty servers should be valid")

func test_inventory_cleared_on_new_game():
	# Setup inventory
	var items = [{"data": {"name": "Test", "shape": [[0, 0]]}, "grid_pos": Vector2i(1, 1)}]
	GameStateManager.save_inventory_state(items, [])

	# Verify it was saved
	var before = GameStateManager.get_inventory_state()
	assert_eq(before.items.size(), 1, "Should have 1 item before new game")

	# Start new game
	GameStateManager.start_new_game()

	# Check inventory is cleared (current_inventory is now an empty dictionary)
	var after = GameStateManager.get_inventory_state()
	# After clear, it's just an empty dictionary, not a dictionary with items/servers keys
	assert_true(after.is_empty() or (after.has("items") and after.items.size() == 0),
		"Inventory should be cleared after new game")
