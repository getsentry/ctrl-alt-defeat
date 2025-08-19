extends SceneTree

func _init():
	print("Testing Godot-Server Integration...")

	# Get autoload references
	var server_api = get_root().get_node("/root/ServerAPI")
	var game_state = get_root().get_node("/root/GameStateManager")

	if server_api:
		print("✓ ServerAPI autoload found")
	else:
		print("✗ ServerAPI not found")
		quit(1)

	if game_state:
		print("✓ GameStateManager autoload found")
	else:
		print("✗ GameStateManager not found")
		quit(1)

	# Try to start a new game
	print("Starting new game session...")
	server_api.start_new_game(42)

	# Wait for response
	await create_timer(2.0).timeout

	print("Test complete!")
	quit(0)
