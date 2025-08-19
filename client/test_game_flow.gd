extends Node

# Test the actual game flow
func _ready():
	print("=== TESTING GAME FLOW ===")

	# Check autoloads
	var server_api = get_node("/root/ServerAPI")
	var game_state = get_node("/root/GameStateManager")

	if not server_api:
		print("✗ ServerAPI not found!")
		get_tree().quit(1)
		return

	if not game_state:
		print("✗ GameStateManager not found!")
		get_tree().quit(1)
		return

	print("✓ Autoloads loaded")

	# Test server connection
	print("Testing server connection...")

	# Connect to signals
	server_api.game_started.connect(_on_game_started)
	server_api.error_occurred.connect(_on_error)

	# Try to start a game
	print("Starting new game with seed 42...")
	server_api.start_new_game(42)

	# Wait for response
	await get_tree().create_timer(3.0).timeout

	print("If you see this and no game started message, the server may not be running.")
	print("Make sure to run: cd server && TEST_MODE=true python main.py")

	# Quit after test
	await get_tree().create_timer(1.0).timeout
	get_tree().quit()

func _on_game_started(player_id: String, game_data: Dictionary):
	print("✓ Game started successfully!")
	print("  Player ID: ", player_id.substr(0, 8), "...")
	print("  Gold: ", game_data.get("session", {}).get("gold", 0))
	print("  Lives: ", game_data.get("session", {}).get("lives", 0))
	print("  Shop items: ", game_data.get("session", {}).get("current_shop", []).size())
	print("\n✅ CLIENT-SERVER INTEGRATION WORKING!")

func _on_error(message: String):
	print("✗ Error: ", message)
	print("  Make sure the server is running!")
	get_tree().quit(1)
