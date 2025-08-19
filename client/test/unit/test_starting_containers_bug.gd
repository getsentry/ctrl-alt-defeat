extends GutTest
# Regression test for the starting_containers bug that was causing crashes

func before_each():
	# Reset state before each test
	GameStateManager.start_new_game()

func test_main_menu_starting_containers_assignment():
	# This is the exact code that was failing in MainMenu.gd
	var mock_session_data = {
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

	# This line was causing: "Invalid assignment of property or key 'starting_containers'"
	# Now it should work fine
	if mock_session_data.has("starting_containers"):
		GameStateManager.starting_containers = mock_session_data.starting_containers

	assert_eq(GameStateManager.starting_containers.size(), 3,
		"Should have set 3 starting containers from session data")
	assert_eq(GameStateManager.starting_containers[0].type, "cube_2x2",
		"First container should be cube_2x2")

func test_game_over_screen_starting_containers_assignment():
	# Test the same assignment from GameOverScreen.gd
	var session_data = {
		"starting_containers": [
			{"type": "rack_2x3", "position": Vector2i(2, 2)}
		]
	}

	if session_data.has("starting_containers"):
		GameStateManager.starting_containers = session_data.starting_containers

	assert_eq(GameStateManager.starting_containers.size(), 1,
		"Should have 1 container from game over screen")
	assert_eq(GameStateManager.starting_containers[0].type, "rack_2x3",
		"Container should be rack_2x3")

func test_empty_starting_containers_is_valid():
	# Test that empty array is also valid
	GameStateManager.starting_containers = []
	assert_eq(GameStateManager.starting_containers.size(), 0,
		"Empty starting_containers should be valid")

	# Test clearing via start_new_game
	GameStateManager.starting_containers = [{"type": "test"}]
	GameStateManager.start_new_game()
	assert_eq(GameStateManager.starting_containers.size(), 0,
		"start_new_game should clear starting_containers")

func test_unified_grid_uses_starting_containers():
	# Set up starting containers in GameStateManager
	GameStateManager.starting_containers = [
		{"type": "cube_2x2", "position": Vector2i(5, 5)}
	]

	# UnifiedGridUI should be able to read this
	var containers = GameStateManager.starting_containers
	assert_eq(containers.size(), 1, "Should retrieve containers from GameStateManager")
	assert_eq(containers[0].position, Vector2i(5, 5), "Position should be (5, 5)")
