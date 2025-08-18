extends SceneTree
# Test that starting_containers property is properly added and works

func _init():
	print("\n=== Testing Starting Containers Fix ===")

	# Test 1: Verify GameStateManager has starting_containers property now
	print("\nTest 1: Checking if GameStateManager has starting_containers property...")
	assert("starting_containers" in GameStateManager, "GameStateManager should have starting_containers property")
	print("✓ GameStateManager has 'starting_containers' property")

	# Test 2: Test setting and getting starting_containers
	print("\nTest 2: Testing set/get of starting_containers...")
	var test_containers = [
		{"type": "cube_2x2", "position": Vector2i(1, 3)},
		{"type": "cube_2x2", "position": Vector2i(4, 3)},
		{"type": "cube_2x2", "position": Vector2i(7, 3)}
	]

	# This should now work without error
	GameStateManager.starting_containers = test_containers
	assert(GameStateManager.starting_containers.size() == 3, "Should have 3 containers")
	assert(GameStateManager.starting_containers[0].type == "cube_2x2", "First container should be cube_2x2")
	print("✓ Successfully set and retrieved starting_containers")

	# Test 3: Verify start_new_game clears starting_containers
	print("\nTest 3: Testing that start_new_game() clears starting_containers...")
	GameStateManager.start_new_game()
	assert(GameStateManager.starting_containers.size() == 0, "starting_containers should be empty after start_new_game")
	print("✓ start_new_game() properly clears starting_containers")

	# Test 4: Simulate the flow from MainMenu
	print("\nTest 4: Simulating MainMenu flow...")
	var mock_session_data = {
		"player_id": "test-player",
		"round": 1,
		"gold": 10,
		"current_shop": [],
		"starting_containers": [
			{"type": "cube_2x2", "position": Vector2i(2, 2)},
			{"type": "rack_2x3", "position": Vector2i(5, 1)}
		]
	}

	# Simulate what MainMenu does
	GameStateManager.player_id = mock_session_data.player_id
	GameStateManager.current_round = mock_session_data.round
	GameStateManager.gold = mock_session_data.gold
	GameStateManager.current_shop = mock_session_data.current_shop

	# This is the line that was causing the error - should work now
	if mock_session_data.has("starting_containers"):
		GameStateManager.starting_containers = mock_session_data.starting_containers
		print("✓ Successfully set starting_containers from mock session data")

	assert(GameStateManager.starting_containers.size() == 2, "Should have 2 containers from session")
	assert(GameStateManager.starting_containers[1].type == "rack_2x3", "Second container should be rack_2x3")

	print("\n✅ All starting containers tests passed!")
	print("The bug has been fixed - GameStateManager now has the starting_containers property")
	quit(0)
