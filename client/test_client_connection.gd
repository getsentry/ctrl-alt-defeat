extends SceneTree

func _init():
	print("Testing client connection to server...")

	# Create the ServerAPI
	var server_api = preload("res://scripts/ServerAPI.gd").new()
	root.add_child(server_api)

	# Connect signals
	server_api.game_started.connect(_on_game_started)
	server_api.error_occurred.connect(_on_error)

	# Start a new game
	print("Starting new game...")
	server_api.start_new_game(42)

	# Wait for response
	await create_timer(2.0).timeout

	print("Test complete!")
	quit()

func _on_game_started(player_id: String, game_data: Dictionary):
	print("✅ Game started successfully!")
	print("Player ID: ", player_id)
	print("Initial gold: ", game_data.get("session", {}).get("gold", 0))
	print("Shop items: ", game_data.get("session", {}).get("current_shop", []).size())

func _on_error(message: String):
	print("❌ Error: ", message)
