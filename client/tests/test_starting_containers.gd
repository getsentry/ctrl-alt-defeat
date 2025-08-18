extends SceneTree
# Test that starting_containers property doesn't cause errors

func _init():
	print("\n=== Testing Starting Containers Bug ===")

	# Test 1: Verify GameStateManager doesn't have starting_containers property
	print("\nTest 1: Checking if GameStateManager has starting_containers property...")
	var has_property = "starting_containers" in GameStateManager
	print("Has 'starting_containers' property: %s" % has_property)

	# Test 2: Try to set starting_containers and catch error
	print("\nTest 2: Attempting to set starting_containers...")
	var test_containers = [
		{"type": "cube_2x2", "position": Vector2i(1, 3)},
		{"type": "cube_2x2", "position": Vector2i(4, 3)},
		{"type": "cube_2x2", "position": Vector2i(7, 3)}
	]

	# This should fail with the error the user reported
	print("Trying to set GameStateManager.starting_containers...")

	# Check if property exists before trying to set it
	if not has_property:
		print("ERROR: GameStateManager does not have 'starting_containers' property!")
		print("This would cause: Invalid assignment of property or key 'starting_containers'")
		assert(false, "Missing starting_containers property in GameStateManager")
	else:
		GameStateManager.starting_containers = test_containers
		print("✓ Successfully set starting_containers")

	print("\n✅ Test complete")
	quit(0)
