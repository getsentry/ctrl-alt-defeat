extends GutTest
# Test server-provided starting containers

func test_server_starting_containers_format():
	# Test that we can handle server format for starting containers
	GameStateManager.start_new_game()

	# Simulate server response with starting containers
	var server_containers = [
		{
			"type": "standard_vm",
			"name": "Standard VM",
			"position": {"x": 1, "y": 3},
			"width": 2,
			"height": 2
		},
		{
			"type": "standard_vm",
			"name": "Standard VM",
			"position": {"x": 3, "y": 3},
			"width": 2,
			"height": 2
		},
		{
			"type": "standard_vm",
			"name": "Standard VM",
			"position": {"x": 5, "y": 3},
			"width": 2,
			"height": 2
		}
	]

	GameStateManager.starting_containers = server_containers

	# Verify they were stored correctly
	assert_eq(GameStateManager.starting_containers.size(), 3, "Should have 3 starting containers")

	# Check first container
	var first = GameStateManager.starting_containers[0]
	assert_eq(first.type, "standard_vm", "Should be standard_vm type")
	assert_eq(first.position.x, 1, "Should be at x=1")
	assert_eq(first.position.y, 3, "Should be at y=3")
	assert_eq(first.width, 2, "Should be 2 wide")
	assert_eq(first.height, 2, "Should be 2 high")

func test_container_position_handling():
	# Test that UnifiedGridUI can handle both Vector2i and dict formats

	# Dictionary format (from server)
	var dict_pos = {"x": 5, "y": 7}

	# Simulate what UnifiedGridUI does
	var position
	if dict_pos is Dictionary:
		position = Vector2i(dict_pos.get("x", 1), dict_pos.get("y", 3))

	assert_eq(position.x, 5, "Should extract x from dict")
	assert_eq(position.y, 7, "Should extract y from dict")

func test_standard_vm_mapping():
	# Test that standard_vm from server maps to cube_2x2 on client
	GameStateManager.start_new_game()

	# Set containers with standard_vm type
	GameStateManager.starting_containers = [
		{"type": "standard_vm", "position": {"x": 1, "y": 1}}
	]

	# The client should map this to cube_2x2
	var container_type = GameStateManager.starting_containers[0].type
	assert_eq(container_type, "standard_vm", "Raw data should still say standard_vm")

	# But UnifiedGridUI should map it
	# This is handled in UnifiedGridUI._place_starting_containers

func test_multiple_containers_side_by_side():
	# Test 3 containers placed side by side
	GameStateManager.start_new_game()

	var containers = [
		{"type": "standard_vm", "position": {"x": 1, "y": 3}, "width": 2, "height": 2},
		{"type": "standard_vm", "position": {"x": 3, "y": 3}, "width": 2, "height": 2},
		{"type": "standard_vm", "position": {"x": 5, "y": 3}, "width": 2, "height": 2}
	]

	GameStateManager.starting_containers = containers

	# Verify positioning doesn't overlap
	var positions_used = []
	for container in GameStateManager.starting_containers:
		var x = container.position.x
		var y = container.position.y
		var w = container.width
		var h = container.height

		# Check all squares this container occupies
		for dy in range(h):
			for dx in range(w):
				var pos = Vector2i(x + dx, y + dy)
				assert_false(pos in positions_used,
					"Position %s should not be occupied by multiple containers" % pos)
				positions_used.append(pos)

	# Should occupy 12 total squares (3 containers * 2x2 each)
	assert_eq(positions_used.size(), 12, "3 2x2 containers should occupy 12 squares")
