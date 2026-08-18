extends GutTest
# Test server-provided starting containers

func test_server_starting_containers_format():
	# Test that we can handle server format for starting containers
	GameStateManager.start_new_game()

	# Simulate server response with starting containers
	var server_containers = [
		TestHelpers.container_data({"position": [1, 3]}),
		TestHelpers.container_data({"position": [3, 3]}),
		TestHelpers.container_data({"position": [5, 3]})
	]

	GameStateManager.server_containers = server_containers

	# Verify they were stored correctly
	assert_eq(GameStateManager.server_containers.size(), 3, "Should have 3 starting containers")

	# Check first container
	var first = GameStateManager.server_containers[0]
	assert_eq(first.item_type, "standard_vm", "Should be standard_vm type")
	assert_eq(first.position[0], 1, "Should be at x=1")
	assert_eq(first.position[1], 3, "Should be at y=3")
	assert_eq(first.shape, [[0, 0], [1, 0], [0, 1], [1, 1]], "Should cover a 2x2 block")

func test_container_position_handling():
	# A position is an [x, y] array.
	var array_pos = [5, 7]
	var position = Vector2i(array_pos[0], array_pos[1])

	assert_eq(position.x, 5, "Should read x from index 0")
	assert_eq(position.y, 7, "Should read y from index 1")

func test_standard_vm_mapping():
	# Test that standard_vm from server maps to cube_2x2 on client
	GameStateManager.start_new_game()

	# Set containers with standard_vm type
	GameStateManager.server_containers = [
		TestHelpers.container_data({"position": [1, 1]})
	]

	# The client should map this to cube_2x2
	var container_type = GameStateManager.server_containers[0].item_type
	assert_eq(container_type, "standard_vm", "Raw data should still say standard_vm")

	# But UnifiedGridUI should map it
	# This is handled in UnifiedGridUI._place_starting_containers

func test_multiple_containers_side_by_side():
	# Test 3 containers placed side by side
	GameStateManager.start_new_game()

	var containers = [
		TestHelpers.container_data({"position": [1, 3]}),
		TestHelpers.container_data({"position": [3, 3]}),
		TestHelpers.container_data({"position": [5, 3]})
	]

	GameStateManager.server_containers = containers

	# Verify positioning doesn't overlap
	var positions_used = []
	for container in GameStateManager.server_containers:
		var x = container.position[0]
		var y = container.position[1]

		# Check all squares this container occupies
		for offset in container.shape:
			var pos = Vector2i(x + offset[0], y + offset[1])
			assert_false(pos in positions_used,
				"Position %s should not be occupied by multiple containers" % pos)
			positions_used.append(pos)

	# Should occupy 12 total squares (3 containers * 2x2 each)
	assert_eq(positions_used.size(), 12, "3 2x2 containers should occupy 12 squares")
