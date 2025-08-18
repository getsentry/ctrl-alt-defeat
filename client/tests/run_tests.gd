extends Node
# Test runner that can access GameStateManager and other autoloads

func _ready():
	print("\n" + "="*60)
	print("RUNNING AUTOBATTLER TESTS")
	print("="*60)

	# Run all test suites
	var all_passed = true

	all_passed = test_game_state_manager() and all_passed
	all_passed = test_starting_containers() and all_passed
	all_passed = test_inventory_persistence() and all_passed

	if all_passed:
		print("\n" + "="*60)
		print("✅ ALL TESTS PASSED!")
		print("="*60)
	else:
		print("\n" + "="*60)
		print("❌ SOME TESTS FAILED")
		print("="*60)

	# Exit after tests
	get_tree().quit(0 if all_passed else 1)

func test_game_state_manager() -> bool:
	print("\n--- Testing GameStateManager Properties ---")

	# Test that starting_containers property exists (the bug we fixed)
	if not "starting_containers" in GameStateManager:
		print("❌ FAILED: GameStateManager missing 'starting_containers' property")
		return false
	print("✓ starting_containers property exists")

	# Test setting and getting
	var test_containers = [
		{"type": "cube_2x2", "position": Vector2i(1, 3)}
	]
	GameStateManager.starting_containers = test_containers

	if GameStateManager.starting_containers.size() != 1:
		print("❌ FAILED: Could not set starting_containers")
		return false
	print("✓ Can set and get starting_containers")

	# Test start_new_game clears it
	GameStateManager.start_new_game()
	if GameStateManager.starting_containers.size() != 0:
		print("❌ FAILED: start_new_game() didn't clear starting_containers")
		return false
	print("✓ start_new_game() clears starting_containers")

	print("✅ GameStateManager tests passed")
	return true

func test_starting_containers() -> bool:
	print("\n--- Testing Starting Containers Flow ---")

	# Simulate what MainMenu does when starting a new game
	GameStateManager.start_new_game()

	# Simulate server response with starting containers
	var mock_session = {
		"player_id": "test-123",
		"round": 1,
		"gold": 10,
		"current_shop": [],
		"starting_containers": [
			{"type": "cube_2x2", "position": Vector2i(1, 3)},
			{"type": "cube_2x2", "position": Vector2i(4, 3)},
			{"type": "cube_2x2", "position": Vector2i(7, 3)}
		]
	}

	# This is what was causing the error before
	if mock_session.has("starting_containers"):
		GameStateManager.starting_containers = mock_session.starting_containers

	if GameStateManager.starting_containers.size() != 3:
		print("❌ FAILED: Starting containers not set correctly")
		return false
	print("✓ Starting containers set from mock session")

	print("✅ Starting containers flow tests passed")
	return true

func test_inventory_persistence() -> bool:
	print("\n--- Testing Inventory Persistence ---")

	GameStateManager.start_new_game()

	# Test saving inventory
	var test_items = [
		{"data": {"name": "CPU", "width": 1, "height": 1}, "grid_pos": Vector2i(2, 2)}
	]
	var test_servers = [
		{"data": {"name": "Rack", "pattern": [[1,1],[1,1]]}, "pos": Vector2i(0, 0)}
	]

	GameStateManager.save_inventory_state(test_items, test_servers)

	var saved = GameStateManager.get_inventory_state()
	if saved.items.size() != 1 or saved.servers.size() != 1:
		print("❌ FAILED: Inventory not saved correctly")
		return false
	print("✓ Inventory saved and retrieved")

	# Test that inventory persists after battle
	var mock_battle_result = {
		"battle_result": {"winner": 1},
		"session_update": {"round": 2, "gold": 20}
	}

	GameStateManager.update_after_battle(mock_battle_result)

	var after_battle = GameStateManager.get_inventory_state()
	if after_battle.items.size() != 1:
		print("❌ FAILED: Inventory lost after battle")
		return false
	print("✓ Inventory persists after battle")

	print("✅ Inventory persistence tests passed")
	return true
